"""Pydantic schemas for the Framework 4 Tranche Sizing endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrancheSizingResponse(BaseModel):
    """Response from the Framework 4 tranche-sizing endpoint.

    Maps three external signals to four cash-deployment tranches (T1–T4).

    T1  10-15% of available cash  — fires when the initial catalyst is confirmed
    T2  20-25% of available cash  — fires when the regime is CAUTION
    T3  30-40% of available cash  — fires when the regime is CLEAR
    T4  Remaining cash to floor   — fires when Iran Resolution is confirmed
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    t1: str = Field(
        description=(
            "'10-15% of available cash' when initial catalyst is confirmed, "
            "otherwise 'Blocked'."
        )
    )
    t2: str = Field(
        description=(
            "'20-25% of available cash' when Framework 2 regime is CAUTION, "
            "otherwise 'Blocked'."
        )
    )
    t3: str = Field(
        description=(
            "'30-40% of available cash' when Framework 2 regime is CLEAR, "
            "otherwise 'Blocked'."
        )
    )
    t4: str = Field(
        description=(
            "'Remaining cash to floor' when Iran Resolution is confirmed, "
            "otherwise 'Blocked'."
        )
    )
