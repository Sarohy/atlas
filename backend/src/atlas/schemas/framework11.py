"""Pydantic schemas for Framework 11 — Cash Floor Enforcer.

Framework 11 enforces portfolio cash above the regime-driven floor from
Section 14.1 at all times.  All buy signals are queued (not cancelled) when
the floor is violated.  The GTC aggregate window prevents simultaneous GTC
fills from breaching the floor post-fill.

Floor values by regime (Section 14.1 — never hardcoded):
  CRISIS HALT  → 30 %  (minimum; "30%+" per spec)
  CAUTION      → 20 %
  SOFT CAUTION → 15 %
  CLEAR        → 10 % during first 14 calendar days after transition
               →  8 % after 14 days (settled CLEAR)

If regime is unknown → 30 % conservative default.
If CLEAR but transition date unknown → 10 % conservative default.

GTC proximity threshold: 8 % below market price.
  ≤ 8 % below market  → near-money → counts toward GTC window.
  >  8 % below market → deep-OTM   → exempt from GTC window.

GTC aggregate window:
  window_usd = cash_usd − (1.1 × floor_pct × current_nav)
  (1.1 × safety buffer protects against simultaneous fills pushing cash
  below the floor)
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class F11FloorStatus(StrEnum):
    """Framework 11 floor compliance state."""

    COMPLIANT = "COMPLIANT"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"


class GTCItem(BaseModel):
    """Single open GTC buy order with proximity classification."""

    ticker: str = Field(description="Equity ticker symbol.")
    limit_price: float = Field(description="GTC limit price in USD.")
    quantity: int = Field(description="Number of shares in the order.")
    notional_usd: float = Field(description="limit_price × quantity.")
    current_price: float | None = Field(description="Latest market price from Polygon.io.")
    proximity_pct: float | None = Field(
        description="(current_price − limit_price) / current_price × 100. "
        "≤ 8 % = near-money; > 8 % = deep-OTM / exempt."
    )
    is_near_money: bool | None = Field(description="True when proximity_pct ≤ 8 %.")
    is_exempt: bool | None = Field(
        description="True when proximity_pct > 8 % (deep-OTM; exempt from window)."
    )
    price_missing: bool = Field(description="True when Polygon.io returned no price.")
    price_missing_reason: str | None = Field(
        default=None,
        description="Human-readable reason when price_missing is True.",
    )


class Framework11Result(BaseModel):
    """Full Framework 11 cash floor evaluation result."""

    # ── Core floor status ───────────────────────────────────────────────────
    floor_status: F11FloorStatus = Field(description="COMPLIANT | VIOLATED | UNKNOWN")
    floor_violated: bool | None = Field(
        description="True when cash < floor, False when ≥ floor, "
        "None when required data is unavailable."
    )
    all_buys_blocked: bool = Field(
        description="True when floor is violated OR data is unavailable. "
        "False only when floor_status is COMPLIANT."
    )

    # ── Regime and floor ────────────────────────────────────────────────────
    regime: str | None = Field(description="Regime string from Framework 2.")
    floor_pct: float | None = Field(
        description="Active floor as a percentage (e.g. 15.0 for 15 %)."
    )
    floor_pct_source: str = Field(
        description="Key identifying which rule produced this floor value."
    )
    using_conservative_default: bool = Field(
        description="True when a conservative default floor was applied due to "
        "missing regime data."
    )
    clear_transition_days: int | None = Field(
        description="Days since CLEAR transition date (None when regime is not CLEAR)."
    )

    # ── Portfolio numbers ────────────────────────────────────────────────────
    cash_usd: float | None = Field(description="Cash balance in USD from portfolio_config.")
    cash_pct: float | None = Field(description="cash_usd as a percentage of current_nav.")
    current_nav: float | None = Field(
        description="Current portfolio NAV in USD (from Framework 30 calculation)."
    )

    # ── Floor shortfall / buffer ─────────────────────────────────────────────
    shortfall_pct: float | None = Field(
        description="floor_pct − cash_pct when floor_violated is True."
    )
    shortfall_usd: float | None = Field(
        description="Shortfall in USD when floor_violated is True."
    )
    buffer_pct: float | None = Field(
        description="cash_pct − floor_pct when floor_violated is False."
    )
    buffer_usd: float | None = Field(
        description="Buffer in USD when floor_violated is False."
    )

    # ── GTC aggregate window ─────────────────────────────────────────────────
    gtc_window_usd: float | None = Field(
        description="cash_usd − (1.1 × floor_pct/100 × current_nav). "
        "Maximum safe notional for near-money GTC orders. "
        "Null when cash or NAV is unavailable."
    )
    gtc_window_negative: bool = Field(
        description="True when gtc_window_usd ≤ 0 (no safe GTC capacity)."
    )
    gtc_near_money_total_usd: float | None = Field(
        description="Sum of notional values for all near-money GTC buy orders."
    )
    gtc_oversubscribed: bool | None = Field(
        description="True when near-money GTC total exceeds the window. "
        "None when window could not be calculated."
    )
    gtc_excess_usd: float | None = Field(
        description="Amount by which GTC total exceeds the window when oversubscribed."
    )
    gtc_remaining_usd: float | None = Field(
        description="Remaining window capacity when not oversubscribed."
    )
    gtc_items: list[GTCItem] = Field(
        description="All open GTC buy orders with proximity classification."
    )
    gtc_near_money_count: int = Field(description="Number of near-money GTC orders.")
    gtc_exempt_count: int = Field(
        description="Number of deep-OTM GTC orders exempt from window."
    )
    gtc_price_missing_count: int = Field(
        description="Number of GTC orders where Polygon.io price was unavailable."
    )

    # ── Signal queue ─────────────────────────────────────────────────────────
    queued_signals_count: int = Field(
        description="Number of buy signals currently queued due to F11 floor violation."
    )
    signal_queue: list[dict] = Field(  # type: ignore[type-arg]
        description="List of queued signal records."
    )

    # ── Data source health ────────────────────────────────────────────────────
    f2_available: bool = Field(description="True when regime data was available.")
    f30_available: bool = Field(description="True when NAV data was available.")
    cash_db_available: bool = Field(description="True when cash balance DB was readable.")
    gtc_db_available: bool = Field(description="True when GTC orders table was readable.")

    # ── Metadata ─────────────────────────────────────────────────────────────
    data_gap_severity: str = Field(
        description="NONE | PARTIAL | MAJOR | CRITICAL — severity of missing data."
    )
    warning_messages: list[str] = Field(description="Human-readable warning messages.")
    last_updated: str = Field(description="ISO 8601 UTC timestamp of this evaluation.")
    data_age_minutes: int = Field(
        description="Age of cached result in minutes (0 for fresh evaluations)."
    )
    cache_hit: bool = Field(description="True when result was served from cache.")


class Framework11SimpleResult(BaseModel):
    """Lightweight Framework 11 status for consumption by Framework 4, LEAPS, etc."""

    floor_status: F11FloorStatus
    floor_violated: bool | None
    all_buys_blocked: bool
    floor_pct: float | None
    cash_pct: float | None
    shortfall_usd: float | None
    gtc_window_usd: float | None
    gtc_oversubscribed: bool | None
    data_gap_severity: str


class Framework11QueueResponse(BaseModel):
    """Response for GET /framework11/queue."""

    queued_signals: list[dict]  # type: ignore[type-arg]
    count: int
