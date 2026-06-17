"""Pydantic schemas for the Framework Score endpoint.

The Framework Score is the top-level ATLAS conviction metric.  It aggregates
the five factor scores (F1-F5) using the weightings defined in the
Factor_Mapping_Guide and maps the result to a human-readable action.

Formula (Factor_Mapping_Guide §Final Score):
  Raw Total = (F1 x 0.20) + (F2 x 0.25) + (F3 x 0.15) + (F4 x 0.15) + (F5 x 0.20)
  Final Score = round(Raw Total), clamped [0, 100]

  Max raw total = 95 (all factors = 100).

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
    flow_monitor_action: str | None = Field(
        default=None,
        description=(
            "F4 only: the Flow Monitor final action (add gate). Populated for the F4 row so "
            "the panel shows the action verdict, never an implied BUY from the factor itself."
        ),
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
        description="Weighted sum of all factor contributions (max 95).",
    )
    final_score: int = Field(
        ge=0,
        le=100,
        description="Final ATLAS conviction score: round(raw_total), clamped [0, 100].",
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
    degraded: bool = Field(
        default=False,
        description=(
            "True when F2 or F5 used fallback scores due to an Alpha Vantage "
            "rate-limit. Do not cache this response."
        ),
    )
    f4_data_gap_badge: str | None = Field(
        default=None,
        description=(
            "Short badge label propagated from Framework 9 "
            "when options data is incomplete."
        ),
    )
    f4_data_gap_message: str | None = Field(
        default=None,
        description="Human-readable message explaining the F4 data gap.",
    )
    f4_data_gap_tooltip: str | None = Field(
        default=None,
        description="Detailed tooltip text for the F4 data gap badge.",
    )

    # --- Framework 8 insider buying bonus ---
    f5_raw_score: int | None = Field(
        default=None,
        description=(
            "Raw F5 score before any adjustments. "
            "Null when F5 could not be computed."
        ),
    )
    f8_buying_bonus: int = Field(
        default=0,
        ge=0,
        description="Additive bonus applied to the framework score from insider buying activity.",
    )
    f8_clustered_selling_note: str | None = Field(
        default=None,
        description=(
            "Display-only note when multiple C-suite insiders sell without a 10b5-1 plan. "
            "Null when no concern detected. Carries no scoring impact."
        ),
    )
