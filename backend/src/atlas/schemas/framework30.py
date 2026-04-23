"""Pydantic schemas for Framework 30 — Max Drawdown Gate.

Framework 30 calculates portfolio drawdown from the 90-day peak NAV and
gates all ADD signals when drawdown exceeds 15%.  LEAPS have a carve-out:
allowed up to 0.5% NAV per position during 15-25% drawdown.
At 25% drawdown (HARD_HALT) everything stops including the LEAPS carve-out.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DrawdownState(StrEnum):
    """Four possible portfolio drawdown states."""

    NORMAL = "NORMAL"
    CARVEOUT = "CARVEOUT"
    HARD_HALT = "HARD_HALT"
    UNKNOWN = "UNKNOWN"


class PositionNavItem(BaseModel):
    """Per-position NAV contribution detail."""

    ticker: str
    shares: float | None
    price: float | None
    price_stale: bool
    price_age_min: int | None = None
    value_usd: float | None
    excluded: bool
    exclude_reason: str | None = None


class Framework30Result(BaseModel):
    """Full Framework 30 drawdown gate evaluation."""

    current_nav: float | None
    peak_nav_90d: float | None
    peak_nav_date: str | None
    drawdown_pct: float | None
    drawdown_usd: float | None
    drawdown_state: DrawdownState

    adds_permitted: bool
    leaps_permitted: bool
    leaps_position_cap_pct: float | None
    all_signals_halted: bool
    hard_halt_active: bool
    limit_orders_cancel: bool

    recovery_active: bool | None
    recovery_start_date: str | None
    recovery_days_elapsed: int | None
    recovery_days_remaining: int | None
    sizing_multiplier: float | None

    position_nav_items: list[PositionNavItem]
    stale_positions: list[str]
    missing_positions: list[str]

    nav_data_complete: bool
    peak_data_source: str
    data_age_minutes: int
    warning_messages: list[str]
    cache_hit: bool


class Framework30DrawdownState(BaseModel):
    """Lightweight drawdown state — consumed by LEAPS service and Framework 4."""

    drawdown_state: DrawdownState
    drawdown_pct: float | None
    adds_permitted: bool
    leaps_permitted: bool
    leaps_position_cap_pct: float | None
    sizing_multiplier: float | None
    hard_halt_active: bool
    data_complete: bool


class HardHaltConfirmRequest(BaseModel):
    """Body for POST /framework30/hard-halt/confirm."""

    confirmed: bool
    reason: str = Field(min_length=1)
