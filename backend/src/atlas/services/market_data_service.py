"""Service for syncing live market data from Polygon.io into ticker records.

Paid-tier strategy (two phases):

  Phase 1 — Quotes (⌈N / 250⌉ HTTP requests):
    Batch snapshot calls return real-time price, previous close and today's
    change for up to 250 tickers per request.  Paid-tier snapshots reflect
    the most-recent trade rather than the prior session's close.

  Phase 2 — Beta (N + 1 HTTP requests, concurrency-limited):
    365-day daily aggregate bars are fetched for SPY (benchmark) and each
    ticker.  β = Cov(r_ticker, r_spy) / Var(r_spy) is computed on the
    aligned daily simple-return series using sample statistics (n − 1).
"""

import asyncio
import statistics
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.ticker import Ticker
from atlas.models.watchlist import WatchlistItem

# ---------------------------------------------------------------------------
# Polygon endpoint templates
# ---------------------------------------------------------------------------

# Paid-tier batch snapshot — returns real-time price, prev close, day change.
# Accepts up to _SNAPSHOT_BATCH_SIZE comma-separated tickers per request.
_POLYGON_SNAPSHOT_URL = (
    "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
)

# Daily aggregate bars — used exclusively for the rolling beta calculation.
_POLYGON_AGGS_URL = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# 365 calendar days ≈ 252 trading sessions — the standard 1-year beta window.
_LOOKBACK_DAYS = 365

# S&P 500 ETF used as the broad-market benchmark in beta calculations.
_BENCHMARK_TICKER = "SPY"

# Polygon hard limit on symbols per batch snapshot request.
_SNAPSHOT_BATCH_SIZE = 250

# Max concurrent aggregate requests — paid tier supports substantially higher
# throughput than the free tier (previously limited to 5 requests/minute).
_MAX_CONCURRENCY = 20

# Minimum aligned return pairs for a statistically meaningful beta estimate.
# 30 pairs ≈ 6 weeks of daily data; below this the estimate is unreliable.
_MIN_RETURN_PAIRS = 30

# Polygon can emit 0 for snapshot closes before a usable session price exists.
_MIN_VALID_PRICE = Decimal("0")


