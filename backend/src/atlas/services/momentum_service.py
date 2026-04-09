"""F1 Momentum scoring service.

Computes six momentum indicators — RSI, MACD, MA alignment, 52-week position,
1M/6M performance, and relative sector momentum — then rolls them into a
0-100 composite F1 score.

All calculation helpers are pure functions (no I/O, no side-effects) so they
can be tested in isolation without any network calls.  The ``MomentumService``
class owns all Polygon API access and calls the pure helpers once the raw bar
data has been fetched.

Scoring weights (max 100 pts total):
  RSI              0-20 pts
  MACD             0-20 pts
  MA alignment     0-20 pts
  52-week position 0-20 pts
  1M/6M perf       0-20 pts  (10 pts per sub-window)
  Sector momentum  0-20 pts  (capped so total never exceeds 100)
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Final

import httpx

from atlas.schemas.momentum import (
    F1Grade,
    MaAlignmentIndicator,
    MacdIndicator,
    MomentumResponse,
    PerformanceIndicator,
    RsiIndicator,
    SectorMomentumIndicator,
    Week52PositionIndicator,
)

# ---------------------------------------------------------------------------
# Named constants — scoring thresholds
# ---------------------------------------------------------------------------

# RSI period — Wilder's 14-session standard.
_RSI_PERIOD: Final[int] = 14

# MACD standard parameters: fast EMA, slow EMA, signal EMA.
_MACD_FAST: Final[int] = 12
_MACD_SLOW: Final[int] = 26
_MACD_SIGNAL: Final[int] = 9

# One trading month ≈ 21 sessions; six months ≈ 126 sessions.
_LOOKBACK_1M_BARS: Final[int] = 21
_LOOKBACK_6M_BARS: Final[int] = 126

# One calendar year of daily bars for 52-week range and indicators.
_LOOKBACK_DAYS: Final[int] = 365

# Three months for sector relative comparison.
_LOOKBACK_3M_BARS: Final[int] = 63

# Max concurrent Polygon requests within the service.
_MAX_CONCURRENCY: Final[int] = 5

# Polygon endpoints.
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)
_POLYGON_TICKER_DETAILS_URL: Final[str] = (
    "https://api.polygon.io/v3/reference/tickers/{ticker}"
)

# Map from Polygon SIC / industry group name fragments → sector ETF symbol.
# Only top-level GICS sectors that have a SPDR ETF are mapped.
_SECTOR_ETF_MAP: Final[dict[str, str]] = {
    "technology": "XLK",
    "software": "XLK",
    "semiconductor": "XLK",
    "computer": "XLK",
    "electronic": "XLK",
    "health": "XLV",
    "pharmaceutical": "XLV",
    "biotech": "XLV",
    "medical": "XLV",
    "bank": "XLF",
    "financial": "XLF",
    "insurance": "XLF",
    "invest": "XLF",
    "energy": "XLE",
    "oil": "XLE",
    "gas": "XLE",
    "petroleum": "XLE",
    "consumer discretionary": "XLY",
    "retail": "XLY",
    "automobile": "XLY",
    "apparel": "XLY",
    "food": "XLP",
    "beverage": "XLP",
    "household": "XLP",
    "tobacco": "XLP",
    "industrial": "XLI",
    "aerospace": "XLI",
    "defense": "XLI",
    "transport": "XLI",
    "chemical": "XLB",
    "material": "XLB",
    "mining": "XLB",
    "metal": "XLB",
    "utility": "XLU",
    "electric": "XLU",
    "water": "XLU",
    "real estate": "XLRE",
    "reit": "XLRE",
    "communication": "XLC",
    "telecom": "XLC",
    "media": "XLC",
}

# Default fallback sector ETF when no industry match found.
_DEFAULT_SECTOR_ETF: Final[str] = "SPY"

# F1 grade boundary thresholds (inclusive lower bound).
_GRADE_STRONG_BUY_MIN: Final[int] = 80
_GRADE_BUY_MIN: Final[int] = 60
_GRADE_NEUTRAL_MIN: Final[int] = 40
_GRADE_WEAK_MIN: Final[int] = 20


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def _compute_rsi(
    bars: list[dict],  # type: ignore[type-arg]
    period: int = _RSI_PERIOD,
) -> float | None:
    """Compute Wilder RSI from a list of OHLCV bar dicts.

    Uses the Wilder smoothed average (exponential smoothing factor 1/period).
    Returns None when fewer than ``period + 1`` bars are available.
    Returns 50.0 when the average loss is zero (flat or all-up series) to
    avoid a division-by-zero; RSI of 100 would be technically correct but 50
    is the convention for a completely flat series.
    """
    closes = [float(b["c"]) for b in bars if b.get("c") is not None]
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0.0, c) for c in changes]
    losses = [max(0.0, -c) for c in changes]

    # Seed with simple average of the first ``period`` changes.
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing for subsequent bars.
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        # All gains (or flat) → RSI = 100; convention: return 50 for truly flat
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _score_rsi(rsi: float) -> int:
    """Map RSI value to a 0-20 point momentum score.

    Scoring rationale:
      60-79 = strong momentum zone, but not yet overextended → 20 pts
      50-59 = constructive momentum → 15 pts
      80+   = overbought, still trending but caution → 10 pts
      40-49 = below midline, weak → 5 pts
      30-39 = bearish → 2 pts
      <30   = oversold → 0 pts
    """
    if 60.0 <= rsi < 80.0:
        return 20
    if 50.0 <= rsi < 60.0:
        return 15
    if rsi >= 80.0:
        return 10
    if 40.0 <= rsi < 50.0:
        return 5
    if 30.0 <= rsi < 40.0:
        return 2
    return 0  # rsi < 30


def _ema(values: list[float], period: int) -> list[float]:
    """Compute EMA of a price series using the standard multiplier 2/(N+1)."""
    if not values:
        return []
    k = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def _compute_macd(
    bars: list[dict],  # type: ignore[type-arg]
    fast: int = _MACD_FAST,
    slow: int = _MACD_SLOW,
    signal: int = _MACD_SIGNAL,
) -> tuple[float, float, float] | None:
    """Compute MACD line, signal line, and histogram.

    Returns ``(macd, signal, histogram)`` or None when the series is too short.
    Minimum bars required: ``slow + signal - 1``.
    """
    closes = [float(b["c"]) for b in bars if b.get("c") is not None]
    min_bars = slow + signal - 1
    if len(closes) < min_bars:
        return None

    fast_ema = _ema(closes, fast)
    slow_ema = _ema(closes, slow)

    # MACD line = fast EMA - slow EMA (aligned from index slow-1 onwards)
    macd_line = [f - s for f, s in zip(fast_ema[slow - 1 :], slow_ema[slow - 1 :], strict=True)]

    signal_ema = _ema(macd_line, signal)
    last_macd = macd_line[-1]
    last_signal = signal_ema[-1]
    histogram = last_macd - last_signal

    return last_macd, last_signal, histogram


def _score_macd(macd: float, signal: float, histogram: float) -> int:
    """Map MACD state to a 0-20 point momentum score.

    Scoring:
      MACD > signal AND histogram > 0 AND macd > 0 → 20 pts (bull expansion)
      MACD > signal AND histogram > 0              → 15 pts (bull crossover)
      MACD > signal                                → 10 pts (positive cross)
      MACD < signal AND histogram < 0 but shrinking → 5 pts (possible bottom)
      MACD < signal AND histogram < 0              → 0 pts (bearish)
    """
    above_signal = macd > signal
    positive_hist = histogram > 0

    if above_signal and positive_hist and macd > 0:
        return 20
    if above_signal and positive_hist:
        return 15
    if above_signal:
        return 10
    if not above_signal and histogram > -0.05:
        # histogram is small-negative — momentum may be bottoming
        return 5
    return 0


def _compute_ma_alignment(
    bars: list[dict],  # type: ignore[type-arg]
) -> tuple[float, float, float, str] | None:
    """Compute MA-20, MA-50, MA-200 and the alignment label.

    Returns ``(ma20, ma50, ma200, label)`` or None when < 200 bars exist.

    Labels:
      FULL_BULL   price > MA20 > MA50 > MA200
      BULL        price > MA20 and MA20 > MA50
      MIXED       price > MA20 only
      BEAR        price < MA20 but above MA200
      FULL_BEAR   price < MA200
    """
    closes = [float(b["c"]) for b in bars if b.get("c") is not None]
    if len(closes) < 200:
        return None

    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    ma200 = sum(closes[-200:]) / 200
    current = closes[-1]

    if current > ma20 > ma50 > ma200:
        label = "FULL_BULL"
    elif current > ma20 and ma20 > ma50:
        label = "BULL"
    elif current > ma20:
        label = "MIXED"
    elif current >= ma200:
        label = "BEAR"
    else:
        label = "FULL_BEAR"

    return ma20, ma50, ma200, label


def _score_ma_alignment(label: str) -> int:
    """Map MA alignment label to a 0-20 point momentum score."""
    return {
        "FULL_BULL": 20,
        "BULL": 15,
        "MIXED": 10,
        "BEAR": 5,
        "FULL_BEAR": 0,
    }.get(label, 0)


def _compute_52w_position(
    bars: list[dict],  # type: ignore[type-arg]
) -> tuple[float, float, float] | None:
    """Compute where the current price sits in the trailing 252-session range.

    Returns ``(high_52w, low_52w, position_pct)`` or None when < 252 bars.
    ``position_pct`` is in [0, 100]: 0 = at the 52w low, 100 = at the 52w high.
    """
    closes = [float(b["c"]) for b in bars if b.get("c") is not None]
    if len(closes) < 252:
        return None

    window = closes[-252:]
    high = max(window)
    low = min(window)
    current = closes[-1]

    if high == low:
        return high, low, 50.0

    pct = (current - low) / (high - low) * 100.0
    return high, low, pct


def _score_52w_position(position_pct: float) -> int:
    """Map 52-week position percentage to a 0-20 point score.

    Top quintile (≥80%) → 20 pts
    Second quintile (60-79%) → 15 pts
    Middle (40-59%) → 10 pts
    Fourth quintile (20-39%) → 5 pts
    Bottom quintile (<20%) → 0 pts
    """
    if position_pct >= 80.0:
        return 20
    if position_pct >= 60.0:
        return 15
    if position_pct >= 40.0:
        return 10
    if position_pct >= 20.0:
        return 5
    return 0


def _compute_performance(
    bars: list[dict],  # type: ignore[type-arg]
) -> tuple[float, float] | None:
    """Compute 1-month and 6-month total returns (as percentages).

    Returns ``(perf_1m_pct, perf_6m_pct)`` or None when insufficient bars.
    Needs at least ``_LOOKBACK_6M_BARS + 1`` bars.
    """
    closes = [float(b["c"]) for b in bars if b.get("c") is not None]
    min_bars = _LOOKBACK_6M_BARS + 1
    if len(closes) < min_bars:
        return None

    current = closes[-1]

    price_1m_ago = closes[-(_LOOKBACK_1M_BARS + 1)]
    price_6m_ago = closes[-(_LOOKBACK_6M_BARS + 1)]

    perf_1m = (current - price_1m_ago) / price_1m_ago * 100.0
    perf_6m = (current - price_6m_ago) / price_6m_ago * 100.0

    return perf_1m, perf_6m


def _score_1m_perf(perf_pct: float) -> int:
    """Map 1-month performance to a 0-10 point sub-score."""
    if perf_pct >= 10.0:
        return 10
    if perf_pct >= 5.0:
        return 8
    if perf_pct >= 0.0:
        return 5
    if perf_pct >= -5.0:
        return 2
    return 0


def _score_6m_perf(perf_pct: float) -> int:
    """Map 6-month performance to a 0-10 point sub-score."""
    if perf_pct >= 20.0:
        return 10
    if perf_pct >= 10.0:
        return 8
    if perf_pct >= 0.0:
        return 5
    if perf_pct >= -10.0:
        return 2
    return 0


def _compute_sector_score(ticker_perf_3m: float, sector_perf_3m: float) -> int:
    """Score relative 3-month outperformance vs sector ETF (0-20 pts).

    Relative = ticker_perf_3m - sector_perf_3m

    > +5%  → 20 pts  (strong outperformance)
    0-5%   → 15 pts  (mild outperformance)
    within ±2% → 10 pts (in-line)
    -5-0%  → 5 pts   (mild underperformance)
    < -5%  → 0 pts   (significant underperformance)
    """
    relative = ticker_perf_3m - sector_perf_3m
    if relative > 5.0:
        return 20
    if relative > 0.0:
        return 15
    if relative >= -2.0:
        return 10
    if relative >= -5.0:
        return 5
    return 0


def _compute_f1_score(
    rsi_score: int,
    macd_score: int,
    ma_score: int,
    week52_score: int,
    perf_score: int,
    sector_score: int,
) -> tuple[int, str]:
    """Aggregate sub-scores into the 0-100 F1 composite and assign a grade.

    Total is hard-capped at 100 even if inputs sum above it.
    """
    total = min(100, rsi_score + macd_score + ma_score + week52_score + perf_score + sector_score)
    grade = _grade_from_total(total)
    return total, grade


def _grade_from_total(total: int) -> str:
    """Convert a numeric F1 total to a human-readable grade string."""
    if total >= _GRADE_STRONG_BUY_MIN:
        return F1Grade.STRONG_BUY
    if total >= _GRADE_BUY_MIN:
        return F1Grade.BUY
    if total >= _GRADE_NEUTRAL_MIN:
        return F1Grade.NEUTRAL
    if total >= _GRADE_WEAK_MIN:
        return F1Grade.WEAK
    return F1Grade.AVOID


def _resolve_sector_etf(industry_description: str) -> str:
    """Return the best-matching sector ETF for a Polygon industry description."""
    lower = industry_description.lower()
    for keyword, etf in _SECTOR_ETF_MAP.items():
        if keyword in lower:
            return etf
    return _DEFAULT_SECTOR_ETF


# ---------------------------------------------------------------------------
# Network-dependent service
# ---------------------------------------------------------------------------


class MomentumService:
    """Fetches historical bars from Polygon and computes the F1 Momentum score."""

    def __init__(self, api_key: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._client = client

    async def compute_momentum(self, ticker: str) -> MomentumResponse:
        """Compute all momentum indicators and the F1 score for ``ticker``.

        1. Resolve the ticker's sector ETF via Polygon reference endpoint.
        2. Fetch one year of daily bars for the ticker and the sector ETF
           concurrently.
        3. Compute each pure-function indicator, score it, and assemble the
           response.
        """
        to_date = date.today()
        from_date = to_date - timedelta(days=_LOOKBACK_DAYS)

        # Resolve sector ETF and bars concurrently.
        sector_etf, ticker_bars = await asyncio.gather(
            self._resolve_sector_etf_for(ticker),
            self._fetch_bars(ticker, from_date, to_date),
        )
        sector_bars = await self._fetch_bars(sector_etf, from_date, to_date)

        # ---- RSI ----
        rsi_value = _compute_rsi(ticker_bars)
        rsi_score = _score_rsi(rsi_value) if rsi_value is not None else 0

        # ---- MACD ----
        macd_result = _compute_macd(ticker_bars)
        if macd_result is not None:
            macd_val, macd_signal, macd_hist = macd_result
            macd_score = _score_macd(macd_val, macd_signal, macd_hist)
        else:
            macd_val = macd_signal = macd_hist = 0.0
            macd_score = 0

        # ---- MA alignment ----
        ma_result = _compute_ma_alignment(ticker_bars)
        if ma_result is not None:
            ma20, ma50, ma200, ma_label = ma_result
            ma_score = _score_ma_alignment(ma_label)
        else:
            ma20 = ma50 = ma200 = 0.0
            ma_label = "INSUFFICIENT_DATA"
            ma_score = 0

        # ---- 52-week position ----
        w52_result = _compute_52w_position(ticker_bars)
        if w52_result is not None:
            high52, low52, pos52 = w52_result
            week52_score = _score_52w_position(pos52)
        else:
            high52 = low52 = pos52 = 0.0
            week52_score = 0

        # ---- 1M / 6M performance ----
        perf_result = _compute_performance(ticker_bars)
        if perf_result is not None:
            perf_1m, perf_6m = perf_result
            score_1m = _score_1m_perf(perf_1m)
            score_6m = _score_6m_perf(perf_6m)
        else:
            perf_1m = perf_6m = 0.0
            score_1m = score_6m = 0
        perf_score = score_1m + score_6m

        # ---- Sector momentum ----
        ticker_3m = self._perf_3m(ticker_bars)
        sector_3m = self._perf_3m(sector_bars)
        sector_score = _compute_sector_score(ticker_3m, sector_3m)

        # ---- F1 composite ----
        f1_total, f1_grade = _compute_f1_score(
            rsi_score=rsi_score,
            macd_score=macd_score,
            ma_score=ma_score,
            week52_score=week52_score,
            perf_score=perf_score,
            sector_score=sector_score,
        )

        return MomentumResponse(
            ticker=ticker.upper(),
            sector_etf=sector_etf,
            rsi=RsiIndicator(
                value=round(rsi_value, 2) if rsi_value is not None else None,
                score=rsi_score,
                max_score=20,
            ),
            macd=MacdIndicator(
                macd_line=round(macd_val, 4),
                signal_line=round(macd_signal, 4),
                histogram=round(macd_hist, 4),
                score=macd_score,
                max_score=20,
            ),
            ma_alignment=MaAlignmentIndicator(
                ma_20=round(ma20, 2),
                ma_50=round(ma50, 2),
                ma_200=round(ma200, 2),
                label=ma_label,
                score=ma_score,
                max_score=20,
            ),
            week_52_position=Week52PositionIndicator(
                high_52w=round(high52, 2),
                low_52w=round(low52, 2),
                position_pct=round(pos52, 1),
                score=week52_score,
                max_score=20,
            ),
            performance=PerformanceIndicator(
                perf_1m=round(perf_1m, 2),
                perf_6m=round(perf_6m, 2),
                score_1m=score_1m,
                score_6m=score_6m,
                score=perf_score,
                max_score=20,
            ),
            sector_momentum=SectorMomentumIndicator(
                sector_etf=sector_etf,
                ticker_perf_3m=round(ticker_3m, 2),
                sector_perf_3m=round(sector_3m, 2),
                relative_perf_3m=round(ticker_3m - sector_3m, 2),
                score=sector_score,
                max_score=20,
            ),
            f1_score=f1_total,
            f1_grade=f1_grade,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_sector_etf_for(self, ticker: str) -> str:
        """Return the sector ETF symbol for ``ticker`` via Polygon reference.

        Falls back to SPY when the ticker cannot be resolved.
        """
        url = _POLYGON_TICKER_DETAILS_URL.format(ticker=ticker)
        try:
            response = await self._client.get(
                url,
                params={"apiKey": self._api_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: dict = response.json()  # type: ignore[type-arg]
            results: dict = payload.get("results", {})  # type: ignore[type-arg]
            industry: str = (
                results.get("sic_description")
                or results.get("description")
                or ""
            )
            return _resolve_sector_etf(industry)
        except (httpx.HTTPStatusError, httpx.RequestError):
            return _DEFAULT_SECTOR_ETF

    async def _fetch_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict]:  # type: ignore[type-arg]
        """Return ascending daily OHLCV bar dicts from Polygon.

        Returns an empty list on any HTTP error.
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
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []

        payload: dict = response.json()  # type: ignore[type-arg]
        results: list[dict] = payload.get("results", [])  # type: ignore[type-arg]
        return results

    @staticmethod
    def _perf_3m(bars: list[dict]) -> float:  # type: ignore[type-arg]
        """Return 3-month (63-bar) total return as a percentage.

        Returns 0.0 when insufficient bars are available.
        """
        closes = [float(b["c"]) for b in bars if b.get("c") is not None]
        if len(closes) < _LOOKBACK_3M_BARS + 1:
            return 0.0
        price_now = closes[-1]
        price_then = closes[-(_LOOKBACK_3M_BARS + 1)]
        if price_then == 0:
            return 0.0
        return (price_now - price_then) / price_then * 100.0
