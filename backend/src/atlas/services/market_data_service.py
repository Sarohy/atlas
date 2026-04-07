"""Service for syncing live market data from Polygon.io into position records."""

import asyncio
import statistics
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.position import Position

# Polygon free-tier daily aggregates endpoint — one request per ticker.
# Snapshot endpoints (/v2/snapshot, /v3/snapshot) require a paid plan.
_POLYGON_AGGS_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"

# 365 calendar days ≈ 252 trading sessions — the standard 1-year beta window.
# Also provides enough bars for current price (last 2 sessions).
_LOOKBACK_DAYS = 365

# Market benchmark used for beta calculation.
_BENCHMARK_TICKER = "SPY"

# Max concurrent Polygon requests — stays within free-tier rate limits.
_MAX_CONCURRENCY = 5

# Minimum number of aligned return pairs needed to produce a meaningful beta.
_MIN_RETURN_PAIRS = 30


class MarketDataService:
    """Fetches delayed daily quotes + computes 1-year beta from Polygon free tier."""

    def __init__(self, api_key: str, session: AsyncSession, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._session = session
        self._client = client

    async def sync_positions(self) -> list[Position]:
        """Fetch quotes and beta for all positions; persist to DB.

        Strategy:
          1. Load all positions from DB.
          2. Fetch 365-day daily bars for SPY once (benchmark for beta).
          3. Concurrently fetch 365-day bars per ticker.
          4. For each ticker: extract price data from last 2 bars; compute
             beta by aligning daily returns with SPY returns.
        """
        result = await self._session.execute(select(Position).order_by(Position.ticker))
        positions: list[Position] = list(result.scalars().all())

        if not positions:
            return []

        to_date = date.today()
        from_date = to_date - timedelta(days=_LOOKBACK_DAYS)

        # Fetch SPY benchmark first — used by every beta calculation.
        spy_bars = await self._fetch_raw_bars(_BENCHMARK_TICKER, from_date, to_date)
        # Build a timestamp → close map for fast O(1) alignment.
        spy_close_by_ts: dict[int, float] = {b["t"]: b["c"] for b in spy_bars if "t" in b and "c" in b}

        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

        async def fetch_one(position: Position) -> tuple[Position, list[dict]]:  # type: ignore[type-arg]
            async with semaphore:
                bars = await self._fetch_raw_bars(position.ticker, from_date, to_date)
            return position, bars

        results_pairs = await asyncio.gather(*(fetch_one(p) for p in positions))

        now = datetime.now(tz=timezone.utc)
        for position, bars in results_pairs:
            self._apply_market_data(position, bars, spy_close_by_ts, now)

        return positions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_raw_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict]:  # type: ignore[type-arg]
        """Return raw OHLCV bar dicts from Polygon for the given date range.

        Each bar dict contains at minimum: ``t`` (ms timestamp), ``c`` (close),
        ``o`` (open). Returns an empty list on any error.
        """
        url = _POLYGON_AGGS_URL.format(
            ticker=ticker,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        try:
            response = await self._client.get(
                url,
                params={"adjusted": "true", "sort": "asc", "limit": "500", "apiKey": self._api_key},
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return []

        payload: dict = response.json()  # type: ignore[type-arg]
        return payload.get("results", [])  # type: ignore[type-arg]

    @staticmethod
    def _compute_beta(
        ticker_bars: list[dict],  # type: ignore[type-arg]
        spy_close_by_ts: dict[int, float],
    ) -> Decimal | None:
        """Compute rolling 1-year beta vs SPY using daily log-like returns.

        Beta = Cov(ticker_returns, spy_returns) / Var(spy_returns)

        Only trading days present in *both* series are used (inner join on
        timestamp). Returns None if fewer than _MIN_RETURN_PAIRS pairs exist.
        """
        # Build an ordered list of (ticker_close, spy_close) for matching days.
        aligned: list[tuple[float, float]] = []
        for bar in ticker_bars:
            ts = bar.get("t")
            tc = bar.get("c")
            sc = spy_close_by_ts.get(ts)  # type: ignore[arg-type]
            if ts is not None and tc is not None and sc is not None:
                aligned.append((float(tc), float(sc)))

        # Need at least _MIN_RETURN_PAIRS + 1 closes to produce that many returns.
        if len(aligned) < _MIN_RETURN_PAIRS + 1:
            return None

        ticker_closes = [p[0] for p in aligned]
        spy_closes = [p[1] for p in aligned]

        # Daily simple returns: (P_t - P_{t-1}) / P_{t-1}
        n = len(ticker_closes)
        ticker_rets = [
            (ticker_closes[i] - ticker_closes[i - 1]) / ticker_closes[i - 1]
            for i in range(1, n)
        ]
        spy_rets = [
            (spy_closes[i] - spy_closes[i - 1]) / spy_closes[i - 1]
            for i in range(1, n)
        ]

        var_spy = statistics.variance(spy_rets)
        if var_spy == 0:
            return None

        n_ret = len(ticker_rets)
        ticker_mean = statistics.mean(ticker_rets)
        spy_mean = statistics.mean(spy_rets)
        cov = sum(
            (t - ticker_mean) * (s - spy_mean)
            for t, s in zip(ticker_rets, spy_rets)
        ) / (n_ret - 1)

        try:
            return Decimal(str(round(cov / var_spy, 4)))
        except InvalidOperation:
            return None

    @staticmethod
    def _apply_market_data(
        position: Position,
        bars: list[dict],  # type: ignore[type-arg]
        spy_close_by_ts: dict[int, float],
        now: datetime,
    ) -> None:
        """Write computed market-data and beta onto a Position instance (no flush)."""

        def to_dec(value: object) -> Decimal | None:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return None

        if not bars:
            return

        # --- Price data: last 2 bars ---
        latest = bars[-1]
        current_price = to_dec(latest.get("c"))
        if current_price is None:
            return

        if len(bars) >= 2:
            previous_close = to_dec(bars[-2].get("c"))
        else:
            previous_close = to_dec(latest.get("o"))

        if previous_close is not None and previous_close != 0:
            day_change = current_price - previous_close
            day_change_pct = to_dec(
                float((day_change / previous_close) * 100)
            )
        else:
            day_change = None
            day_change_pct = None

        # --- Beta: full 365-day window aligned with SPY ---
        beta = MarketDataService._compute_beta(bars, spy_close_by_ts)

        position.current_price = current_price
        position.previous_close = previous_close
        position.day_change = day_change
        position.day_change_pct = day_change_pct
        position.position_value = current_price * position.shares
        position.beta = beta
        position.synced_at = now
