"""Pydantic schemas for the F1 Momentum endpoint."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# F1 grade literals
# ---------------------------------------------------------------------------


class F1Grade:
    """Named constants for the five F1 momentum grades."""

    STRONG_BUY: Final[str] = "STRONG BUY"
    BUY: Final[str] = "BUY"
    NEUTRAL: Final[str] = "NEUTRAL"
    WEAK: Final[str] = "WEAK"
    AVOID: Final[str] = "AVOID"


# ---------------------------------------------------------------------------
# Sub-indicator schemas
# ---------------------------------------------------------------------------


class RsiIndicator(BaseModel):
    """RSI (14-period Wilder) result and its contribution to the F1 score."""

    model_config = ConfigDict(from_attributes=True)

    value: float | None = Field(
        None, description="RSI value in [0, 100]; null when insufficient data."
    )
    raw_score: int = Field(
        ge=0, le=100, description="RSI raw score (0-100) before weight is applied."
    )
    score: int = Field(
        ge=0, le=20, description="Weighted contribution to F1 (raw_score x 0.20, 0-20)."
    )
    max_score: int = Field(
        default=20, description="Maximum contribution this indicator can add to F1."
    )


class MacdIndicator(BaseModel):
    """MACD (12/26/9) result and its contribution to the F1 score."""

    model_config = ConfigDict(from_attributes=True)

    macd_line: float = Field(description="MACD line value (fast EMA - slow EMA).")
    signal_line: float = Field(description="Signal line (9-period EMA of MACD).")
    histogram: float = Field(description="MACD histogram (macd_line - signal_line).")
    raw_score: int = Field(
        ge=0, le=100, description="MACD raw score (0-100) before weight is applied."
    )
    score: int = Field(
        ge=0, le=15, description="Weighted contribution to F1 (raw_score x 0.15, 0-15)."
    )
    max_score: int = Field(default=15)


class MaAlignmentIndicator(BaseModel):
    """20/50/200-day MA alignment result and its contribution to the F1 score."""

    model_config = ConfigDict(from_attributes=True)

    ma_20: float = Field(description="20-day simple moving average.")
    ma_50: float = Field(description="50-day simple moving average.")
    ma_200: float = Field(description="200-day simple moving average.")
    label: str = Field(
        description=(
            "Alignment label: ABOVE_ALL | ABOVE_50_200 | ABOVE_200 | BELOW_ALL | INSUFFICIENT_DATA"
        )
    )
    raw_score: int = Field(
        ge=0, le=100, description="MA alignment raw score (0-100) before weight is applied."
    )
    score: int = Field(
        ge=0, le=20, description="Weighted contribution to F1 (raw_score x 0.20, 0-20)."
    )
    max_score: int = Field(default=20)


class Week52PositionIndicator(BaseModel):
    """52-week high/low position result and its contribution to the F1 score."""

    model_config = ConfigDict(from_attributes=True)

    high_52w: float = Field(description="52-week closing high.")
    low_52w: float = Field(description="52-week closing low.")
    position_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Where the current price sits in the 52-week range (0=low, 100=high).",
    )
    raw_score: int = Field(
        ge=0, le=100, description="52-week raw score (0-100) before weight is applied."
    )
    score: int = Field(
        ge=0, le=15, description="Weighted contribution to F1 (raw_score x 0.15, 0-15)."
    )
    max_score: int = Field(default=15)


class PerformanceIndicator(BaseModel):
    """1-month and 6-month price performance and their combined contribution."""

    model_config = ConfigDict(from_attributes=True)

    perf_1m: float = Field(description="1-month (21-session) total return (%).")
    perf_6m: float = Field(description="6-month (126-session) total return (%).")
    raw_score_1m: int = Field(
        ge=0, le=100, description="1-month raw score (0-100) before weight is applied."
    )
    raw_score_6m: int = Field(
        ge=0, le=100, description="6-month raw score (0-100) before weight is applied."
    )
    score_1m: int = Field(
        ge=0, le=15, description="1-month weighted contribution (raw x 0.15, 0-15)."
    )
    score_6m: int = Field(
        ge=0, le=10, description="6-month weighted contribution (raw x 0.10, 0-10)."
    )
    score: int = Field(
        ge=0, le=25, description="Combined performance contribution (score_1m + score_6m, 0-25)."
    )
    max_score: int = Field(default=25)


class SectorMomentumIndicator(BaseModel):
    """Sector relative performance result and its contribution to the F1 score."""

    model_config = ConfigDict(from_attributes=True)

    sector_etf: str = Field(description="SPDR sector ETF used as the benchmark (e.g. XLK).")
    ticker_perf_6m: float = Field(description="Ticker 6-month total return (%).")
    sector_perf_6m: float = Field(description="Sector ETF 6-month total return (%).")
    relative_perf_6m: float = Field(description="Ticker minus sector 6-month return (%).")
    raw_score: int = Field(
        ge=0, le=100, description="Sector raw score (0-100) before weight is applied."
    )
    score: int = Field(
        ge=0, le=5, description="Weighted contribution to F1 (raw_score x 0.05, 0-5)."
    )
    max_score: int = Field(default=5)


# ---------------------------------------------------------------------------
# Top-level response schema
# ---------------------------------------------------------------------------


class MomentumResponse(BaseModel):
    """Complete F1 Momentum analysis for a single ticker."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    sector_etf: str = Field(description="Sector ETF used for relative momentum.")
    rsi: RsiIndicator
    macd: MacdIndicator
    ma_alignment: MaAlignmentIndicator
    week_52_position: Week52PositionIndicator
    performance: PerformanceIndicator
    sector_momentum: SectorMomentumIndicator
    f1_score: int = Field(ge=0, le=100, description="Composite F1 Momentum score (0-100).")
    f1_grade: str = Field(
        description="F1 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID"
    )
