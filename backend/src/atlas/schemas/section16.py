"""Pydantic schemas for Section 16 — Entry Gatekeeper.

Section 16 is the entry-decision pipeline.  It evaluates 4 rules per ticker
(Track A) or 2 rules + parabolic exception (Track B), plus an optional
override path (Track A only).  When the gate PASSES, control hands off to
Framework 12 for sizing.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums (string literals — kept simple for JSON serialisation).
# ---------------------------------------------------------------------------

TrackType = Literal["TRACK_A", "TRACK_B", "UNASSIGNED"]
GateResult = Literal["PASS", "FAIL", "UNKNOWN"]
Rule1Priority = Literal["PRIORITY_1", "PRIORITY_2", "PRIORITY_3", "NO_MATCH"]


# ---------------------------------------------------------------------------
# Per-rule result models — each rule returns its own structured verdict.
# ---------------------------------------------------------------------------


class Rule1Result(BaseModel):
    """Rule 1 — Catalyst conviction gate (priority-based signal threshold)."""

    result: GateResult
    priority_matched: Rule1Priority
    dark_pool_usd: float | None = None
    flow_usd: float | None = None
    days_to_earnings: int | None = None
    threshold_dark_pool_usd: float | None = None
    threshold_flow_usd: float | None = None
    reason: str


class Rule2Result(BaseModel):
    """Rule 2 — Catalyst horizon (must have earnings/catalyst within window)."""

    result: GateResult
    days_to_earnings: int | None = None
    earnings_date: date | None = None
    catalyst_max_days: int
    parabolic_window: bool = False
    reason: str


class Rule3Result(BaseModel):
    """Rule 3 — Price-position gate (not near 365d high without a pullback)."""

    result: GateResult
    current_price: float | None = None
    high_365d: float | None = None
    pct_below_high: float | None = None
    near_high_pct_threshold: float
    pullback_pct_required: float
    pullback_pct_actual: float | None = None
    reason: str


class Rule4Result(BaseModel):
    """Rule 4 — Portfolio fit (operator must set fits_portfolio=True today)."""

    result: GateResult
    fit_date: date | None = None
    fits_portfolio: bool | None = None
    set_by: str | None = None
    cluster_gap: str | None = None
    redundancy_check: str | None = None
    reason: str


class OverrideResult(BaseModel):
    """Override evaluation — Track A only.  Bypasses Rule 1 fail."""

    available: bool
    used_in_cycle: bool
    qualifies: bool
    dark_pool_usd: float | None = None
    flow_usd: float | None = None
    threshold_dark_pool_usd: float
    threshold_flow_usd: float
    lookback_days: int
    reason: str


# ---------------------------------------------------------------------------
# Top-level Section 16 result — what every consumer reads.
# ---------------------------------------------------------------------------


class Section16Result(BaseModel):
    """Entry-gate verdict for a single ticker.

    `gate` is the single source of truth: PASS means hand off to Framework 12.
    """

    ticker: str
    track: TrackType
    gate: GateResult

    rule1: Rule1Result | None = None
    rule2: Rule2Result | None = None
    rule3: Rule3Result | None = None
    rule4: Rule4Result | None = None
    override: OverrideResult | None = None

    # When true, the override (Track A) was used to satisfy Rule 1.
    override_used: bool = False

    evaluated_at: datetime
    notes: str | None = None


# ---------------------------------------------------------------------------
# Request bodies for operator-set state.
# ---------------------------------------------------------------------------


class TrackAssignmentRequest(BaseModel):
    """Body for POST /section16/track/{ticker}."""

    track: Literal["TRACK_A", "TRACK_B"]
    assigned_by: str = Field(min_length=1, max_length=100)
    notes: str | None = None


class Rule4Request(BaseModel):
    """Body for POST /section16/rule4/{ticker}."""

    fits_portfolio: bool
    set_by: str = Field(min_length=1, max_length=100)
    cluster_gap: str | None = None
    redundancy_check: str | None = None
    notes: str | None = None


class OverrideUseRequest(BaseModel):
    """Body for POST /section16/override/{ticker}/use."""

    used_by: str = Field(min_length=1, max_length=100)
    notes: str | None = None
