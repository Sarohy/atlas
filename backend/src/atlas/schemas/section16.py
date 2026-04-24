"""Pydantic v2 request/response schemas for Section 16 Exit Rules.

All schemas are pure — no imports from models or services.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Rule 16.1 — Score-Based Exit
# ---------------------------------------------------------------------------

# Valid status values for Rule 16.1.
Rule161Status = Literal[
    "CLEAR",
    "CYCLE_ONE",
    "CYCLE_ONE_PAUSED",
    "CYCLE_TWO",
    "DEFERRED",
    "TRIM_TRIGGERED",
    "FULL_EXIT_TRIGGERED",
    "UNKNOWN",
]


class Rule161Result(BaseModel):
    """Result of the Rule 16.1 two-cycle score-based exit evaluation."""

    status: Rule161Status
    cycle_count: int = Field(ge=0, le=2)
    trim_triggered: bool
    full_exit_triggered: bool

    # Set when full_exit_triggered is True.
    exit_window_trading_days: int | None = None

    # Set when trim_triggered is True.
    trim_window_trading_days: int | None = None
    trim_pct: Decimal | None = None

    # Set when status is DEFERRED.
    deferred_reason: str | None = None
    deferred_until: date | None = None

    # Set when reconciliation is pending.
    reconciliation_pending: bool = False
    claude_score: Decimal | None = None
    grok_score: Decimal | None = None
    score_gap: Decimal | None = None

    # Score that triggered the current cycle state.
    triggering_score: Decimal | None = None
    triggering_date: date | None = None

    data_available: bool = True
    missing_sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule 16.2 — Gap-Down
# ---------------------------------------------------------------------------

GapDownStatus = Literal["CLEAR", "HOLDING", "RESCORED", "RESOLVED", "UNKNOWN"]


class Rule162Result(BaseModel):
    """Result of the Rule 16.2 gap-down evaluation."""

    gap_triggered: bool
    status: GapDownStatus

    # Set when gap_triggered is True.
    gap_down_pct: Decimal | None = None
    prev_close: Decimal | None = None
    open_price: Decimal | None = None
    event_date: date | None = None
    hold_until: datetime | None = None
    rescore_at: datetime | None = None

    # Set after rescore.
    rescore_score: Decimal | None = None
    resolved_at: datetime | None = None

    data_available: bool = True
    missing_sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule 16.3 — Appreciation Trim
# ---------------------------------------------------------------------------

AppreciationStatus = Literal[
    "CLEAR", "NO_NEW_CAPITAL", "CONSIDER_TRIM", "UNKNOWN"
]


class Rule163Result(BaseModel):
    """Result of the Rule 16.3 appreciation/concentration trim evaluation."""

    status: AppreciationStatus
    no_new_capital: bool
    consider_trim: bool

    # Position sizing context.
    position_pct_of_nav: Decimal | None = None
    position_value: Decimal | None = None
    total_nav: Decimal | None = None
    trim_pct: Decimal | None = None

    data_available: bool = True
    missing_sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule 16.4 — Put Protection
# ---------------------------------------------------------------------------

PutProtectionStatus = Literal[
    "PUT_PROTECTION_RECOMMENDED", "NOT_TRIGGERED", "UNKNOWN"
]


class Rule164ConditionDetail(BaseModel):
    """Pass/fail detail for a single Rule 16.4 condition."""

    condition_number: int
    description: str
    met: bool | None  # None when data unavailable
    value: str | None = None
    threshold: str | None = None


class Rule164Result(BaseModel):
    """Result of the Rule 16.4 put-protection evaluation."""

    recommend_puts: bool | None  # None when data incomplete
    status: PutProtectionStatus
    conditions_met: int
    conditions: list[Rule164ConditionDetail]

    data_available: bool = True
    missing_sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level Section 16 result
# ---------------------------------------------------------------------------

Section16OverallStatus = Literal[
    "ALL_CLEAR", "EXIT_ACTIVE", "PARTIAL_DATA", "UNKNOWN"
]


class Section16Result(BaseModel):
    """Full Section 16 evaluation result for a single ticker."""

    ticker: str
    available: bool = True  # F12 checks this field
    overall_status: Section16OverallStatus

    rule_161: Rule161Result
    rule_162: Rule162Result
    rule_163: Rule163Result
    rule_164: Rule164Result

    # True when any rule has fired an exit or put-protection signal.
    any_exit_signal: bool

    # Human override suppresses all automated signals.
    override_active: bool = False
    override_reason: str | None = None
    override_set_by: str | None = None
    override_set_at: datetime | None = None

    evaluated_at: datetime


class Section16SimpleResult(BaseModel):
    """Lightweight result for F12 integration — available + exit_active only."""

    available: bool = True
    exit_rule_active: bool | None  # None when status is UNKNOWN
    overall_status: Section16OverallStatus
    ticker: str


class ActiveCycleEntry(BaseModel):
    """One row in the active-cycles portfolio summary."""

    ticker: str
    cycle_status: str
    cycle_one_date: date | None
    cycle_one_score: Decimal | None
    trim_triggered: bool
    full_exit_triggered: bool
    deferred_until: date | None
    override_active: bool


class ActiveCyclesSummary(BaseModel):
    """All tickers with non-CLEAR exit rule cycles."""

    cycles: list[ActiveCycleEntry]
    total_active: int


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

# Minimum override reason length — must be substantive.
_OVERRIDE_REASON_MIN_LEN = 50


class OverrideRequest(BaseModel):
    """Request body for POST /section16/override/{ticker}."""

    reason: str = Field(
        min_length=_OVERRIDE_REASON_MIN_LEN,
        description=(
            f"Mandatory justification for the override — "
            f"minimum {_OVERRIDE_REASON_MIN_LEN} characters."
        ),
    )
    set_by: str = Field(min_length=1, description="Operator identifier.")


class GrokScoreRequest(BaseModel):
    """Request body for POST /section16/grok-score/{ticker}."""

    score: Decimal = Field(ge=0, le=100, description="Grok conviction score 0-100.")
    score_date: date
    entered_by: str = Field(min_length=1)
    notes: str | None = None


class ResolveGapDownRequest(BaseModel):
    """Request body for PUT /section16/gap-down/{id}/resolve."""

    rescore_score: Decimal | None = Field(
        default=None, ge=0, le=100, description="Optional rescore conviction score."
    )
    notes: str | None = None