class MarketDataService:
    """Fetches real-time quotes and computes 1-year rolling beta via Polygon."""

    def __init__(
        self,
        api_key: str,
        session: AsyncSession,
        client: httpx.AsyncClient,
    ) -> None:
        self._api_key = api_key
        self._session = session
        self._client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_tickers(self) -> list[Ticker]:
        """Fetch live quotes + beta for all tickers; persist to DB.

        Phase 1: batch snapshot call(s) for current price, previous close
                 and today's dollar/percent change.
        Phase 2: 365-day daily agg bars for SPY and each ticker to compute
                 rolling 1-year beta.
        """
        result = await self._session.execute(select(Ticker).order_by(Ticker.ticker))
        tickers: list[Ticker] = list(result.scalars().all())

        if not tickers:
            return []

        to_date = date.today()
        from_date = to_date - timedelta(days=_LOOKBACK_DAYS)

        # Phase 1: batch snapshot — ⌈N/250⌉ requests cover all tickers.
        snapshot_map = await self._fetch_snapshot_batch([t.ticker for t in tickers])

        # Phase 2: SPY daily bars first (needed by every beta calculation).
        spy_bars = await self._fetch_raw_bars(_BENCHMARK_TICKER, from_date, to_date)
        spy_close_by_ts = self._build_close_map(spy_bars)

        # Fetch each ticker's agg bars concurrently (rate-limited by semaphore).
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

        async def _fetch_one(t: Ticker) -> tuple[Ticker, list[dict]]:  # type: ignore[type-arg]
            async with semaphore:
                bars = await self._fetch_raw_bars(t.ticker, from_date, to_date)
            return t, bars

        agg_pairs = await asyncio.gather(*(_fetch_one(t) for t in tickers))

        now = datetime.now(tz=timezone.utc)
        for ticker, agg_bars in agg_pairs:
            snap = snapshot_map.get(ticker.ticker)
            beta = self._compute_beta(agg_bars, spy_close_by_ts)
            self._apply_market_data(ticker, snap, agg_bars, beta, now)

        return tickers

    async def sync_watchlist_items(self) -> list[WatchlistItem]:
        """Fetch live quotes + beta for all watchlist items; persist to DB.

        Uses the same two-phase strategy as ``sync_tickers``:
          Phase 1: batch snapshot for current price, previous close, day change.
          Phase 2: 365-day daily agg bars for SPY and each ticker for beta.
        """
        result = await self._session.execute(select(WatchlistItem).order_by(WatchlistItem.ticker))
        items: list[WatchlistItem] = list(result.scalars().all())

        if not items:
            return []

        to_date = date.today()
        from_date = to_date - timedelta(days=_LOOKBACK_DAYS)

        snapshot_map = await self._fetch_snapshot_batch([i.ticker for i in items])

        spy_bars = await self._fetch_raw_bars(_BENCHMARK_TICKER, from_date, to_date)
        spy_close_by_ts = self._build_close_map(spy_bars)

        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

        async def _fetch_one(item: WatchlistItem) -> tuple[WatchlistItem, list[dict]]:  # type: ignore[type-arg]
            async with semaphore:
                bars = await self._fetch_raw_bars(item.ticker, from_date, to_date)
            return item, bars

        agg_pairs = await asyncio.gather(*(_fetch_one(i) for i in items))

        now = datetime.now(tz=timezone.utc)
        for item, agg_bars in agg_pairs:
            snap = snapshot_map.get(item.ticker)
            beta = self._compute_beta(agg_bars, spy_close_by_ts)
            self._apply_watchlist_market_data(item, snap, agg_bars, beta, now)

        return items

    # ------------------------------------------------------------------
    # Private helpers — network
    # ------------------------------------------------------------------

    async def _fetch_snapshot_batch(
        self, symbols: list[str]
    ) -> dict[str, dict]:  # type: ignore[type-arg]
        """Return a {ticker: snapshot_dict} map via Polygon batch snapshot.

        Splits into ⌈N / _SNAPSHOT_BATCH_SIZE⌉ requests.  Symbols that are
        not returned by Polygon (e.g. invalid tickers, HTTP errors) are
        silently omitted from the result dict.
        """
        result: dict[str, dict] = {}  # type: ignore[type-arg]
        for i in range(0, len(symbols), _SNAPSHOT_BATCH_SIZE):
            chunk = await self._fetch_snapshot_chunk(symbols[i : i + _SNAPSHOT_BATCH_SIZE])
            result.update(chunk)
        return result

    async def _fetch_snapshot_chunk(
        self, symbols: list[str]
    ) -> dict[str, dict]:  # type: ignore[type-arg]
        """Fetch one batch snapshot request; return {ticker: snapshot_dict}."""
        try:
            response = await self._client.get(
                _POLYGON_SNAPSHOT_URL,
                params={"tickers": ",".join(symbols), "apiKey": self._api_key},
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return {}

        payload: dict = response.json()  # type: ignore[type-arg]
        return {
            snap["ticker"]: snap
            for snap in payload.get("tickers", [])
            if "ticker" in snap
        }

    async def _fetch_raw_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict]:  # type: ignore[type-arg]
        """Return OHLCV bar dicts from Polygon daily aggregates endpoint.

        Bars are sorted ascending by timestamp (``sort=asc``).  Returns an
        empty list on any HTTP error so callers degrade gracefully.
        """
        url = _POLYGON_AGGS_URL.format(
            ticker=ticker,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        try:
            response = await self._client.get(
                url,
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": "500",
                    "apiKey": self._api_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return []

        payload: dict = response.json()  # type: ignore[type-arg]
        return payload.get("results", [])

    # ------------------------------------------------------------------
    # Private helpers — computation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_close_map(
        bars: list[dict],  # type: ignore[type-arg]
    ) -> dict[int, float]:
        """Build a {unix_ms_timestamp: close_price} map from daily agg bars."""
        close_map: dict[int, float] = {}
        for bar in bars:
            ts = bar.get("t")
            close = bar.get("c")
            if ts is not None and close is not None:
                close_map[int(ts)] = float(close)
        return close_map

    @staticmethod
    def _compute_beta(
        ticker_bars: list[dict],  # type: ignore[type-arg]
        spy_close_by_ts: dict[int, float],
    ) -> Decimal | None:
        """Compute rolling 1-year beta vs SPY using daily simple returns.

        β = Cov(r_ticker, r_spy) / Var(r_spy)

        Uses ``statistics.covariance`` and ``statistics.variance`` (both use
        the sample / Bessel-corrected n − 1 denominator), so the estimator is
        consistent regardless of the number of aligned trading days.

        Only days present in *both* series are included (inner join on the
        Polygon millisecond timestamp).  Returns None when:
          - fewer than _MIN_RETURN_PAIRS aligned pairs exist, or
          - the SPY return variance is zero (flat/missing benchmark data).
        """
        # Inner join: only include closes present in both ticker and SPY.
        ticker_closes: list[float] = []
        spy_closes: list[float] = []
        for bar in ticker_bars:
            ts = bar.get("t")
            close = bar.get("c")
            if ts is None or close is None:
                continue
            spy_close = spy_close_by_ts.get(int(ts))
            if spy_close is None:
                continue
            ticker_closes.append(float(close))
            spy_closes.append(spy_close)

        # Need at least _MIN_RETURN_PAIRS + 1 closes to produce that many returns.
        if len(ticker_closes) < _MIN_RETURN_PAIRS + 1:
            return None

        n = len(ticker_closes)

        # Daily simple returns: (P_t − P_{t−1}) / P_{t−1}
        ticker_rets = [
            (ticker_closes[i] - ticker_closes[i - 1]) / ticker_closes[i - 1]
            for i in range(1, n)
        ]
        spy_rets = [
            (spy_closes[i] - spy_closes[i - 1]) / spy_closes[i - 1]
            for i in range(1, n)
        ]

        # statistics.variance uses sample variance (n − 1 denominator).
        var_spy = statistics.variance(spy_rets)
        if var_spy == 0:
            return None

        # statistics.covariance also uses n − 1; the denominators cancel in
        # the ratio so the (n − 1) correction has no net effect on the result.
        cov = statistics.covariance(ticker_rets, spy_rets)

        try:
            return Decimal(str(round(cov / var_spy, 4)))
        except InvalidOperation:
            return None

    @staticmethod
    def _apply_market_data(
        ticker: Ticker,
        snapshot: dict | None,  # type: ignore[type-arg]
        agg_bars: list[dict],  # type: ignore[type-arg]
        beta: Decimal | None,
        now: datetime,
    ) -> None:
        """Write price data and beta onto a Ticker instance (no flush).

        Price source priority:
          1. Polygon batch snapshot — real-time price, prev close, day change.
          2. Last two daily agg bars — fallback when snapshot is unavailable.

        Only ``beta`` and ``synced_at`` are written when no price data exists.
        """

        def to_dec(value: object) -> Decimal | None:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return None

        def to_price(value: object) -> Decimal | None:
            price = to_dec(value)
            if price is None or price <= _MIN_VALID_PRICE:
                return None
            return price

        current_price: Decimal | None = None
        previous_close: Decimal | None = None
        day_change: Decimal | None = None
        day_change_pct: Decimal | None = None

        if snapshot is not None:
            day = snapshot.get("day") or {}
            prev_day = snapshot.get("prevDay") or {}

            current_price = to_price(day.get("c"))
            previous_close = to_price(prev_day.get("c"))

            # Polygon snapshot provides the computed day change directly.
            day_change = to_dec(snapshot.get("todaysChange"))
            day_change_pct = to_dec(snapshot.get("todaysChangePerc"))

            # If the current session has no close yet, fall back to last agg bar.
            if current_price is None and agg_bars:
                current_price = to_price(agg_bars[-1].get("c"))

            if current_price is None:
                current_price = previous_close

        elif agg_bars:
            # Snapshot unavailable — derive from the last two daily agg bars.
            latest = agg_bars[-1]
            current_price = to_price(latest.get("c"))
            previous_close = (
                to_price(agg_bars[-2].get("c"))
                if len(agg_bars) >= 2
                else to_price(latest.get("o"))
            )

        # Re-derive day change locally when Polygon did not include it.
        if (
            day_change is None
            and current_price is not None
            and previous_close is not None
            and previous_close != 0
        ):
            day_change = current_price - previous_close
            day_change_pct = to_dec(float(day_change / previous_close * 100))

        # Always write the beta and audit timestamp.
        ticker.beta = beta
        ticker.synced_at = now

        if current_price is None:
            # No price data available — skip price-related fields.
            return

        ticker.current_price = current_price
        ticker.previous_close = previous_close
        ticker.day_change = day_change
        ticker.day_change_pct = day_change_pct
        ticker.position_value = current_price * ticker.shares

    @staticmethod
    def _apply_watchlist_market_data(
        item: WatchlistItem,
        snapshot: dict | None,  # type: ignore[type-arg]
        agg_bars: list[dict],  # type: ignore[type-arg]
        beta: Decimal | None,
        now: datetime,
    ) -> None:
        """Write price data and beta onto a WatchlistItem instance (no flush).

        Identical price-source priority to ``_apply_market_data`` except there
        is no position value to compute (watchlist items carry no share count).
        """

        def to_dec(value: object) -> Decimal | None:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return None

        current_price: Decimal | None = None
        previous_close: Decimal | None = None
        day_change: Decimal | None = None
        day_change_pct: Decimal | None = None

        if snapshot is not None:
            day = snapshot.get("day") or {}
            prev_day = snapshot.get("prevDay") or {}

            current_price = to_dec(day.get("c"))
            previous_close = to_dec(prev_day.get("c"))
            day_change = to_dec(snapshot.get("todaysChange"))
            day_change_pct = to_dec(snapshot.get("todaysChangePerc"))

            if current_price is None and agg_bars:
                current_price = to_dec(agg_bars[-1].get("c"))

        elif agg_bars:
            latest = agg_bars[-1]
            current_price = to_dec(latest.get("c"))
            previous_close = (
                to_dec(agg_bars[-2].get("c"))
                if len(agg_bars) >= 2
                else to_dec(latest.get("o"))
            )

        if (
            day_change is None
            and current_price is not None
            and previous_close is not None
            and previous_close != 0
        ):
            day_change = current_price - previous_close
            day_change_pct = to_dec(float(day_change / previous_close * 100))

        item.beta = beta
        item.synced_at = now

        if current_price is None:
            return

        item.current_price = current_price
        item.previous_close = previous_close
        item.day_change = day_change
        item.day_change_pct = day_change_pct
