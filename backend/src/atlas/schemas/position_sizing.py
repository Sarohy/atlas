"""Pydantic schemas for the Framework 3 Position Sizing endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PositionSizingResponse(BaseModel):
    """Response from the Framework 3 position-sizing endpoint.

    Score-to-action map (v7.3.5):
      >= 85       T1_ELITE    — Core position, LEAPS eligible, 5-10% NAV
      80-84       T1          — Core position, 2-4% NAV
      70-79       T2          — GTC adds permitted, 0.5-1.5% NAV
      50-69       T3          — Small speculative position, 0-0.5% NAV
      < 50        BELOW_GATE  — Exit rules active (see Framework 16)
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    conviction_score: int = Field(
        ge=0,
        le=100,
        description="Framework 1 conviction score used as input (0-100).",
    )
    tier: str = Field(
        description=(
            "Position tier: 'T1_ELITE' | 'T1' | 'T2' | 'T3' | 'BELOW_GATE'."
        ),
    )
    action: str = Field(description="Short action label for the position tier.")
    grey_zone: bool = Field(
        description="Retained for backward compatibility — always False.",
    )
    consensus_required: bool = Field(
        description="Retained for backward compatibility — always False.",
    )
    trigger_exit_rules: bool = Field(
        description="True for BELOW_GATE tier — see Framework 16 for exit rules.",
    )
    adds_permitted: bool = Field(
        description=("True when new adds are permitted given tier and cap state."),
    )
    leaps_eligible: bool = Field(
        description="True for T1_ELITE positions without a concentration cap block.",
    )
    display_message: str = Field(
        description="Human-readable guidance sentence for the current position state.",
    )
    consensus_confirmed: bool = Field(
        description="Retained for backward compatibility — always False.",
    )
