"""Pydantic schemas for the F3 Analyst Conviction endpoint — v7.3.4.

F3 v7.3.4 uses a base-score + modifier approach:
  Priority 1: Consensus label  → base score  (Strong Buy 90 / Buy 78 / Hold 55 / Sell 30)
  Priority 2: Analyst count    → modifier     (+8 / +5 / +3 / 0 / -5)
  Priority 3: PT revision dir  → modifier     (+5 / +3 / 0 / -5 / -10)
  Priority 4: Net upgrades 30d → modifier     (+5 / +3 / 0 / -5 / -10)
  Priority 5: Price vs target  → adjustment   (applied last)

High consensus override: Buy/SB + ≥9 analysts + 0 sells + raised/maintained PT → min 78
Hard cap: pvt > +20% → f3_final = min(f3_before, 45)
Half penalty: pvt in (10%,20%] AND consensus NOT deteriorating → -7 not -15
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Sub-indicator schemas
# ---------------------------------------------------------------------------


class ConsensusRatingIndicator(BaseModel):
    """Analyst buy/hold/sell breakdown and consensus label.

    base_score maps the label to the v7.3.4 base value:
      Strong Buy → 90 | Buy → 78 | Hold → 55 | Sell → 30
    """

    model_config = ConfigDict(from_attributes=True)

    strong_buy_count: int = Field(ge=0)
    buy_count: int = Field(ge=0)
    hold_count: int = Field(ge=0)
    sell_count: int = Field(ge=0)
    strong_sell_count: int = Field(ge=0)
    total_analysts: int = Field(ge=0)
    buy_pct: float | None = Field(
        None,
        description="(Strong Buy + Buy) as % of total. Null when no analyst coverage.",
    )
    label: str = Field(description="STRONG BUY | BUY | HOLD | SELL | NO DATA")
    base_score: int | None = Field(
        default=None,
        description="v7.3.4 base score for this consensus label (90/78/55/30).",
    )


class AnalystCoverageIndicator(BaseModel):
    """Analyst coverage count and its v7.3.4 modifier.

    Modifier mapping: >30 → +8 | 20-30 → +5 | 10-19 → +3 | 5-9 → 0 | <5 → -5
    """

    model_config = ConfigDict(from_attributes=True)

    num_analysts: int = Field(ge=0)
    modifier: int | None = Field(
        default=None,
        description="v7.3.4 analyst count modifier. Null when no coverage data.",
    )


class PtDirectionIndicator(BaseModel):
    """PT revision direction over the last 30 days and its v7.3.4 modifier.

    direction_label values:
      MULTIPLE_RAISES | SINGLE_RAISE | NO_CHANGE | SINGLE_CUT | MULTIPLE_CUTS | NO_DATA

    Modifier mapping:
      MULTIPLE_RAISES → +5 | SINGLE_RAISE → +3 | NO_CHANGE → 0
      SINGLE_CUT → -5 | MULTIPLE_CUTS → -10
    """

    model_config = ConfigDict(from_attributes=True)

    raises_30d: int = Field(ge=0, description="PT raises (Raises/Announces) in last 30 days.")
    lowers_30d: int = Field(ge=0, description="PT cuts (Lowers) in last 30 days.")
    direction_label: str = Field(
        description=(
            "MULTIPLE_RAISES | SINGLE_RAISE | NO_CHANGE | SINGLE_CUT | MULTIPLE_CUTS | NO_DATA"
        )
    )
    modifier: int | None = Field(
        default=None,
        description="v7.3.4 PT revision modifier. Null when Benzinga data unavailable.",
    )


class RecentUpgradesIndicator(BaseModel):
    """Net rating upgrades/downgrades over the last 30 days and its v7.3.4 modifier.

    Modifier mapping:
      net > 2 → +5 | net 1-2 → +3 | net 0 → 0 | net -1 to -2 → -5 | net < -2 → -10
    """

    model_config = ConfigDict(from_attributes=True)

    upgrades_30d: int = Field(ge=0, description="Rating upgrades in last 30 days.")
    downgrades_30d: int = Field(ge=0, description="Rating downgrades in last 30 days.")
    net_upgrades_30d: int = Field(
        description="Net upgrades (positive) or net downgrades (negative) in last 30 days."
    )
    modifier: int | None = Field(
        default=None,
        description="v7.3.4 upgrade/downgrade modifier. Null when Benzinga data unavailable.",
    )


class PtUpsideIndicator(BaseModel):
    """Price vs analyst consensus target — used for Priority 5 adjustment.

    upside_pct:          Traditional upside % for display (positive = stock below target).
    price_vs_target:     (current - target) / target — used for band determination.
    price_vs_target_band: Descriptive band label.
    adjustment:          The score adjustment applied (0, +5, +10, -7, -15, or cap delta).
    """

    model_config = ConfigDict(from_attributes=True)

    current_price: float | None = Field(None, description="Latest closing price (USD).")
    consensus_pt: float | None = Field(None, description="Consensus 12-month price target (USD).")
    upside_pct: float | None = Field(
        None,
        description=(
            "Traditional upside from current price to PT. "
            "Positive = stock below target (upside), negative = above."
        ),
    )
    price_vs_target: float | None = Field(
        None,
        description="(current_price - consensus_pt) / consensus_pt, rounded to 4 dp.",
    )
    price_vs_target_band: str | None = Field(
        None,
        description=(
            "Band label: '20%+ below target (+10)' | '10-20% below target (+5)' | "
            "'At target — neutral (0)' | '10-20% above target (-15)' | "
            "'20%+ above target (capped at 45)'"
        ),
    )
    adjustment: int | None = Field(
        None,
        description="Score adjustment applied by the price vs target band.",
    )
    upside_color: str | None = Field(
        default=None,
        description="Semantic colour token: GREEN | LIGHT_GREEN | NEUTRAL | AMBER | RED",
    )


# ---------------------------------------------------------------------------
# Top-level response schema
# ---------------------------------------------------------------------------


class AnalystResponse(BaseModel):
    """Complete F3 Analyst Conviction analysis for a single ticker — v7.3.4."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # Sub-indicators
    consensus_rating: ConsensusRatingIndicator
    analyst_coverage: AnalystCoverageIndicator
    pt_direction: PtDirectionIndicator
    recent_upgrades: RecentUpgradesIndicator
    pt_upside: PtUpsideIndicator

    # Score computation trail
    f3_before_price_adjustment: int | None = Field(
        default=None,
        description=(
            "base_score + analyst_count_mod + pt_revision_mod + upgrade_downgrade_mod, "
            "before the price vs target adjustment is applied."
        ),
    )
    override_applied: bool = Field(
        default=False,
        description="True when the high consensus override lifted the score to 78 minimum.",
    )
    override_reason: str | None = Field(
        default=None,
        description="Reason string when the high consensus override was applied.",
    )

    # Final score
    f3_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Composite F3 Analyst Conviction score (0-100). Null when no analyst coverage.",
    )
    f3_grade: str = Field(description="STRONG BUY | BUY | NEUTRAL | WEAK | AVOID | NO DATA")
