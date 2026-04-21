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
        description="False when concentration cap suppresses all tranche rows."
    )
    position_weight: float = Field(
        description="Current position weight as a fraction of NAV (e.g. 0.136 = 13.6%)."
    )
    message: str | None = Field(
        default=None,
        description="Human-readable status message; set when cap is active.",
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
