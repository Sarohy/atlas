"""Pydantic schemas for the Framework 3 Position Sizing endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PositionSizingResponse(BaseModel):
    """Response from the Framework 3 position-sizing endpoint.

    Maps a Framework 1 conviction score to a human-readable position action
    and a descriptive instruction string.

    Score-to-action map (Factor_Mapping_Guide §Framework3):
      > 90        MAXIMUM POSITION      — Add on every dip
      80 – 90     HOLD FULL             — Eligible for adds
      70 – 79     HOLD                  — No new adds
      60 – 69     REDUCE 25-50%         — Reduce 25-50%
      55 – 59     REDUCE AGGRESSIVELY   — Reduce aggressively
      < 55        EXIT                  — Exit immediately
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    conviction_score: int = Field(
        ge=0,
        le=100,
        description="Framework 1 conviction score used as input (0-100).",
    )
    action: str = Field(
        description=(
            "Position action derived from the conviction score: "
            "'MAXIMUM POSITION' | 'HOLD FULL' | 'HOLD' | "
            "'REDUCE 25-50%' | 'REDUCE AGGRESSIVELY' | 'EXIT'."
        ),
    )
    instruction: str = Field(
        description="Human-readable instruction for the action.",
    )
