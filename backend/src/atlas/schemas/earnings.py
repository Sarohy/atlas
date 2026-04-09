"""Pydantic schemas for the F2 Earnings Quality endpoint."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# F2 grade literals
# ---------------------------------------------------------------------------


class F2Grade:
    """Named constants for the five F2 earnings-quality grades."""

    STRONG_BUY: Final[str] = "STRONG BUY"
    BUY: Final[str] = "BUY"
    NEUTRAL: Final[str] = "NEUTRAL"
    WEAK: Final[str] = "WEAK"
    AVOID: Final[str] = "AVOID"


# ---------------------------------------------------------------------------
# Sub-indicator schemas
# ---------------------------------------------------------------------------


class RevenueGrowthIndicator(BaseModel):
    """Year-over-year TTM revenue growth and its contribution to the F2 score."""

    model_config = ConfigDict(from_attributes=True)

    current_ttm: float | None = Field(
        None, description="Trailing twelve-month revenue (most recent, USD millions)."
    )
    prior_ttm: float | None = Field(
        None, description="Trailing twelve-month revenue (one year prior, USD millions)."
    )
    growth_pct: float | None = Field(
        None, description="YoY TTM revenue growth (%). Null when prior TTM is unavailable."
    )
    score: int = Field(ge=0, le=20, description="F2 score contribution (0-20).")
    max_score: int = Field(default=20)


class EpsBeatsIndicator(BaseModel):
    """EPS-vs-consensus beat rate over the last 4 reported quarters."""

    model_config = ConfigDict(from_attributes=True)

    beat_rate_pct: float | None = Field(
        None,
        description="Percentage of the last 4 quarters where EPS beat consensus (0-100). "
        "Null when earnings data is unavailable.",
    )
    quarters_beat: int | None = Field(
        None, description="Number of quarters (out of 4) where actual EPS beat estimate."
    )
    score: int = Field(ge=0, le=20, description="F2 score contribution (0-20).")
    max_score: int = Field(default=20)


class GuidanceIndicator(BaseModel):
    """Management guidance quality derived from EPS estimate revision trend."""

    model_config = ConfigDict(from_attributes=True)

    revision_direction: int = Field(
        description=(
            "Net revision direction: +2 strongly raised, +1 raised, 0 flat, "
            "-1 cut, -2 strongly cut."
        )
    )
    revision_pct: float | None = Field(
        None,
        description="Percentage change in consensus EPS estimate over the last 4 revisions. "
        "Null when revision data is unavailable.",
    )
    score: int = Field(ge=0, le=20, description="F2 score contribution (0-20).")
    max_score: int = Field(default=20)


class BacklogBtbIndicator(BaseModel):
    """Book-to-bill proxy derived from revenue-growth vs gross-margin stability.

    A true book-to-bill ratio requires segment-level order data that is rarely
    available via public APIs.  ATLAS approximates it by comparing the last
    two consecutive quarters of revenue growth rate: if revenue acceleration
    is positive *and* gross margin is stable-or-improving, we infer backlog
    expansion (BTB > 1).
    """

    model_config = ConfigDict(from_attributes=True)

    btb_proxy: float | None = Field(
        None,
        description=(
            "Book-to-bill proxy: positive = orders accelerating relative to revenue, "
            "negative = decelerating.  Null when insufficient quarterly data."
        ),
    )
    revenue_acceleration: float | None = Field(
        None,
        description="Change in QoQ revenue growth rate (latest quarter minus prior quarter, ppts).",
    )
    score: int = Field(ge=0, le=20, description="F2 score contribution (0-20).")
    max_score: int = Field(default=20)


class MarginTrajectoryIndicator(BaseModel):
    """Gross-margin direction over the last four reported quarters."""

    model_config = ConfigDict(from_attributes=True)

    gross_margins: list[float] = Field(
        description="Gross margin (%) for each of the last 4 quarters (oldest first)."
    )
    trajectory: float | None = Field(
        None,
        description=(
            "Average quarter-over-quarter change in gross margin (ppts). "
            "Positive = expanding, negative = contracting."
        ),
    )
    score: int = Field(ge=0, le=20, description="F2 score contribution (0-20).")
    max_score: int = Field(default=20)


# ---------------------------------------------------------------------------
# Top-level response schema
# ---------------------------------------------------------------------------


class EarningsResponse(BaseModel):
    """Complete F2 Earnings Quality analysis for a single ticker."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    revenue_growth: RevenueGrowthIndicator
    eps_beats: EpsBeatsIndicator
    guidance: GuidanceIndicator
    backlog_btb: BacklogBtbIndicator
    margin_trajectory: MarginTrajectoryIndicator
    f2_score: int = Field(ge=0, le=100, description="Composite F2 Earnings Quality score (0-100).")
    f2_grade: str = Field(
        description="F2 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID"
    )
