"""API routes for Framework 28 — War Duration Ladder.

GET /api/v1/framework28/ladder → Framework28Result (5-min cache)

Framework 28 is portfolio-level (no {ticker} path parameter).
Reads F17 state from the F17 service; reads tier thresholds from DB.
Never hardcodes duration or Brent price values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.framework28 import Framework28Result
from atlas.services.framework17_service import evaluate_framework17
from atlas.services.framework28_service import (
    cache_invalidate,
    evaluate_framework28,
)

router = APIRouter(prefix="/framework28", tags=["framework28"])


@router.get("/ladder", response_model=Framework28Result)
async def get_f28_ladder(
    session: AsyncSession = Depends(get_db_session),
) -> Framework28Result:
    """War Duration Ladder evaluation (5-minute cache).

    Reads current F17 state (conflict duration, Brent price) from the
    F17 service. Matches against ladder tiers from the
    framework28_ladder_tiers table.

    Returns the highest-severity matching tier plus all tiers for display.
    When F17 is not active, returns ladder_active=False.
    """
    from atlas.services.framework28_service import _cache_get

    cached = _cache_get()
    if cached is not None:
        return Framework28Result(**{**cached.model_dump(), "cache_hit": True})

    f17_result = await evaluate_framework17(session)
    return await evaluate_framework28(f17_result, session)
