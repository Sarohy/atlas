"""Pydantic schema for the Extension & Washout Overlay endpoint (Spec v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MetricLegsOut(BaseModel):
    """Extension-severity legs (§10) — display/context only."""

    moderate: list[str] = Field(default_factory=list)
    extreme: list[str] = Field(default_factory=list)


class ThresholdRow(BaseModel):
    """A single editable overlay threshold (§10) for the Settings view."""

    key: str
    value: str
    group: str


class RiskExceptionRow(BaseModel):
    """A per-name override / risk exception for the Risk-exceptions view."""

    ticker: str
    track: str
    overshoot: str
    elasticity_tier: str
    flags: list[str] = Field(default_factory=list)
    note: str = ""


class WashoutReferenceResponse(BaseModel):
    """Settings thresholds + Risk exception rows (read-only reference)."""

    thresholds: list[ThresholdRow] = Field(default_factory=list)
    exceptions: list[RiskExceptionRow] = Field(default_factory=list)


class ExtensionWashoutResponse(BaseModel):
    """Display/posture overlay. Reads price/flow only — never touches F1-F5."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str

    # --- Headline posture (§9) ---
    state: str = Field(description="One of the nine overlay states (§9).")
    reason: str = Field(description="Plain-English rationale for the state.")
    rung: str = Field(description="Extension ladder action label (§3).")

    # --- Per-name tags (§2 / §3.2) ---
    track: str = Field(description="EXTENSION | BREADTH_FLOW (track wins over tier).")
    overshoot: str = Field(description="MASSIVE | MODERATE | SHARP_FALLER | EXCLUDED | UNKNOWN.")
    low_confidence: bool = Field(description="True for <3-washout / unmapped names.")

    # --- Trim authorization (§7) + size rule (§3.1) ---
    trim_authorized: bool = Field(description="Whether a share trim is authorized (§7).")
    size_relabeled: bool = Field(
        description="True when a below-target position re-labeled a trim state to Stop-Add (§3.1)."
    )
    confirmation_count: int = Field(description="Number of behavioural confirmation legs present.")
    confirmation_present: list[str] = Field(default_factory=list)

    # --- Confirmation-leg inputs (what fired) ---
    flow_distribution: bool = Field(default=False, description="DP sell% >= threshold, down day.")
    vwap_lost: bool = Field(
        default=False, description="Close below daily VWAP (only counts when extended >= Stop-Add)."
    )
    group_rolling: bool = Field(default=False, description="Breadth alert active (group rolling).")
    absorption: bool = Field(
        default=False, description="Extreme extension + DP buying, no follow-through (§4)."
    )
    hard_override: bool = Field(
        default=False, description="Confirmed close back below 20d/50d (§7)."
    )
    negative_catalyst: bool = Field(
        default=False, description="Operator-supplied negative catalyst."
    )

    # --- Extension metrics (read-only; never write to the score) ---
    dist_50d: float | None = Field(None, description="Distance above the 50-day MA, percent.")
    rsi_14: float | None = None
    move_21d_pct: float | None = None
    move_14d_pct: float | None = None
    move_20d_pct: float | None = None
    dark_pool_sell_pct: float | None = Field(
        None, description="Latest-session dark-pool sell% (reactive DP confirm, §6)."
    )
    metric_legs: MetricLegsOut = Field(default_factory=MetricLegsOut)

    # --- Position sizing (§3.1) ---
    position_weight_pct: float | None = Field(None, description="Live position weight, % NAV.")
    target_pct: float = Field(description="Target weight used for the size gate, % NAV.")
    below_target: bool | None = Field(None, description="True/False, or null when weight unknown.")

    # --- Breadth (§5, book-level) ---
    breadth: str | None = Field(None, description="BREADTH_WATCH | BREADTH_HEDGE | null.")
    breadth_watch_count: int = Field(default=0, description="Names down in the watch band.")
    breadth_hedge_count: int = Field(default=0, description="Names down by the hedge threshold.")
    breadth_universe_size: int = Field(default=0)

    # --- Overshoot Elasticity (SPEC v2.1 amendment — sub-module, sizing only) ---
    elasticity_tier: str = Field(
        default="UNKNOWN",
        description="EXTREME | HIGH | MODERATE | LOW | SHARP_FALLER | NEVER_CROSS | ANOMALY.",
    )
    elasticity_score: int | None = Field(None, description="0-100 elasticity score (None on gap).")
    elasticity_confidence: str = Field(default="LOW", description="HIGH | MODERATE | LOW.")
    elasticity_event_count: int = Field(default=0, description="Historical overshoot event count.")
    plus40_state: str = Field(
        default="ARM_PROTECTION", description="Recommended posture state at +40 for this tier."
    )
    plus40_behavior: str = Field(default="", description="+40 behaviour label for this tier.")
    elasticity_ladder: list[float] = Field(
        default_factory=list, description="Tier-spaced ladder lines [arm, active, forced] (50d %)."
    )
    sizing_guidance: str = Field(default="", description="Core/satellite/tactical sizing guidance.")
    elasticity_provisional: bool = Field(default=False)
    elasticity_watch_promote: bool = Field(default=False)
    elasticity_excluded_from_recalibration: bool = Field(default=False)
    elasticity_hard_override: bool = Field(default=False)
    rv20: float | None = Field(None, description="Annualized realized vol, 20d (%).")
    rv60: float | None = Field(None, description="Annualized realized vol, 60d (%).")
    beta: float | None = Field(None, description="Beta used for the elasticity score, if supplied.")
    elasticity_data_gaps: list[str] = Field(
        default_factory=list,
        description="Sources not yet wired into the elasticity score (DATA_GAP).",
    )

    data_gaps: list[str] = Field(default_factory=list)
