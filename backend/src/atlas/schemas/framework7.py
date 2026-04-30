"""Pydantic schema for Framework 7 — Earnings Gate Rule response."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class EarningsGate(BaseModel):
    """Framework 7 Earnings Gate evaluation result.

    Returned by GET /api/v1/framework7/{ticker}.
    """

    # ── Ticker identification ──────────────────────────────────────────────
    ticker: str

    # ── Earnings date information ──────────────────────────────────────────
    # None when no upcoming earnings found within the 3-month horizon.
    earnings_date: date | None = None

    # None when earnings_date is None.
    gate_close_date: date | None = None

    # Calendar days from today to earnings_date. None when no earnings found.
    days_to_earnings: int | None = None

    # ── Gate state ────────────────────────────────────────────────────────
    gate_active: bool

    # ── Scores and flags ──────────────────────────────────────────────────
    # Framework 1 final score (0-100), regime-adjusted by F2.
    final_score: int = Field(ge=0, le=100)

    # True when recent significant insider selling detected (Framework 8).
    insider_flag: bool

    # ── Decision output ───────────────────────────────────────────────────
    # True when the investor is permitted to add to the position.
    can_add: bool

    # Maximum fraction of target weight that may be deployed.
    # 0.0 = no adds allowed, 0.5 = 50% cap, 1.0 = fully open.
    size_cap: float = Field(ge=0.0, le=1.0)

    # Four possible values: OPEN | CLOSED | 50% CAP | DOUBLE BLOCKED
    status: str

    # Human-readable explanation of the current gate state.
    message: str

    # ── Geopolitical context (Framework 17 integration) ───────────────────
    # True when F17 flag is ACTIVE — oil-exposed positions need elevated
    # scrutiny in morning briefing. Set by Framework 17 service, not by F7.
    oil_priority_elevated: bool = Field(
        default=False,
        description="True when Framework 17 reports an active geopolitical risk.",
    )
