"""Pydantic schemas for Framework 15 — VIX Regime Override."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class F15Severity(StrEnum):
    """Alert severity when F15 fires.

    Severity is driven by Framework 2 regime at the time of trigger.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class F15Status(StrEnum):
    """Overall Framework 15 halt state for the current session."""

    ACTIVE = "ACTIVE"            # VIX spike fired — halt in force
    CLEAR = "CLEAR"              # No spike detected this session
    UNKNOWN = "UNKNOWN"          # VIX data unavailable — cannot determine
    OUTSIDE_HOURS = "OUTSIDE_HOURS"  # Market closed — F15 only monitors intraday


class OrderReviewStatus(StrEnum):
    """Human review state for a paused order."""

    PENDING_REVIEW = "PENDING_REVIEW"
    KEPT = "KEPT"
    MODIFIED = "MODIFIED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class PausedOrder(BaseModel):
    """One order paused when F15 fired."""

    order_id: int
    ticker: str
    order_type: str
    paused_at: str
    review_status: OrderReviewStatus


class VixSnapshot(BaseModel):
    """Lightweight VIX snapshot for Framework 25 (Liquidity Protocol).

    Framework 25 reads current intraday VIX exclusively from this endpoint.
    F15 is the single source of truth for intraday VIX in the system.
    """

    current_vix: float | None
    session_open_vix: float | None
    spike_size: float | None
    spike_threshold: float | None
    f15_active: bool | None
    data_available: bool
    market_open: bool
    last_updated: str


class Framework15SimpleResult(BaseModel):
    """Lightweight status for consuming frameworks (F3, F4, F16, Section 17).

    Consuming frameworks call GET /api/v1/framework15/status/simple.
    They NEVER independently check VIX spike conditions.
    """

    f15_status: F15Status
    f15_active: bool | None        # None = UNKNOWN — treat as blocked
    severity: F15Severity | None
    new_market_orders_blocked: bool
    non_stop_orders_paused: bool
    data_gap_severity: str
    market_open: bool


# ---------------------------------------------------------------------------
# Main result model
# ---------------------------------------------------------------------------


class Framework15Result(BaseModel):
    """Full Framework 15 evaluation result — session-level (not per-ticker).

    Cached 60 seconds.  Very short TTL because intraday VIX changes every minute.
    F15 is the ONLY source for f15_active in the system.
    F3, F4, Section 17, F25 all read from this result.
    """

    # Core halt state
    f15_status: F15Status
    f15_active: bool | None        # None = UNKNOWN

    # Alert severity (set when f15_active is True or UNKNOWN)
    severity: F15Severity | None

    # VIX data
    current_vix: float | None
    session_open_vix: float | None
    spike_size: float | None
    spike_threshold: float | None   # from atlas_config — never hardcoded
    spike_confirmed: bool | None    # None when VIX data unavailable

    # Session state
    market_open: bool
    session_date: str
    halt_triggered_at: str | None   # ISO timestamp when halt first fired

    # Downstream blocking state
    new_market_orders_blocked: bool
    non_stop_orders_paused: bool
    limit_orders_flagged: bool

    # Paused orders
    paused_orders_count: int
    paused_orders: list[PausedOrder]

    # Upstream data sources
    regime: str | None              # from Framework 2 — never computed here
    regime_available: bool
    polygon_available: bool

    # Override state
    override_active: bool
    override_reason: str | None

    # Data quality
    data_gap_severity: str          # NONE | PARTIAL | MAJOR | CRITICAL
    warning_messages: list[str]

    # Meta
    last_updated: str
    cache_hit: bool


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AddOverrideRequest(BaseModel):
    """Human override request for mid-session F15 halt.

    Minimum 50-character reason enforced in the router.
    Does NOT clear f15_active — only restores specified order types.
    Logged to decision_trace.
    """

    override_reason: str
    restore_order_types: list[str]


class ReviewOrderRequest(BaseModel):
    """Human review decision for a paused order."""

    decision: str    # KEEP | MODIFY | CANCEL
    reviewed_by: str
