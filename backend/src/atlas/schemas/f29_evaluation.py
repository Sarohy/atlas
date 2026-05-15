"""Pydantic schemas for Framework 29 — Three-Path Entry Classifier.

This module contains the new per-ticker evaluation schema that replaces the
flat 4-signal AND-gate counter.  The old Framework29Result schema (in
framework29.py) is kept intact for backward compatibility with existing
consumers of /api/v1/framework29/signals.

Architecture: three-path classifier with a regime precondition hard-stop.
  Regime precondition → [WASHOUT | CATALYST_VALIDATED | DISCRETIONARY]

Open questions surfaced via CLIENT_CLARIFICATION_REQUIRED comments below.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class F29EntryType(StrEnum):
    WASHOUT = "WASHOUT"
    CATALYST_VALIDATED = "CATALYST_VALIDATED"
    DISCRETIONARY = "DISCRETIONARY"
    BLOCKED_BY_REGIME = "BLOCKED_BY_REGIME"
    UNAVAILABLE = "UNAVAILABLE"


class F29GateStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Condition primitives
# ---------------------------------------------------------------------------

# CLIENT_CLARIFICATION_REQUIRED: The `met` field uses a tri-state
# (True | False | "UNAVAILABLE") to distinguish confirmed conditions,
# failed conditions, and conditions where data was unavailable.
# Downstream UI must render UNAVAILABLE as amber (not red), per spec.
ConditionMet = bool | Literal["UNAVAILABLE"]


class F29ConditionResult(BaseModel):
    """Result of evaluating a single condition within a path."""

    id: str
    met: ConditionMet
    value: float | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Regime precondition
# ---------------------------------------------------------------------------


class F29RegimePrecondition(BaseModel):
    """Result of the regime hard-stop check (Step 1).

    CLIENT_CLARIFICATION_REQUIRED (#1): PRE_CATALYST regime is mentioned in
    client notes as permitted but is not in the v7.3.4 regime taxonomy
    (CLEAR / SOFT_CAUTION / CAUTION / CRISIS_HALT).  Current behaviour:
    PRE_CATALYST → REGIME_UNDEFINED → gate_status=UNAVAILABLE.
    """

    regime: str
    passed: bool
    reason: str | None = None
    regime_undefined_flag: bool = False


# ---------------------------------------------------------------------------
# Path A — WASHOUT
# ---------------------------------------------------------------------------


class F29WashoutEvaluation(BaseModel):
    """Evaluation result for the WASHOUT path (Path A).

    Both conditions must be True for matched=True.
    If either source is unavailable, matched=False and the classifier
    falls through to Path B (CATALYST_VALIDATED).
    """

    matched: bool
    session_change_pct: float | None = None
    f4_score: float | None = None
    conditions: list[F29ConditionResult]
    data_gaps: list[str]


# ---------------------------------------------------------------------------
# Path B — CATALYST_VALIDATED
# ---------------------------------------------------------------------------


class F29CatalystValidatedEvaluation(BaseModel):
    """Evaluation result for the CATALYST_VALIDATED path (Path B).

    Requires position_held AND score_tier_pass AND ≥2 sub-conditions met.
    UNAVAILABLE sub-conditions count as not-met for the 2-of-3 threshold.

    CLIENT_CLARIFICATION_REQUIRED (#4): 13F data source not wired.
    CLIENT_CLARIFICATION_REQUIRED (#5): Analyst PT raise + management meeting
      linkage not available — current feeds don't link these events.
    """

    matched: bool
    position_held: ConditionMet
    score_tier_pass: ConditionMet
    sub_conditions: list[F29ConditionResult]
    sub_conditions_met_count: int
    data_gaps: list[str]


# ---------------------------------------------------------------------------
# Path C — DISCRETIONARY
# ---------------------------------------------------------------------------


class F29DiscretionarySignal(BaseModel):
    """One macro signal within the DISCRETIONARY path evaluation."""

    id: str
    label: str
    met: ConditionMet
    value: float | None = None


class F29DiscretionaryEvaluation(BaseModel):
    """Evaluation result for the DISCRETIONARY path (Path C).

    CLIENT_CLARIFICATION_REQUIRED (#2): Threshold of 2-of-3 is inferred from
    the original 3-of-5 ratio after removing S2 (oil) and S5 (regime, now a
    precondition).  threshold_inferred=True flags this for operator review.

    CLIENT_CLARIFICATION_REQUIRED (#3): Tie-breaking — if WASHOUT and
    CATALYST_VALIDATED both match, WASHOUT wins (more time-sensitive).
    The alternate path status is logged in the decision trace.
    """

    signals: list[F29DiscretionarySignal]
    signals_met: int
    signals_unavailable: int
    threshold: int = 2
    threshold_inferred: bool = True


# ---------------------------------------------------------------------------
# Full evaluation result
# ---------------------------------------------------------------------------


class F29Evaluation(BaseModel):
    """Complete Framework 29 evaluation for a single ticker (new classifier schema).

    This is the response schema for GET /api/v1/framework29/evaluate/{ticker}.
    It replaces the flat counter for per-ticker decisions.  The portfolio-level
    /api/v1/framework29/signals endpoint (Framework29Result) is kept intact
    for backward compatibility.
    """

    framework_id: Literal[29] = 29
    ticker: str
    gate_status: F29GateStatus
    entry_type: F29EntryType
    regime_precondition: F29RegimePrecondition
    washout_evaluation: F29WashoutEvaluation
    catalyst_validated_evaluation: F29CatalystValidatedEvaluation
    discretionary_evaluation: F29DiscretionaryEvaluation | None
    decision_trace_id: str
    evaluated_at: datetime

    # Consolidated data gaps across all paths.
    all_data_gaps: list[str] = Field(default_factory=list)
