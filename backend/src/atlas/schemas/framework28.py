"""Pydantic schemas for Framework 28 — War Duration Ladder."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LadderTierResult(BaseModel):
    """A single war duration ladder tier from the DB."""

    tier_order: int
    duration_min_days: int
    duration_max_days: int | None = None
    brent_range_low: float
    brent_range_high: float | None = None
    fed_implication: str
    portfolio_action: str


class Framework28Result(BaseModel):
    """Full F28 evaluation result — returned by GET /api/v1/framework28/ladder."""

    f17_active: bool | None = Field(
        description="F17 flag state (None = never set, treated as BLOCKED).",
    )

    # Current conflict context (passed from F17)
    conflict_duration_days: int | None = Field(
        description="Days since conflict start date; None if no start date.",
    )
    brent_price: float | None = Field(
        description="Current Brent crude price from Polygon.io (USD/barrel).",
    )

    # Active tier match
    active_tier: LadderTierResult | None = Field(
        default=None,
        description="The ladder tier that matches current duration and Brent price; "
        "None if no tier matches or F17 is not active.",
    )

    # All tiers for display
    all_tiers: list[LadderTierResult] = Field(
        default_factory=list,
        description="All active ladder tiers from the DB.",
    )

    # Display flags
    ladder_active: bool = Field(
        default=False,
        description="True only when F17 is active and at least one tier matched.",
    )
    no_match_reason: str | None = Field(
        default=None,
        description="Explanation when no tier matches (e.g. Brent below range).",
    )

    cache_hit: bool = False
    data_as_of: datetime | None = None
