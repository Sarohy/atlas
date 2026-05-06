"""Pydantic schemas for the Framework 6 Conviction Action endpoint.

v7.3.5 spec — New tier structure.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Tier(StrEnum):
    """Framework 6 conviction tier."""

    T1_ELITE = "T1_ELITE"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    BELOW_GATE = "BELOW_GATE"


class PositionSizeStatus(StrEnum):
    """Whether the current position is inside, below, or above the tier range."""

    UNDERWEIGHT = "UNDERWEIGHT"
    IN_RANGE = "IN_RANGE"
    OVERWEIGHT = "OVERWEIGHT"
    NO_POSITION = "NO_POSITION"


class ConsensusStatus(StrEnum):
    """3-AI consensus state — only relevant for GREY_ZONE tier."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class ConvictionActionResponse(BaseModel):
    """Framework 6 v7.3.4 — full conviction-action result for a single ticker."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    final_score: float = Field(
        description="Regime-adjusted framework score used for tier assignment."
    )

    # ── Tier ────────────────────────────────────────────────────────────────
    tier: Tier = Field(description="Assigned conviction tier.")
    tier_label: str = Field(description="Human-readable tier label (e.g. 'TIER 1 — CORE').")
    tier_color: str = Field(description="Hex colour for the tier (e.g. '#39d353').")

    # ── Score band ──────────────────────────────────────────────────────────
    score_band_min: int = Field(description="Lower inclusive bound of the tier's score band.")
    score_band_max: int | None = Field(
        description="Upper inclusive bound, or None for TIER_1_CORE (no ceiling)."
    )

    # ── Size range ──────────────────────────────────────────────────────────
    size_min_pct: float = Field(description="Tier minimum target size as % of NAV (e.g. 3.0).")
    size_max_pct: float = Field(description="Tier maximum target size as % of NAV (e.g. 5.0).")

    # ── Action text ─────────────────────────────────────────────────────────
    action: str = Field(description="Primary action text for this tier.")
    leaps_eligible: bool = Field(description="True only for T1_ELITE (score ≥ 85).")

    # ── Position size ───────────────────────────────────────────────────────
    current_weight_pct: float = Field(description="Current position weight as % of NAV.")
    position_size_status: PositionSizeStatus = Field(
        description="UNDERWEIGHT / IN_RANGE / OVERWEIGHT / NO_POSITION."
    )
    room_to_add_pct: float = Field(description="Room to add as % of NAV (0.0 when at/above max).")
    trim_suggested: bool = Field(description="True when current weight exceeds tier max.")

    # ── Adds permission ─────────────────────────────────────────────────────
    adds_permitted: bool = Field(description="True when no blocking condition is active.")
    adds_blocked_reason: str | None = Field(
        description="Human-readable blocking reason when adds_permitted=False."
    )

    # ── External cap flags ──────────────────────────────────────────────────
    beta_cap_active: bool = Field(description="True when Framework 13 beta cap is blocking adds.")
    concentration_cap: bool = Field(
        description="True when Framework 14 concentration cap is blocking adds."
    )

    # ── Exit cycle ──────────────────────────────────────────────────────────
    exit_triggered: bool = Field(description="True after two consecutive Friday closes below 50.")
    exit_cycle_count: int = Field(description="Number of consecutive Friday closes below 50 (0-2).")

    # ── Cluster (from Framework 14) ──────────────────────────────────────────
    cluster: str = Field(description="Correlation cluster name.")
    cluster_weight_pct: float = Field(description="Total cluster weight as % of NAV.")
    cluster_status: str = Field(description="NORMAL / YELLOW_ZONE / RED_ZONE.")

    # ── Framework 18 — 4-Week Trend Gate ────────────────────────────────────
    f18_active: bool | None = Field(
        default=None,
        description=(
            "True when the 4-Week Trend Gate is active, False when clear, "
            "None when SPY data unavailable. None is treated as BLOCKED."
        ),
    )
    f18_speculative_blocked: bool = Field(
        default=False,
        description=(
            "True when f18_active=True and ticker is NOT in the portfolio. "
            "No new positions on non-portfolio tickers while gate is active."
        ),
    )
    f18_tier3_blocked: bool = Field(
        default=False,
        description=(
            "True when f18_active=True and the ticker's tier is T3. "
            "Tier 3 adds are blocked while the gate is active."
        ),
    )
    f18_size_max_reduced: bool = Field(
        default=False,
        description=(
            "True when size_max_pct has been reduced by add_reduction_pct "
            "because f18_active=True."
        ),
    )
    f18_note: str | None = Field(
        default=None,
        description="Human-readable F18 reduction or block note shown in the UI.",
    )

    # ── Bottom-line rationale ───────────────────────────────────────────────
    rationale: str = Field(description="One-line bottom action message.")


# ---------------------------------------------------------------------------
# Mutation request schemas
# ---------------------------------------------------------------------------


class ConsensusUpdateRequest(BaseModel):
    """Body for POST /conviction-action/{ticker}/consensus."""

    status: ConsensusStatus = Field(description="New consensus status: CONFIRMED or FAILED.")


class ExitCycleResponse(BaseModel):
    """Response for POST /conviction-action/{ticker}/exit-cycle."""

    ticker: str
    exit_cycle_count: int
    exit_triggered: bool
