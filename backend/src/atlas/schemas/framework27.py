"""Pydantic schemas for Framework 27 — Supply Chain Contagion Map."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ContagionRuleResult(BaseModel):
    """Result for a single contagion rule evaluation."""

    rule_id: int
    ticker: str
    primary_risk: str
    secondary_exposure: str
    contagion_trigger_type: str
    trigger_condition: str
    triggered: bool = Field(
        description="True if current conditions exceed the trigger threshold.",
    )
    trigger_reason: str = Field(
        default="",
        description="Explanation of why this trigger fired or did not fire.",
    )
    action_on_trigger: str


class Framework27Result(BaseModel):
    """Full F27 evaluation result — returned by GET /api/v1/framework27/contagion."""

    f17_active: bool | None = Field(
        description="F17 flag state (None = never set, treated as BLOCKED).",
    )
    rules_evaluated: int = Field(
        description="Total number of active contagion rules evaluated.",
    )
    rules_triggered: int = Field(
        description="Number of rules that fired.",
    )
    triggered_rules: list[ContagionRuleResult] = Field(
        default_factory=list,
        description="Rules that are currently triggered.",
    )
    all_rules: list[ContagionRuleResult] = Field(
        default_factory=list,
        description="All evaluated rules (triggered and not triggered).",
    )

    # Operator-confirmed flags active this session
    asia_freight_flagged: bool = Field(
        default=False,
        description="Operator has confirmed Asia freight disruption this session.",
    )
    metals_disruption_flagged: bool = Field(
        default=False,
        description="Operator has confirmed metals supply disruption this session.",
    )
    indium_disruption_flagged: bool = Field(
        default=False,
        description="Operator has confirmed indium supply disruption this session.",
    )

    # Brent and duration context passed from F17
    brent_price: float | None = None
    conflict_duration_days: int | None = None

    cache_hit: bool = False
    data_as_of: datetime | None = None


class ManualFlagRequest(BaseModel):
    """Request body for POST /api/v1/framework27/contagion/manual-flag."""

    trigger_type: str = Field(
        description="One of: ASIA_FREIGHT_DISRUPTION_PCT, METALS_DISRUPTION, "
        "INDIUM_SUPPLY_DISRUPTION",
    )
    flagged_by: str = Field(
        min_length=1,
        max_length=100,
        description="Operator identifier.",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional operator notes.",
    )
    override_reason: str = Field(
        min_length=50,
        description="Justification for flagging this disruption. Minimum 50 characters.",
    )
