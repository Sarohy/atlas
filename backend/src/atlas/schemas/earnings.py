"""Pydantic schemas for the F2 Earnings Quality endpoint.

Schema field names mirror the Factor_Mapping_Guide §F2 rework:
  - All indicators carry ``raw_score`` (0-100 pre-weight) and ``score`` (weighted contribution).
  - ``GuidanceIndicator`` uses a categorical ``guidance_label`` string.
  - ``BacklogBtbIndicator`` uses a categorical ``backlog_label`` string.
  - ``MarginTrajectoryIndicator`` exposes ``margin_change_pts`` in percentage points.
  - Max-score values reflect the new internal weights (30/20/20/15/15).
"""

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
    """Year-over-year revenue growth and its contribution to the F2 score.

    Weight: 30%  →  max 30 pts contribution.
    """

    model_config = ConfigDict(from_attributes=True)

    yoy_pct: float | None = Field(
        None,
        description="YoY quarterly revenue growth (%). Null when data is unavailable.",
    )
    raw_score: int | None = Field(
        None, ge=0, le=100, description="Raw 0-100 score before weighting. Null when AV data is unavailable."
    )
    score: int | None = Field(None, ge=0, le=30, description="Weighted F2 contribution (0-30). Null when excluded via weight rescaling.")
    max_score: int = Field(default=30)


class EpsBeatsIndicator(BaseModel):
    """EPS-vs-consensus beat count over the last 3 reported quarters.

    Weight: 20%  →  max 20 pts contribution.
    """

    model_config = ConfigDict(from_attributes=True)

    beats_in_3: int | None = Field(
        None,
        description="Number of the last 3 quarters where reported EPS beat estimated EPS (0-3).",
    )
    quarters_checked: int | None = Field(
        None,
        description="How many of the last 3 quarters had sufficient EPS data.",
    )
    raw_score: int = Field(
        ge=0, le=100, description="Raw 0-100 score before weighting."
    )
    score: int = Field(ge=0, le=20, description="Weighted F2 contribution (0-20).")
    max_score: int = Field(default=20)


class GuidanceIndicator(BaseModel):
    """Management guidance direction derived from the earnings-call transcript.

    Weight: 20%  →  max 20 pts contribution.
    raw_score and score are None when guidance_label is UNDETECTED (no pattern
    matched the transcript); the sub-factor is excluded from the F2 composite
    and remaining weights are rescaled proportionally.
    """

    model_config = ConfigDict(from_attributes=True)

    guidance_label: str = Field(
        description=(
            "Guidance classification: RAISE_FULL_YEAR | MAINTAIN | NARROW_RANGE | LOWER | UNDETECTED"
        )
    )
    transcript_quarter: str | None = Field(
        None,
        description="Fiscal quarter of the transcript used (e.g. '2024Q3').",
    )
    raw_score: int | None = Field(
        default=None, ge=0, le=100, description="Raw 0-100 score before weighting. None when UNDETECTED."
    )
    score: int | None = Field(default=None, ge=0, le=20, description="Weighted F2 contribution (0-20). None when UNDETECTED.")
    max_score: int = Field(default=20)


class BacklogBtbIndicator(BaseModel):
    """Backlog / forward visibility derived from the earnings-call transcript.

    Weight: 15%  →  max 15 pts contribution.
    """

    model_config = ConfigDict(from_attributes=True)

    backlog_label: str = Field(
        description=(
            "Backlog classification: EXPLICIT_MULTI_QUARTER | STRONG | LIMITED | NO_COMMENTARY"
        )
    )
    raw_score: int = Field(
        ge=0, le=100, description="Raw 0-100 score before weighting."
    )
    score: int = Field(ge=0, le=15, description="Weighted F2 contribution (0-15).")
    max_score: int = Field(default=15)


class MarginTrajectoryIndicator(BaseModel):
    """Gross-margin trend derived from the last 3 reported quarterly income statements.

    Weight: 15%  →  max 15 pts contribution.
    """

    model_config = ConfigDict(from_attributes=True)

    gross_margins: list[float] = Field(
        default_factory=list,
        description="Gross-margin (%) values for the last 3 quarters (oldest first).",
    )
    margin_change_pts: float | None = Field(
        None,
        description=(
            "Gross-margin change in percentage points (most recent minus oldest in window). "
            "Positive = expanding, negative = contracting. Null when insufficient data."
        ),
    )
    raw_score: int = Field(
        ge=0, le=100, description="Raw 0-100 score before weighting."
    )
    score: int = Field(ge=0, le=15, description="Weighted F2 contribution (0-15).")
    max_score: int = Field(default=15)


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
    margin_trajectory: MarginTrajectoryIndicator
    backlog_btb: BacklogBtbIndicator
    f2_score: int = Field(ge=0, le=100, description="Composite F2 Earnings Quality score (0-100).")
    f2_grade: str = Field(
        description="F2 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID"
    )
    data_available: bool = Field(
        default=True,
        description="False when Alpha Vantage returned no data (rate-limited); scores are fallback-only.",
    )
