"""Pydantic schemas for Section 17 — LEAPS Strategy Module.

LEAPS eligibility is a tristate: True | False | None.
None means required data was unavailable — no eligibility decision is made.

V1 scope: read-only tracking.  Positions may be created manually.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IVAlert(StrEnum):
    """IV-related alert states for LEAPS."""

    NONE = "NONE"
    IV_HIGH_ALERT = "IV_HIGH_ALERT"
    IV_COMPRESSION_SIGNAL = "IV_COMPRESSION_SIGNAL"
    IV_EARNINGS_PROXIMITY = "IV_EARNINGS_PROXIMITY"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class EntryConditionStatus(StrEnum):
    """Status of a LEAPS entry condition."""

    CONFIRMED = "CONFIRMED"
    NOT_MET = "NOT_MET"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EntryCondition(BaseModel):
    """One of the three LEAPS entry conditions."""

    condition_name: str
    status: EntryConditionStatus
    met: bool | None
    detail: str | None = None


class LeapsEligibility(BaseModel):
    """LEAPS eligibility result for a specific ticker.

    leaps_eligible is a tristate:
      True  — all required checks passed
      False — one or more checks failed (blocked)
      None  — required data unavailable; decision deferred
    """

    ticker: str
    leaps_eligible: bool | None
    eligibility_undetermined: bool

    score: int | None
    tier: str | None
    flow_confirmed: bool | None

    regime_state: str | None
    regime_clears_leaps: bool | None

    gate_f7_active: bool | None
    gate_f29_passed: bool | None
    gate_f30_permits_leaps: bool | None

    iv_current: float | None
    iv_percentile: float | None
    iv_blocked: bool | None
    iv_alert: IVAlert

    entry_conditions: list[EntryCondition]
    conditions_met: int
    conditions_required: int

    block_reasons: list[str]
    warning_messages: list[str]

    data_age_minutes: int
    cache_hit: bool


class LeapsPosition(BaseModel):
    """A tracked LEAPS position (read-only V1)."""

    id: int
    ticker: str
    option_symbol: str
    expiration_date: str
    strike_price: float
    option_type: str
    contracts: int
    entry_price: float
    current_price: float | None
    current_value: float | None
    theta_daily: float | None
    iv_at_entry: float | None
    iv_current: float | None
    pnl_usd: float | None
    pnl_pct: float | None
    days_to_expiry: int | None
    status: str
    notes: str | None = None


class LeapsBucketStatus(BaseModel):
    """Aggregate LEAPS bucket utilisation."""

    total_deployed_usd: float
    total_deployed_pct: float
    total_cap_pct: float
    positions_count: int
    bucket_available_pct: float
    bucket_available_usd: float | None
    warning_messages: list[str]
