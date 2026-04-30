"""Pydantic schemas for the Framework 3 Position Sizing endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PositionSizingResponse(BaseModel):
    """Response from the Framework 3 position-sizing endpoint.

    Score-to-action map (v7.3.4):
      >= 85       TIER_1         — Core position, LEAPS eligible
      78 - 84     TIER_2_GREY    - Grey zone, 3-model consensus required
      70 - 77     TIER_2         - GTC adds permitted
      55 - 69     TIER_3         - Small position only
      < 55        WATCHLIST      — Exit rules active (see Framework 16)
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
            "Position tier: 'TIER_1' | 'TIER_2_GREY' | 'TIER_2' | 'TIER_3' | 'WATCHLIST'."
        ),
    )
    action: str = Field(description="Short action label for the position tier.")
    grey_zone: bool = Field(
        description="True when the score falls in the 78-84 consensus-required band.",
    )
    consensus_required: bool = Field(
        description="True when 3-model consensus is needed before adding.",
    )
    trigger_exit_rules: bool = Field(
        description="True for WATCHLIST tier — see Framework 16 for exit rules.",
    )
    adds_permitted: bool = Field(
        description=("True when new adds are permitted given tier, cap, and consensus state."),
    )
    leaps_eligible: bool = Field(
        description="True for TIER_1 positions without a concentration cap block.",
    )
    display_message: str = Field(
        description="Human-readable guidance sentence for the current position state.",
    )
    consensus_confirmed: bool = Field(
        description=("True when the 3-model consensus gate has been confirmed for this ticker."),
    )
