"""Pydantic schema for Framework 8 — Insider Buying Detector response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Framework8Response(BaseModel):
    """Framework 8 insider activity analysis result.

    Returned by GET /api/v1/framework8/{ticker}.
    """

    ticker: str

    # Additive score bonus from insider buying (0 when no qualifying buys).
    buying_bonus: int = Field(default=0, ge=0)

    # Display-only note when multiple Tier-1 insiders sell without a 10b5-1
    # plan.  Null when no concern detected.  Carries NO scoring impact.
    clustered_selling_note: str | None = None

    # "sec_edgar" | "default"
    source: str
