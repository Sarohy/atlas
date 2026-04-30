"""Pydantic schemas for Framework 17 — Geopolitical Monitor.

GeoFlagState values (stored in DB as strings):
  NONE          — conflict resolved or absent
  DE_ESCALATING — tensions cooling
  ACTIVE        — active geopolitical risk

NOT_SET is a runtime-only state (never stored in DB); it means no flag record
has ever been written by an operator.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class GeoFlagState(str, Enum):
    """Operator-set geopolitical flag state."""

    NONE = "NONE"
    DE_ESCALATING = "DE_ESCALATING"
    ACTIVE = "ACTIVE"
    # Runtime-only: flag has never been set by an operator.
    NOT_SET = "NOT_SET"


class F17Severity(str, Enum):
    """Derived severity based on flag state and current regime."""

    CRITICAL = "CRITICAL"   # ACTIVE flag + CRISIS or CAUTION regime
    HIGH = "HIGH"           # ACTIVE flag + SOFT_CAUTION or regime unavailable
    ELEVATED = "ELEVATED"   # DE_ESCALATING flag
    NONE = "NONE"           # No active geopolitical risk
    UNKNOWN = "UNKNOWN"     # Flag has never been set (NOT_SET)


class Framework17SimpleResult(BaseModel):
    """Lightweight F17 result for consuming frameworks (F2, F3, F7).

    This is the only data structure consuming frameworks should use.
    They NEVER independently read the geopolitical_flag table.
    """

    f17_active: bool | None = Field(
        description="True if geo risk is active; False if resolved; "
        "None if flag has never been set (treated as BLOCKED by all consumers).",
    )
    flag_state: GeoFlagState
    clear_regime_possible: bool = Field(
        description="True when NONE or DE_ESCALATING; False when ACTIVE or NOT_SET.",
    )
    severity: F17Severity
    brent_price: float | None = Field(
        description="Most recent Brent crude close from Polygon.io (USD/barrel).",
    )
    conflict_duration_days: int | None = Field(
        description="Days since conflict_start_date; None if no start date provided.",
    )


class Framework17Result(Framework17SimpleResult):
    """Full F17 evaluation result — returned by GET /api/v1/framework17/status."""

    # Flag metadata
    set_by: str | None = Field(
        default=None,
        description="Operator identifier who last set this flag.",
    )
    set_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when flag was last set.",
    )
    conflict_start_date: date | None = Field(
        default=None,
        description="Operator-provided conflict start date.",
    )
    notes: str | None = Field(
        default=None,
        description="Operator notes from last flag-setting action.",
    )
    session_date: date | None = Field(
        default=None,
        description="Session date this flag applies to.",
    )
    carried_forward: bool = Field(
        default=False,
        description="True when today has no flag row and the previous day's flag was used.",
    )

    # Regime context (from Framework 2)
    regime: str | None = Field(
        default=None,
        description="Current regime from Framework 2: CRISIS HALT | CAUTION | "
        "SOFT CAUTION | CLEAR | None if unavailable.",
    )
    regime_available: bool = Field(
        default=False,
        description="True when Framework 2 regime data was successfully retrieved.",
    )

    # CLEAR regime impact
    clear_regime_blocked: bool = Field(
        default=False,
        description="True when ACTIVE flag prevents CLEAR regime from being reached.",
    )

    # Morning briefing message
    briefing_message: str = Field(
        default="",
        description="Pre-composed morning briefing text for the operator.",
    )
    briefing_urgency: str = Field(
        default="INFO",
        description="One of: URGENT, WARNING, INFO — controls morning briefing alert level.",
    )

    # Data freshness
    cache_hit: bool = Field(default=False)
    data_as_of: datetime | None = Field(
        default=None,
        description="UTC timestamp of when this evaluation was computed.",
    )


class SetFlagRequest(BaseModel):
    """Request body for POST /api/v1/framework17/flag."""

    flag_state: GeoFlagState = Field(
        description="New flag state to set. Must be NONE, DE_ESCALATING, or ACTIVE. "
        "NOT_SET is not accepted as input.",
    )
    set_by: str = Field(
        min_length=1,
        max_length=100,
        description="Operator identifier (username or label).",
    )
    conflict_start_date: date | None = Field(
        default=None,
        description="When the conflict started — required when flag_state=ACTIVE.",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional operator notes.",
    )
    override_reason: str = Field(
        min_length=50,
        description="Justification for this flag change. Minimum 50 characters.",
    )


class FlagHistoryEntry(BaseModel):
    """One row from the geopolitical_flag history query."""

    id: int
    flag_state: GeoFlagState
    set_by: str
    set_at: datetime
    conflict_start_date: date | None
    notes: str | None
    session_date: date
