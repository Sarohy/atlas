"""Pydantic schemas for the Regime Modifier endpoint."""

from pydantic import BaseModel, Field
from typing import Literal


GeopoliticalState = Literal["NONE", "RESOLVED", "DE_ESCALATING", "ACTIVE_RISK", "ESCALATING"]


class RegimeModifierResponse(BaseModel):
    """Response from the regime modifier endpoint."""

    ticker: str
    geopolitical_state: GeopoliticalState

    # ── Market conditions (None when Polygon.io data unavailable) ─────────
    brent_price: float | None = Field(
        description="Brent crude price in USD per barrel (most recent daily close).",
    )
    vix_value: float | None = Field(
        description="CBOE VIX index level (most recent daily close).",
    )
    brent_consecutive_below_95_count: int = Field(
        description="Number of consecutive Brent closes below $95 using the most recent closes.",
    )

    # ── Framework score ───────────────────────────────────────────────────
    base_score: int = Field(
        description="Original framework score before regime adjustment (0-100).",
    )
    adjusted_score: int = Field(
        description="Score after applying the triggered regime rule (0-100).",
    )

    # ── Regime determination ──────────────────────────────────────────────
    rule_triggered: int | None = Field(
        description="Which regime rule fired (1 = Crisis, 2 = Caution, 3 = Clear), "
        "or None when market conditions are normal.",
    )
    rule: str = Field(
        description="Human-readable name of the triggered rule: "
        "CRISIS | CAUTION | CLEAR | NORMAL.",
    )
    effective_regime: str = Field(
        description="Displayed regime after applying the geopolitical gate.",
    )
    modifier: int = Field(
        description="Score delta applied by the triggered rule: "
        "-10 (Crisis), -5 (Caution), +5 (Clear), 0 (Normal).",
    )

    # ── Cash guidance — fractions (0.35 = 35 %) ──────────────────────────
    min_cash_pct: float = Field(
        description="Minimum required cash fraction of the ticker's position value.",
    )
    max_cash_pct: float = Field(
        description="Maximum recommended cash fraction of the ticker's position value.",
    )

    # ── Cash guidance — USD amounts ───────────────────────────────────────
    # None when the ticker is not present in the portfolio DB.
    min_cash_usd: float | None = Field(
        description="Minimum cash in USD (min_cash_pct x position_value). "
        "None when ticker is not in the portfolio.",
    )
    max_cash_usd: float | None = Field(
        description="Maximum cash in USD (max_cash_pct x position_value). "
        "None when ticker is not in the portfolio.",
    )

    # ── Human-readable guidance ───────────────────────────────────────────
    output_text: str = Field(
        description="Regime cash-management instruction (multi-line for crisis rules).",
    )
    determination_text: str = Field(
        description="Human-readable summary of the Brent/VIX calculation and modifier.",
    )

    # ── Enriched condition display (Section 14 spec v2.1) ─────────────────
    brent_condition: str = Field(
        description="Brent price with zone label, e.g. '$97.50 — $95-110 (CAUTION trigger)'.",
        default="",
    )
    vix_condition: str = Field(
        description="VIX level with zone label, e.g. '17.48 — Below 22 (SOFT CAUTION zone)'.",
        default="",
    )
    geo_condition: str = Field(
        description="Active geopolitical flag value, e.g. 'ACTIVE_RISK'.",
        default="",
    )
    trigger_logic: str = Field(
        description="Whether this regime uses OR or AND logic: 'OR — either Brent or VIX triggers'.",
        default="",
    )
    modifier_reason: str = Field(
        description="Explanation of the modifier applied, e.g. 'CAUTION + Escalating geo → −7'.",
        default="",
    )
    special_case_active: bool = Field(
        description="True only when regime=CAUTION and geo=ESCALATING (−7 modifier).",
        default=False,
    )
    cash_floor_pct: float = Field(
        description="Minimum portfolio cash floor fraction per Section 14.1 (0.08 = 8%).",
        default=0.20,
    )
