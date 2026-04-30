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


class LeapsExpiryGuidance(BaseModel):
    """Static expiry and strike preference guidance for LEAPS positions."""

    preferred_expiries: list[str]
    """Preferred expiration months, e.g. ['Jan 2027', 'Jan 2028']."""

    otm_pct_low: float
    """Lower end of OTM strike range as a percentage (e.g. 10.0 = 10% OTM)."""

    otm_pct_high: float
    """Upper end of OTM strike range as a percentage (e.g. 20.0 = 20% OTM)."""


class SizeGuidanceSchema(BaseModel):
    """Per-name LEAPS size guidance (mirrors framework33_service.SizeGuidance)."""

    standard_max_pct: float
    """Maximum allocation per name as % of NAV."""

    baseline_pct: float
    """Lower end of suggested baseline range per name as % of NAV."""

    baseline_max_pct: float
    """Upper end of suggested baseline range per name as % of NAV (spec: 0.3-0.75%)."""

    carveout_active: bool
    """True when F30 drawdown gate forces the 0.5% carveout cap."""

    data_missing: bool
    """True when F30 gate state was unknown; conservative cap was applied."""


def _default_expiry_guidance() -> LeapsExpiryGuidance:
    """Static expiry guidance from F10 spec: Jan 2027 / Jan 2028, 10-20% OTM."""
    return LeapsExpiryGuidance(
        preferred_expiries=["Jan 2027", "Jan 2028"],
        otm_pct_low=10.0,
        otm_pct_high=20.0,
    )


def _default_size_guidance() -> SizeGuidanceSchema:
    """Standard sizing (no F30 gate active): 0.3-0.75% baseline, 1.0% max."""
    return SizeGuidanceSchema(
        standard_max_pct=1.0,
        baseline_pct=0.3,
        baseline_max_pct=0.75,
        carveout_active=False,
        data_missing=False,
    )


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

    # --- Post-catalyst IV wait (spec: wait 5-7 days after earnings for IV compression) ---
    iv_catalyst_wait_days_remaining: int | None = None
    """Days remaining in the 7-day post-earnings IV compression wait window.
    None when no earnings date is available. 0 when wait is over.
    """

    # --- Gap-day entry block (spec: never buy LEAPS into a gap) ---
    gap_detected: bool | None = None
    """True when today's open gapped from the prior close by ≥ 2%.
    None when price data is unavailable.
    """

    entry_conditions: list[EntryCondition]
    conditions_met: int
    conditions_required: int

    block_reasons: list[str]
    warning_messages: list[str]

    # --- Expiry and sizing guidance ---
    expiry_guidance: LeapsExpiryGuidance = Field(
        default_factory=_default_expiry_guidance,
    )
    """Static expiry preference: Jan 2027 / Jan 2028, 10-20% OTM strikes."""

    size_guidance: SizeGuidanceSchema = Field(
        default_factory=_default_size_guidance,
    )
    """Per-name position sizing guidance based on F30 drawdown gate state."""

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
