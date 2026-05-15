"""Pydantic schemas for Framework 29 - Capitulation / Re-Entry AND Gate.

Framework 29 monitors 4 market signals and fires a GREEN LIGHT deploy alert
when 3 of 4 are confirmed.  CRISIS HALT is a separate hard stop that blocks
all LEAPS regardless of entry type.  It is portfolio-level (no per-ticker state).

Signals (current spec):
  1. VIX touches prior regime-high then declines for ≥3 consecutive sessions
  2. Regime modifier is CAUTION (market stress confirms capitulation dynamics)
  3. Put/call ratio spikes above 1.3 then reverses downward
  4. % S&P 500 stocks above 50-DMA falls below 30% then recovers

Gate rule: 3 of 4 confirmed = GREEN LIGHT
UNAVAILABLE signals do NOT count toward the 3 required.
CRISIS HALT: gate_status = "CRISIS_HALT_BLOCKED" and crisis_halt_blocked = True.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SignalStatus(StrEnum):
    """Evaluation state for a single AND gate signal."""

    CONFIRMED = "CONFIRMED"
    NOT_MET = "NOT_MET"
    UNAVAILABLE = "UNAVAILABLE"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class Framework29Signal(BaseModel):
    """One of the five capitulation signals."""

    signal_number: int = Field(ge=1, le=4)
    signal_name: str
    status: SignalStatus
    confirmed: bool
    data_missing: bool
    missing_reason: str | None = None
    current_values: dict[str, object] = Field(default_factory=dict)
    threshold: dict[str, object] = Field(default_factory=dict)


class Framework29Result(BaseModel):
    """Full Framework 29 evaluation result."""

    signals_confirmed: int
    signals_unavailable: int
    and_gate_passed: bool
    gate_status: str
    gate_message: str
    signals: list[Framework29Signal]
    data_gap_severity: str
    warning_messages: list[str]
    last_updated: str
    data_age_minutes: int
    cache_hit: bool
    crisis_halt_blocked: bool = False


class Framework29GateStatus(BaseModel):
    """Lightweight gate status — consumed by Framework 4 and Section 17 LEAPS."""

    and_gate_passed: bool
    signals_confirmed: int
    signals_unavailable: int
    gate_status: str
    data_gap_severity: str
    crisis_halt_blocked: bool = False


class ManualConfirmRequest(BaseModel):
    """Body for POST /framework29/signals/confirm."""

    signal: int = Field(ge=1, le=4)
    confirmed: bool
    reason: str = Field(min_length=1)
