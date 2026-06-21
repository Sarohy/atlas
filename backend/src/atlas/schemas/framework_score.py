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

from atlas.schemas.fundamental import F5DebugBridge

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


class EtfBranchComponent(BaseModel):
    """One weighted component used by an ETF branch-specific model."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Component label used in the branch model.")
    weight: float = Field(gt=0.0, le=1.0, description="Branch weight for this component.")
    score: int = Field(ge=0, le=100, description="Component score on a 0-100 scale.")


class EtfConstituent(BaseModel):
    """One curated constituent of a thematic/proxy basket for look-through.

    Weights are approximate/curated (the whole proxy look-through model is
    curated per the ATLAS spec), used only to express how much of the basket
    ATLAS can directly score through to.
    """

    model_config = ConfigDict(from_attributes=True)

    symbol: str = Field(description="Constituent ticker or name.")
    weight_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Approximate (curated) share of basket weight, in percent.",
    )
    scored: bool = Field(
        description=(
            "True when ATLAS directly scores this name (US-listed operating "
            "company with F1-F5 coverage); False for foreign/untracked names."
        ),
    )
    note: str | None = Field(
        default=None,
        description="Optional note (e.g. 'foreign-listed — not directly scored').",
    )


class EtfHedgeInputs(BaseModel):
    """Optional hedge-specific inputs for ETF option protection workflows."""

    model_config = ConfigDict(from_attributes=True)

    purpose: str = Field(description="Protective objective of the hedge instrument.")
    underlying: str = Field(description="Underlying ETF being hedged.")
    portfolio_beta_covered: list[str] = Field(
        default_factory=list,
        description="Representative holdings or sleeves covered by the hedge.",
    )
    iv_rank: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Implied volatility rank when available.",
    )
    delta: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Option delta when available.",
    )
    expiry_days: int | None = Field(
        default=None,
        ge=0,
        description="Days to expiry for the hedge option contract when available.",
    )
    max_hold_days: int | None = Field(
        default=None,
        ge=0,
        description="Risk policy max-hold guidance for the hedge setup.",
    )


class EtfBranchMetadata(BaseModel):
    """Branch-routing metadata for ETF/fund/proxy instruments."""

    model_config = ConfigDict(from_attributes=True)

    route: str = Field(description="ETF branch route key.")
    label: str = Field(description="Human-readable branch label.")
    headline_label: str = Field(description="Primary UI headline for this branch.")
    timing_overlay_role: str = Field(description="How F4/timing overlays are used in this branch.")
    holdings_driver: str | None = Field(
        default=None,
        description="Optional holdings driver summary for thematic/factor proxy baskets.",
    )
    components: list[EtfBranchComponent] = Field(
        default_factory=list,
        description="Component score breakdown for the selected ETF branch model.",
    )
    constituents: list[EtfConstituent] = Field(
        default_factory=list,
        description=(
            "Curated look-through constituents (thematic/proxy baskets only). "
            "Weights are approximate; used to express scored-coverage."
        ),
    )
    scored_coverage_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Approximate share of basket weight made up of ATLAS-scored names. "
            "Null when no curated constituent table is available."
        ),
    )
    coverage_note: str | None = Field(
        default=None,
        description="Human-readable explanation of the scored-coverage figure.",
    )
    hedge_inputs: EtfHedgeInputs | None = Field(
        default=None,
        description="Hedge option inputs when the route is hedge/protective.",
    )


class IntlFactor(BaseModel):
    """One INTL-3F factor (I1/I2/I3) for international operating companies."""

    model_config = ConfigDict(from_attributes=True)

    key: str = Field(description="INTL factor identifier: 'i1' | 'i2' | 'i3'.")
    name: str = Field(description="Human-readable INTL factor name.")
    score: int = Field(ge=0, le=100, description="Factor score on a 0-100 scale.")
    available: bool = Field(
        description="False when no usable international data exists for this factor.",
    )
    source: str = Field(
        description="Provenance of the factor (e.g. 'fundamental', 'momentum', 'DATA_GAP').",
    )


class IntlDataTask(BaseModel):
    """A missing-data task for an international name (what ATLAS still needs)."""

    model_config = ConfigDict(from_attributes=True)

    item: str = Field(description="Missing data item, e.g. 'local financials'.")
    status: str = Field(description="MISSING | PARTIAL.")


class IntlBranchMetadata(BaseModel):
    """Routing metadata for international / ADR / OTC operating companies.

    These names are NOT scored on the domestic F1-F5 model: missing U.S. data
    feeds must not be read as bad fundamentals. The INTL-3F model (I1 business,
    I2 market, I3 external confirmation) ranks them on available data only, and
    missing U.S. options/flow is surfaced as N/A (never bearish / auto-avoid).
    """

    model_config = ConfigDict(from_attributes=True)

    route: str = Field(description="INTL route key (INTL_OPERATING).")
    label: str = Field(description="Branch label, e.g. 'INTL-3F — International Operating Company'.")
    headline_label: str = Field(description="Primary UI headline / action for this branch.")
    instrument_kind: str = Field(
        description="ADR | OTC foreign ordinary | Foreign operating company.",
    )
    coverage_label: str = Field(description="INTL-OK | INTL-PARTIAL | INTL-DATA-GAP.")
    domestic_note: str = Field(
        default="Domestic F1–F5 not applicable.",
        description="Disclosure that domestic factors do not apply.",
    )
    f4_note: str = Field(
        default="F4 N/A — no U.S. flow coverage (unavailable, not bearish).",
        description="How missing U.S. options/dark-pool flow is treated.",
    )
    rank_pending: bool = Field(
        default=False,
        description="True when coverage is partial/absent and the rank is provisional.",
    )
    size_capped: bool = Field(
        default=False,
        description="True when liquidity/coverage warrants a capped position size.",
    )
    factors: list[IntlFactor] = Field(
        default_factory=list,
        description="INTL-3F factor breakdown (I1/I2/I3).",
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Status labels (INTL-PARTIAL, NO-US-FLOW, OTC-LIQUIDITY-RISK, …).",
    )
    data_tasks: list[IntlDataTask] = Field(
        default_factory=list,
        description="Visible list of missing-data tasks for this ticker.",
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
    f5_debug_bridge: F5DebugBridge | None = Field(
        default=None,
        description="Expanded F5 debug bridge propagated from the fundamental service.",
    )
    etf_branch: EtfBranchMetadata | None = Field(
        default=None,
        description=(
            "Populated for ETF/fund/proxy instruments after universal router classification. "
            "Contains branch-specific model metadata used by UI and diagnostics."
        ),
    )
    intl_branch: IntlBranchMetadata | None = Field(
        default=None,
        description=(
            "Populated for international / ADR / OTC operating companies routed to INTL-3F. "
            "Domestic F1-F5 are suppressed; carries coverage labels and missing-data tasks."
        ),
    )
