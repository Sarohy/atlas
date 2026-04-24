"""Pydantic schemas for Framework 19 — NVDA Kill Switch."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class F19Status(StrEnum):
    """Overall Framework 19 kill-switch state for the current session."""

    ACTIVE = "ACTIVE"               # NVDA drop ≥ threshold — kill switch fired
    CLEAR = "CLEAR"                 # No qualifying drop detected this session
    UNKNOWN = "UNKNOWN"             # Polygon data unavailable — cannot determine
    OUTSIDE_HOURS = "OUTSIDE_HOURS" # Market closed — F19 only monitors intraday


class F19Severity(StrEnum):
    """Alert severity when F19 fires."""

    CRITICAL = "CRITICAL"   # Crisis regime + NVDA kill switch simultaneously
    HIGH = "HIGH"            # Standard kill-switch activation
    UNKNOWN = "UNKNOWN"      # Fired but regime data unavailable


class OrderReviewStatus(StrEnum):
    """Human review state for a paused order."""

    PENDING_REVIEW = "PENDING_REVIEW"
    KEPT = "KEPT"
    MODIFIED = "MODIFIED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class NVDADropDetail(BaseModel):
    """Detail of the observed NVDA intraday drop."""

    current_price: float | None
    peak_price_in_window: float | None
    drop_pct: float | None
    drop_amount: float | None
    window_minutes: int | None
    threshold_pct: float
    threshold_breached: bool


class AffectedHolding(BaseModel):
    """Portfolio holding affected by the F19 kill switch."""

    ticker: str
    beta_vs_nvda: float | None      # None when beta data is unavailable
    is_high_beta: bool               # True when beta > f19_beta_threshold
    market_orders_blocked: bool
    buy_orders_paused: bool


class PausedOrder(BaseModel):
    """One order paused when F19 fired."""

    order_id: int
    ticker: str
    order_type: str
    beta_vs_nvda: float | None
    is_high_beta: bool | None
    paused_at: str
    review_status: OrderReviewStatus


class ReviewOrderRequest(BaseModel):
    """Operator review decision for a paused order."""

    decision: str = Field(
        ...,
        description="KEPT | MODIFIED | CANCELLED",
        pattern="^(KEPT|MODIFIED|CANCELLED)$",
    )
    reviewed_by: str = Field(..., min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Lightweight result for consuming frameworks (F3, F4)
# ---------------------------------------------------------------------------


class Framework19SimpleResult(BaseModel):
    """Lightweight status for consuming frameworks (F3, F4).

    F3 and F4 call get_f19_simple(session) from the service.
    They NEVER independently check NVDA drop conditions.

    f19_active = None means UNKNOWN — consuming frameworks treat this as blocked
    (conservative safety posture when data is unavailable).
    """

    f19_status: F19Status
    f19_active: bool | None         # None = UNKNOWN — treat as blocked
    all_ai_buys_blocked: bool       # All AI-correlated buy orders blocked
    high_beta_market_orders_blocked: bool  # High-beta market orders blocked
    beta_threshold: float | None
    drop_pct: float | None          # Observed drop (None when Polygon unavailable)
    threshold_pct: float | None
    polygon_available: bool
    data_gap_severity: str          # NONE | PARTIAL | MAJOR | CRITICAL
    market_open: bool


# ---------------------------------------------------------------------------
# Full evaluation result
# ---------------------------------------------------------------------------


class Framework19Result(BaseModel):
    """Full Framework 19 evaluation result — session-level.

    ZERO caching — Polygon.io is called fresh on every evaluation.
    Consuming frameworks (F3, F4) use Framework19SimpleResult instead.

    F19 is the ONLY source for f19_active in the system.
    """

    # Core kill-switch state
    f19_status: F19Status
    f19_active: bool | None        # None = UNKNOWN

    # Alert severity
    severity: F19Severity | None

    # NVDA drop detail
    nvda_drop: NVDADropDetail

    # Session state
    market_open: bool
    session_date: str
    triggered_at: str | None        # ISO timestamp when kill switch first fired

    # Downstream blocking state
    all_ai_buys_blocked: bool
    high_beta_market_orders_blocked: bool

    # Affected holdings
    beta_threshold: float | None
    affected_holdings: list[AffectedHolding]

    # Paused orders
    paused_orders_count: int
    paused_orders: list[PausedOrder]

    # Upstream data sources
    regime: str | None              # from Framework 2 — never computed here
    regime_available: bool
    polygon_available: bool

    # Alert state
    alert_sent: bool
    alert_sent_at: str | None

    # Data quality
    data_gap_severity: str          # NONE | PARTIAL | MAJOR | CRITICAL
    warning_messages: list[str]

    # Meta — no cache_hit field because F19 is never cached
    last_updated: str
