"""F1 Momentum scoring service.

Computes seven momentum inputs, scores each 0-100, applies the internal F1
weights defined in the Factor_Mapping_Guide, and produces a 0-100 composite
F1 score.

All calculation helpers are pure functions (no I/O, no side-effects) so they
can be tested in isolation without any network calls.  The ``MomentumService``
class owns all Polygon API access and calls the pure helpers once the raw bar
data has been fetched.

F1 internal weights (from Factor_Mapping_Guide):
  RSI (14-day)       20%   → max  20.0 pts contribution
  MACD Signal        15%   → max  15.0 pts contribution
  Price vs MAs       20%   → max  20.0 pts contribution
  52-Week Position   15%   → max  15.0 pts contribution
  1-Month Return     15%   → max  15.0 pts contribution
  6-Month Return     10%   → max  10.0 pts contribution
  vs Sector (6M)      5%   → max   5.0 pts contribution
  TOTAL             100%   → max 100.0 pts
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

# Calendar days to request from Polygon for 52-week range and indicators.
# 380 days ≈ 265 trading sessions — guarantees ≥ 252 bars even accounting
# for US market holidays, leap years, and same-day settlement gaps.
_LOOKBACK_DAYS: Final[int] = 380

# Max concurrent Polygon requests within the service.
_MAX_CONCURRENCY: Final[int] = 5

# F1 internal weights (Factor_Mapping_Guide §F1).
# Each input is scored 0-100; multiplied by its weight to get the contribution.
_W_RSI: Final[float] = 0.20        # 20% — RSI (14-day)
_W_MACD: Final[float] = 0.15       # 15% — MACD signal
_W_MA: Final[float] = 0.20         # 20% — Price vs MAs
_W_52W: Final[float] = 0.15        # 15% — 52-week position
_W_1M: Final[float] = 0.15         # 15% — 1-month return
_W_6M: Final[float] = 0.10         # 10% — 6-month return
_W_SECTOR: Final[float] = 0.05     # 5%  — vs sector (6-month)

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

# Parabolic trend-leader relief.
# When trend stack is fully maxed (MA/52W/1M/6M/sector) and RSI remains at
# least in the healthy band, MACD lag should not drag F1 below high-conviction
# territory. This captures names that cool from extreme momentum while price
# structure stays decisively bullish.
_F1_PARABOLIC_FLOOR: Final[int] = 95
_F1_PARABOLIC_MIN_RSI_RAW: Final[int] = 70
_F1_PARABOLIC_MAX_TREND_RAW: Final[int] = 100


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
    """Map RSI value to a raw 0-100 input score (Factor_Mapping_Guide §F1).

    Scoring bands:
      >= 90  → 100 pts  (extremely overbought — still strong signal)
      70-89  → 85 pts   (overbought / strong momentum)
      55-69  → 70 pts   (healthy momentum zone)
      45-54  → 55 pts   (neutral)
      35-44  → 40 pts   (weak / below midline)
      < 35   → 20 pts   (oversold / bearish)
    """
    if rsi >= 90.0:
        return 100
    if rsi >= 70.0:
        return 85
    if rsi >= 55.0:
        return 70
    if rsi >= 45.0:
        return 55
    if rsi >= 35.0:
        return 40
    return 20


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


def _score_macd(
    macd: float,
    signal: float,
    histogram: float,
    prev_histogram: float | None = None,
) -> int:
    """Map MACD state to a raw 0-100 input score (Factor_Mapping_Guide §F1).

    Scoring bands:
      MACD > Signal AND rising histogram → 100 pts  (bull expansion)
      MACD > Signal AND flat histogram   → 75 pts   (bull crossover, momentum plateauing)
      MACD < Signal AND histogram rising → 50 pts   (bearish but recovering)
      MACD < Signal AND falling          → 20 pts   (bearish decline)

    'Rising' is detected by comparing ``histogram`` to ``prev_histogram``.
    When ``prev_histogram`` is None (unavailable) the histogram sign is used
    as a proxy: positive hist = rising, negative = falling.
    """
    above_signal = macd > signal
    hist_rising = histogram > prev_histogram if prev_histogram is not None else histogram > 0

    if above_signal and hist_rising:
        return 100
    if above_signal:
        return 75
    if hist_rising:  # below signal but recovering
        return 50
    return 20


def _compute_ma_alignment(
    bars: list[dict],  # type: ignore[type-arg]
) -> tuple[float, float, float, str] | None:
    """Compute MA-20, MA-50, MA-200 and the alignment label.

    Returns ``(ma20, ma50, ma200, label)`` or None when < 200 bars exist.

    Labels follow the Factor_Mapping_Guide §F1 four-tier rule:
      ABOVE_ALL   price > MA20, MA50, MA200 (all three) → 100 pts
      ABOVE_50_200  price above MA50 and MA200 only      → 80 pts
      ABOVE_200   price above MA200 only                 → 55 pts
      BELOW_ALL   price below all MAs                    → 20 pts
    """
    closes = [float(b["c"]) for b in bars if b.get("c") is not None]
    if len(closes) < 200:
        return None

    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    ma200 = sum(closes[-200:]) / 200
    current = closes[-1]

    if current > ma20 and current > ma50 and current > ma200:
        label = "ABOVE_ALL"
    elif current > ma50 and current > ma200:
        label = "ABOVE_50_200"
    elif current > ma200:
        label = "ABOVE_200"
    else:
        label = "BELOW_ALL"

    return ma20, ma50, ma200, label


def _score_ma_alignment(label: str) -> int:
    """Map MA alignment label to a raw 0-100 input score (Factor_Mapping_Guide §F1).

    Bands:
      ABOVE_ALL     → 100 pts  (above MA20, MA50, MA200)
      ABOVE_50_200  → 80 pts   (above MA50 and MA200)
      ABOVE_200     → 55 pts   (above MA200 only)
      BELOW_ALL     → 20 pts   (below all MAs)
    """
    return {
        "ABOVE_ALL": 100,
        "ABOVE_50_200": 80,
        "ABOVE_200": 55,
        "BELOW_ALL": 20,
    }.get(label, 20)


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
    """Map 52-week position percentage to a raw 0-100 input score (Factor_Mapping_Guide §F1).

    Bands:
      > 80%   → 100 pts  (near 52-week high)
      60-80%  → 80 pts   (upper range)
      40-60%  → 60 pts   (mid-range)
      20-40%  → 40 pts   (lower range)
      < 20%   → 20 pts   (near 52-week low)
    """
    if position_pct > 80.0:
        return 100
    if position_pct >= 60.0:
        return 80
    if position_pct >= 40.0:
        return 60
    if position_pct >= 20.0:
        return 40
    return 20


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
    """Map 1-month return to a raw 0-100 input score (Factor_Mapping_Guide §F1).

    Bands:
      > +10%         → 100 pts
      +5% to +10%    → 85 pts
      +2% to +5%     → 70 pts
      0% to +2%      → 55 pts
      -2% to 0%      → 40 pts
      < -5%          → 20 pts  (also covers -5% to -2% conservatively)
    """
    if perf_pct > 10.0:
        return 100
    if perf_pct >= 5.0:
        return 85
    if perf_pct >= 2.0:
        return 70
    if perf_pct >= 0.0:
        return 55
    if perf_pct >= -2.0:
        return 40
    return 20


def _score_6m_perf(perf_pct: float) -> int:
    """Map 6-month return to a raw 0-100 input score (Factor_Mapping_Guide §F1).

    Bands:
      > +40%         → 100 pts
      +25% to +40%   → 85 pts
      +15% to +25%   → 70 pts
      +5% to +15%    → 55 pts
      0% to +5%      → 40 pts
      < 0%           → 20 pts
    """
    if perf_pct > 40.0:
        return 100
    if perf_pct >= 25.0:
        return 85
    if perf_pct >= 15.0:
        return 70
    if perf_pct >= 5.0:
        return 55
    if perf_pct >= 0.0:
        return 40
    return 20


def _compute_sector_score(ticker_perf_6m: float, sector_perf_6m: float) -> int:
    """Score 6-month outperformance vs sector ETF as raw 0-100 input score.

    Uses the 6-month (126-day) rolling return window per the Factor_Mapping_Guide
    §F1 SOXX Sector Comparison rules.

    Relative = ticker_perf_6m - sector_perf_6m

    > +5%   → 100 pts  (strong outperformance)
    0-+5%   → 75 pts   (mild outperformance)
    ~0%     → 60 pts   (in-line — also used as fallback when sector data unavailable)
    < 0%    → 30 pts   (underperformance)
    """
    relative = ticker_perf_6m - sector_perf_6m
    if relative > 5.0:
        return 100
    if relative > 0.0:
        return 75
    if relative >= -1.0:  # within ±1 % = effectively in-line
        return 60
    return 30


def _compute_f1_score(
    rsi_raw: int,
    macd_raw: int,
    ma_raw: int,
    week52_raw: int,
    perf_1m_raw: int,
    perf_6m_raw: int,
    sector_raw: int,
) -> tuple[int, str]:
    """Apply guide weights to raw 0-100 input scores and return (total, grade).

    Each raw score is 0-100; weighted by the Factor_Mapping_Guide §F1 percentages:
      RSI 20% + MACD 15% + MAs 20% + 52W 15% + 1M 15% + 6M 10% + Sector 5% = 100%

    Total is rounded to nearest integer and hard-capped at 100.
    """
    weighted = (
        rsi_raw * _W_RSI
        + macd_raw * _W_MACD
        + ma_raw * _W_MA
        + week52_raw * _W_52W
        + perf_1m_raw * _W_1M
        + perf_6m_raw * _W_6M
        + sector_raw * _W_SECTOR
    )

    # Parabolic leader floor: preserve high momentum score when trend structure
    # is unanimously strong and RSI confirms strength, even if MACD lags.
    if (
        ma_raw == _F1_PARABOLIC_MAX_TREND_RAW
        and week52_raw == _F1_PARABOLIC_MAX_TREND_RAW
        and perf_1m_raw == _F1_PARABOLIC_MAX_TREND_RAW
        and perf_6m_raw == _F1_PARABOLIC_MAX_TREND_RAW
        and sector_raw == _F1_PARABOLIC_MAX_TREND_RAW
        and rsi_raw >= _F1_PARABOLIC_MIN_RSI_RAW
    ):
        weighted = max(weighted, float(_F1_PARABOLIC_FLOOR))

    total = min(100, round(weighted))
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
        rsi_raw = _score_rsi(rsi_value) if rsi_value is not None else 55  # neutral fallback

        # ---- MACD ----
        # Compute twice (full series and series-minus-one) to get prev histogram for
        # 'rising vs flat' detection per the Factor_Mapping_Guide.
        macd_result = _compute_macd(ticker_bars)
        macd_result_prev = _compute_macd(ticker_bars[:-1]) if len(ticker_bars) > 1 else None
        if macd_result is not None:
            macd_val, macd_signal, macd_hist = macd_result
            prev_hist = macd_result_prev[2] if macd_result_prev is not None else None
            macd_raw = _score_macd(macd_val, macd_signal, macd_hist, prev_hist)
        else:
            macd_val = macd_signal = macd_hist = 0.0
            macd_raw = 50  # neutral fallback

        # ---- MA alignment ----
        ma_result = _compute_ma_alignment(ticker_bars)
        if ma_result is not None:
            ma20, ma50, ma200, ma_label = ma_result
            ma_raw = _score_ma_alignment(ma_label)
        else:
            ma20 = ma50 = ma200 = 0.0
            ma_label = "INSUFFICIENT_DATA"
            ma_raw = 55  # neutral fallback

        # ---- 52-week position ----
        w52_result = _compute_52w_position(ticker_bars)
        if w52_result is not None:
            high52, low52, pos52 = w52_result
            week52_raw = _score_52w_position(pos52)
        else:
            high52 = low52 = pos52 = 0.0
            week52_raw = 40  # conservative fallback

        # ---- 1M / 6M performance ----
        perf_result = _compute_performance(ticker_bars)
        if perf_result is not None:
            perf_1m, perf_6m = perf_result
            perf_1m_raw = _score_1m_perf(perf_1m)
            perf_6m_raw = _score_6m_perf(perf_6m)
        else:
            perf_1m = perf_6m = 0.0
            perf_1m_raw = perf_6m_raw = 40  # conservative fallback

        # ---- Sector momentum (6-month per guide) ----
        ticker_6m = self._perf_6m(ticker_bars)
        sector_6m = self._perf_6m(sector_bars)
        sector_raw = _compute_sector_score(ticker_6m, sector_6m)

        # ---- F1 composite ----
        f1_total, f1_grade = _compute_f1_score(
            rsi_raw=rsi_raw,
            macd_raw=macd_raw,
            ma_raw=ma_raw,
            week52_raw=week52_raw,
            perf_1m_raw=perf_1m_raw,
            perf_6m_raw=perf_6m_raw,
            sector_raw=sector_raw,
        )

        # Weighted contribution scores for display (raw x weight = pts contributed)
        rsi_contrib = round(rsi_raw * _W_RSI)
        macd_contrib = round(macd_raw * _W_MACD)
        ma_contrib = round(ma_raw * _W_MA)
        week52_contrib = round(week52_raw * _W_52W)
        perf_1m_contrib = round(perf_1m_raw * _W_1M)
        perf_6m_contrib = round(perf_6m_raw * _W_6M)
        sector_contrib = round(sector_raw * _W_SECTOR)

        return MomentumResponse(
            ticker=ticker.upper(),
            sector_etf=sector_etf,
            rsi=RsiIndicator(
                value=round(rsi_value, 2) if rsi_value is not None else None,
                raw_score=rsi_raw,
                score=rsi_contrib,
                max_score=round(_W_RSI * 100),
            ),
            macd=MacdIndicator(
                macd_line=round(macd_val, 4),
                signal_line=round(macd_signal, 4),
                histogram=round(macd_hist, 4),
                raw_score=macd_raw,
                score=macd_contrib,
                max_score=round(_W_MACD * 100),
            ),
            ma_alignment=MaAlignmentIndicator(
                ma_20=round(ma20, 2),
                ma_50=round(ma50, 2),
                ma_200=round(ma200, 2),
                label=ma_label,
                raw_score=ma_raw,
                score=ma_contrib,
                max_score=round(_W_MA * 100),
            ),
            week_52_position=Week52PositionIndicator(
                high_52w=round(high52, 2),
                low_52w=round(low52, 2),
                position_pct=round(pos52, 1),
                raw_score=week52_raw,
                score=week52_contrib,
                max_score=round(_W_52W * 100),
            ),
            performance=PerformanceIndicator(
                perf_1m=round(perf_1m, 2),
                perf_6m=round(perf_6m, 2),
                raw_score_1m=perf_1m_raw,
                raw_score_6m=perf_6m_raw,
                score_1m=perf_1m_contrib,
                score_6m=perf_6m_contrib,
                score=perf_1m_contrib + perf_6m_contrib,
                max_score=round((_W_1M + _W_6M) * 100),
            ),
            sector_momentum=SectorMomentumIndicator(
                sector_etf=sector_etf,
                ticker_perf_6m=round(ticker_6m, 2),
                sector_perf_6m=round(sector_6m, 2),
                relative_perf_6m=round(ticker_6m - sector_6m, 2),
                raw_score=sector_raw,
                score=sector_contrib,
                max_score=round(_W_SECTOR * 100),
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
    def _perf_6m(bars: list[dict]) -> float:  # type: ignore[type-arg]
        """Return 6-month (126-bar) total return as a percentage.

        The Factor_Mapping_Guide uses a rolling 126-day (6-month) window for
        the sector comparison input.  Returns 0.0 when insufficient bars are
        available (triggers the neutral 60-pt fallback in the caller).
        """
        closes = [float(b["c"]) for b in bars if b.get("c") is not None]
        if len(closes) < _LOOKBACK_6M_BARS + 1:
            return 0.0
        price_now = closes[-1]
        price_then = closes[-(_LOOKBACK_6M_BARS + 1)]
        if price_then == 0:
            return 0.0
        return (price_now - price_then) / price_then * 100.0
