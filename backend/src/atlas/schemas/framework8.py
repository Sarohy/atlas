"""Pydantic schema for Framework 8 — Insider Activity Flag response."""

from __future__ import annotations

from pydantic import BaseModel, Field

from atlas.services.framework8_service import InsiderTier


class Framework8Response(BaseModel):
    """Framework 8 insider activity analysis result.

    Returned by GET /api/v1/framework8/{ticker}.
    """

    ticker: str

    # True when discretionary insider selling has been detected.
    flag_active: bool

    # True when many sales + zero purchases -> removed from investable universe.
    hard_pass: bool

    # Insider tier of the filer who triggered the flag. None when flag is off.
    filer_tier: InsiderTier | None = None

    # Total USD value of the largest discretionary sale detected.
    largest_sale_usd: float | None = None

    # Cap applied to F5: 68 (large/Tier 1) or 72 (standard). None = no flag.
    f5_cap: int | None = Field(default=None, ge=68, le=72)

    # "hardcoded" | "sec_edgar" | "default"
    source: str
