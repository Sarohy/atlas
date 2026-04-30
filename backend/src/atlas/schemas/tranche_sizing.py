"""Pydantic schemas for the Framework 4 Tranche Sizing endpoint (v7.3.4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SignalDetail(BaseModel):
    """Per-signal confirmation status for the Framework 29 AND gate."""

    model_config = ConfigDict(from_attributes=True)

    signal_index: int = Field(description="Signal index (1-5).")
    name: str = Field(description="Human-readable signal name.")
    confirmed: bool = Field(description="Whether this signal is confirmed.")


class TrancheSizingResponse(BaseModel):
    """Response from the Framework 4 tranche-sizing endpoint (v7.3.4).

    T1  10-15% of available cash  - fires when the initial catalyst is confirmed
    T2  20-25% of available cash  - fires when the regime is CAUTION
    T3  30-40% of available cash  - fires when CLEAR AND AND gate passes (3/5)
    T4  Remaining cash to floor   - fires when Iran Resolution is confirmed

    All tranche values are None when cap_active is True (concentration cap
    suppresses all tranche sizing per Framework 13).
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # Concentration cap (Framework 14 stub)
    cap_active: bool = Field(
        description="True when position weight >= 8% NAV (concentration cap active)."
    )
    tranche_display: bool = Field(
        description=(
            "False when any cap (F14 concentration or F13 beta) suppresses all tranche rows."
        )
    )
    position_weight: float = Field(
        description="Current position weight as a fraction of NAV (e.g. 0.136 = 13.6%)."
    )
    message: str | None = Field(
        default=None,
        description="Human-readable status message; set when a cap is active.",
    )

    # Beta cap (Framework 13)
    beta_cap_active: bool = Field(
        default=False,
        description="True when Framework 13 beta cap is active for this position.",
    )
    beta_cap_reason: str | None = Field(
        default=None,
        description="Human-readable reason when beta_cap_active is True.",
    )

    # AND gate (Framework 29 stub)
    and_gate_active: bool = Field(
        description="True when regime is CLEAR - AND gate applies to T3 and large decisions."
    )
    and_gate_passed: bool = Field(
        description="True when 3 or more of 5 capitulation signals are confirmed."
    )
    signals_confirmed: int = Field(description="Count of AND gate signals confirmed (0-5).")
    signals_detail: list[SignalDetail] = Field(
        description="Per-signal confirmation status for all 5 Framework 29 signals."
    )

    # Tranche values (None when cap_active is True)
    t1: str | None = Field(
        default=None,
        description=(
            "'10-15% of available cash' when initial catalyst is confirmed, "
            "'Blocked' when gate not met, None when cap suppressed."
        ),
    )
    t2: str | None = Field(
        default=None,
        description=(
            "'20-25% of available cash' when Framework 2 regime is CAUTION, "
            "'Blocked' when gate not met, None when cap suppressed."
        ),
    )
    t3: str | None = Field(
        default=None,
        description=(
            "'30-40% of available cash' when CLEAR AND AND gate passes, "
            "'Blocked' when either condition not met, None when cap suppressed."
        ),
    )
    t4: str | None = Field(
        default=None,
        description=(
            "'Remaining cash to floor' when Iran Resolution is confirmed, "
            "'Blocked' when gate not met, None when cap suppressed."
        ),
    )

    # Sequential gate state
    t1_fired: bool = Field(
        default=False,
        description=(
            "True when T1 has fired for this ticker. "
            "T2/T3/T4 are blocked by the sequential gate until T1 fires."
        ),
    )

    # T2 confirmation state (Framework 17 — auto-triggered by price condition)
    t2_fired: bool = Field(
        default=False,
        description=(
            "True when the operator has confirmed the T2 deployment order. "
            "Set via POST /tranche-sizing/{ticker}/confirm-t2."
        ),
    )
    t2_pending: bool = Field(
        default=False,
        description=(
            "True when T2 conditions are met (T1 fired + Brent < $110) but the "
            "operator has not yet confirmed the deployment order. "
            "Signals the UI to surface the auto-trigger confirmation modal."
        ),
    )

    # T3 confirmation state (Framework 17 — auto-triggered by AND gate)
    t3_fired: bool = Field(
        default=False,
        description=(
            "True when the operator has confirmed the T3 deployment order. "
            "Set via POST /tranche-sizing/{ticker}/confirm-t3."
        ),
    )
    t3_pending: bool = Field(
        default=False,
        description=(
            "True when T3 conditions are met (CLEAR regime + AND gate passed) but the "
            "operator has not yet confirmed the deployment order. "
            "Signals the UI to surface the auto-trigger confirmation modal."
        ),
    )

    # Single source of truth for CATALYST display (same value as t1_fired).
    # Both the CATALYST header and T1 row in the UI must read this field.
    catalyst_confirmed: bool = Field(
        default=False,
        description=(
            "True when T1 has fired for this ticker. "
            "Mirrors t1_fired — single source of truth for the CATALYST header display."
        ),
    )

    # ── Framework 18 — 4-Week Trend Gate ────────────────────────────────────
    f18_active: bool | None = Field(
        default=None,
        description=(
            "True when the 4-Week Trend Gate is active, False when clear, "
            "None when SPY data is unavailable."
        ),
    )
    f18_reduction_pct: float | None = Field(
        default=None,
        description=(
            "Reduction percentage from atlas_config when f18_active=True. "
            "Applied by Framework 6 to size_max. Informational here."
        ),
    )
    f18_note: str | None = Field(
        default=None,
        description=(
            "Human-readable note shown on tranche rows when F18 is active or unknown. "
            "E.g. 'Tranche reduced by 50% — F18 trend gate active. 3 consecutive down weeks.'"
        ),
    )

    # ── Framework 19 — NVDA Kill Switch ────────────────────────────────────
    f19_active: bool | None = Field(
        default=None,
        description=(
            "True when NVDA kill switch fired this session, False when clear, "
            "None when Polygon data unavailable. None is treated as BLOCKED."
        ),
    )
    f19_all_ai_buys_blocked: bool = Field(
        default=False,
        description=(
            "True when f19_active=True or f19_active=None (UNKNOWN). "
            "All tranche buy deployments are blocked while kill switch is active."
        ),
    )
    f19_note: str | None = Field(
        default=None,
        description="Human-readable F19 block note shown on tranche rows.",
    )
