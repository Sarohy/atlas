"""Pydantic schemas for the Framework Score endpoint.

The Framework Score is the top-level ATLAS conviction metric.  It aggregates
the five factor scores (F1-F5) using the weightings defined in the
Factor_Mapping_Guide, adds the Brent-crude regime modifier, and maps the result
to a human-readable action.

Formula (Factor_Mapping_Guide §Final Score):
  Raw Total = (F1 x 0.20) + (F2 x 0.25) + (F3 x 0.15) + (F4 x 0.15) + (F5 x 0.20)
  Final Score = round(Raw Total + Regime Modifier), clamped [0, 100]

  Max raw total = 95 (all factors = 100) - the remaining 5 pts come from a
  CLEAR regime modifier of +5.

Regime modifiers:
  CRISIS HALT  Brent > $110  ->  -10  (cash floor 40 %)
  CAUTION      $95 <= Brent <= $110  ->  -5   (cash floor 25 %)
  CLEAR        Brent < $95   ->  +5   (cash floor 10 %)
  No data      ->  CAUTION  (conservative fallback)

Score -> Action map:
  90-100  MAXIMUM POSITION
  80-89   HOLD / ADD
  70-79   HOLD
  60-69   REDUCE
  55-59   REDUCE FURTHER
  < 55    EXIT
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


class FactorBreakdown(BaseModel):
    """Contribution of a single factor (F1-F5) to the Framework Score."""

    model_config = ConfigDict(from_attributes=True)

    key: str = Field(description="Factor identifier: 'f1' … 'f5'.")
    name: str = Field(description="Human-readable factor name (e.g. 'Momentum').")
    score: int = Field(
        ge=0,
        le=100,
        description="Composite factor score (0-100) returned by the factor service.",
    )
    weight: float = Field(
        gt=0.0,
        le=1.0,
        description="Framework weighting for this factor (e.g. 0.20 for F1).",
    )
    contribution: float = Field(
        ge=0.0,
        le=100.0,
        description="Weighted contribution to the raw total (score x weight).",
    )
    grade: str = Field(
        description="Factor-level grade string (e.g. 'STRONG BUY', 'BUY', 'NEUTRAL').",
    )
    available: bool = Field(
        default=True,
        description=(
            "False when the factor could not be computed (missing API key or network error). "
            "A neutral score of 50 is used as fallback."
        ),
    )


class RegimeInfo(BaseModel):
    """Brent-crude regime state and its effect on the final score."""

    model_config = ConfigDict(from_attributes=True)

    regime: str = Field(
        description="Regime label: 'CRISIS HALT' | 'CAUTION' | 'CLEAR'.",
    )
    brent_price: float | None = Field(
        None,
        description="Latest Brent crude close price (USD).  Null when unavailable.",
    )
    modifier: int = Field(
        description="Score adjustment applied to raw_total: -10, -5, or +5.",
    )
    cash_floor_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Minimum cash floor percentage implied by the regime (0.40 / 0.25 / 0.10).",
    )


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class FrameworkScoreResponse(BaseModel):
    """Complete Framework Score response for a single ticker.

    Returned by GET /api/v1/framework-score/{ticker}.
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    factors: list[FactorBreakdown] = Field(
        description="Ordered list of factor breakdowns: F1, F2, F3, F4, F5.",
    )
    raw_total: float = Field(
        ge=0.0,
        le=95.0,
        description=(
            "Weighted sum of all factor contributions before the regime modifier is applied. "
            "Maximum value is 95 (all factors perfect, five-factor weights sum to 0.95)."
        ),
    )
    regime: RegimeInfo = Field(description="Regime state derived from the current Brent price.")
    final_score: int = Field(
        ge=0,
        le=100,
        description="Final ATLAS conviction score: round(raw_total + regime.modifier), [0, 100].",
    )
    action: str = Field(
        description=(
            "Recommended action per the Factor_Mapping_Guide score-action map: "
            "'MAXIMUM POSITION' | 'HOLD / ADD' | 'HOLD' | 'REDUCE' | 'REDUCE FURTHER' | 'EXIT'."
        ),
    )
    action_tone: str = Field(
        description=(
            "CSS tone class for colour-coding the action badge: "
            "'tone-green' | 'tone-cyan' | 'tone-yellow' | "
            "'tone-orange' | 'tone-red' | 'tone-dark-red'."
        ),
    )
    f5_blocked: bool = Field(
        default=False,
        description=(
            "True when F5 Altman Z-Score is below 1.8 (distress zone), "
            "imposing a hard block on new capital deployment."
        ),
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Human-readable flag messages (e.g. F5 cap applied, missing API keys).",
    )
