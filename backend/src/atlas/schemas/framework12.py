"""Pydantic schemas for Framework 12 — Catalyst No-Fly Zone."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CatalystType(StrEnum):
    """Types of catalyst events tracked by Framework 12.

    EARNINGS is sourced exclusively from Framework 7.
    All other types are entered manually by the operator.
    """

    EARNINGS = "EARNINGS"
    INDEX_INCLUSION = "INDEX_INCLUSION"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    PARTNERSHIP = "PARTNERSHIP"
    ACQUISITION = "ACQUISITION"
    OTHER = "OTHER"


class NoFlyStatus(StrEnum):
    """Overall no-fly zone state for a ticker."""

    ACTIVE = "ACTIVE"
    CLEAR = "CLEAR"
    UNKNOWN = "UNKNOWN"


class ActionStatus(StrEnum):
    """Status of a single sell-side action under Framework 12."""

    BLOCKED = "BLOCKED"
    PERMITTED = "PERMITTED"
    OVERRIDDEN = "OVERRIDDEN"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ActiveCatalyst(BaseModel):
    """Details of one active catalyst within the no-fly window."""

    catalyst_type: CatalystType
    catalyst_date: str
    days_to_catalyst: int
    description: str | None
    source: str


class OverrideDetail(BaseModel):
    """Details of an active human override for one action type."""

    action_type: str
    override_reason: str
    entered_by: str | None
    created_at: str
    override_expires_at: str


# ---------------------------------------------------------------------------
# Main result model
# ---------------------------------------------------------------------------


class Framework12Result(BaseModel):
    """Full Framework 12 evaluation result for one ticker."""

    ticker: str

    # Core no-fly state
    no_fly_status: NoFlyStatus
    no_fly_active: bool | None  # None = UNKNOWN

    # Catalysts in window
    active_catalysts: list[ActiveCatalyst]
    nearest_catalyst: ActiveCatalyst | None
    catalyst_window_days: int  # read from atlas_config, never hardcoded

    # Per-action status
    covered_calls_status: ActionStatus
    partial_sells_status: ActionStatus
    trims_status: ActionStatus

    # Active overrides (one per action at most)
    covered_calls_override: OverrideDetail | None
    partial_sells_override: OverrideDetail | None
    trims_override: OverrideDetail | None

    # Exit rule conflict / deferral
    exit_rule_active: bool | None
    exit_rule_deferred: bool
    exit_rule_deferred_until: str | None
    exit_deferral_trading_days: int  # read from atlas_config, never hardcoded

    # Data source availability
    f7_available: bool
    catalyst_db_available: bool
    section16_available: bool

    # Data quality
    data_gap_severity: str
    warning_messages: list[str]
    last_updated: str
    cache_hit: bool


# ---------------------------------------------------------------------------
# Simplified status (for consuming frameworks)
# ---------------------------------------------------------------------------


class Framework12StatusResult(BaseModel):
    """Lightweight status used by Framework 3 and Section 16."""

    no_fly_status: str
    no_fly_active: bool | None
    covered_calls_status: str
    partial_sells_status: str
    trims_status: str
    nearest_catalyst_date: str | None
    nearest_catalyst_type: str | None
    days_to_catalyst: int | None
    exit_rule_deferred: bool
    exit_rule_deferred_until: str | None
    data_gap_severity: str


# ---------------------------------------------------------------------------
# Portfolio summary (all held tickers)
# ---------------------------------------------------------------------------


class Framework12PortfolioSummary(BaseModel):
    """F12 status across the whole portfolio — for morning briefing overview."""

    tickers_in_no_fly: list[str]
    tickers_clear: list[str]
    tickers_unknown: list[str]
    total_held: int
    active_catalysts_count: int


# ---------------------------------------------------------------------------
# Request / response models for write endpoints
# ---------------------------------------------------------------------------


class AddCatalystRequest(BaseModel):
    """Body for POST /framework12/catalysts — operator adds a non-earnings catalyst."""

    ticker: str
    catalyst_type: str
    catalyst_date: str  # YYYY-MM-DD
    description: str | None = None
    entered_by: str | None = None


class CatalystResponse(BaseModel):
    """Returned after creating or deactivating a catalyst event."""

    id: int
    ticker: str
    catalyst_type: str
    catalyst_date: str
    description: str | None
    status: str
    entered_by: str | None


class AddOverrideRequest(BaseModel):
    """Body for POST /framework12/{ticker}/override."""

    action_type: str  # COVERED_CALL | PARTIAL_SELL | TRIM
    override_reason: str
    override_duration_hours: int
    entered_by: str | None = None
