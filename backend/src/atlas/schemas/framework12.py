"""Pydantic schemas for Framework 12 — Decision Matrix sizing.

Framework 12 only runs after Section 16 returns gate=PASS.  It chooses the
highest-priority matching row from the framework12_decision_matrix table and
returns the recommended USD position size based on live NAV from F30.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Framework12Status = Literal["SIZED", "WATCHLIST", "BLOCKED", "UNKNOWN"]


class DecisionMatrixRow(BaseModel):
    """One priority row from the decision matrix."""

    priority_code: str
    priority_label: str
    track: str | None = None
    earnings_max_days: int | None = None
    earnings_min_days: int | None = None
    override_required: bool
    underweight_required: bool
    strong_flow_required: bool
    size_min_pct: float
    size_max_pct: float
    timing_rule: str
    is_watchlist_only: bool
    priority_order: int
    active: bool


class Framework12Result(BaseModel):
    """Sizing verdict for a ticker that has cleared Section 16."""

    ticker: str
    status: Framework12Status

    # The decision-matrix row that drove the sizing (None if BLOCKED).
    matched_row: DecisionMatrixRow | None = None

    # Live NAV from Framework 30 at the time of evaluation.
    current_nav_usd: float | None = None

    # Recommended USD position size range — derived from row pct + NAV.
    size_min_usd: float | None = None
    size_max_usd: float | None = None

    # Operator-facing timing instruction copied from the matched row.
    timing_rule: str | None = None

    # When Section 16 did not pass, this carries the reason.
    blocked_reason: str | None = None

    evaluated_at: datetime
