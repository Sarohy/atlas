"""API routes for Framework 18 — 4-Week Trend Gate.

GET  /api/v1/framework18/status          → Framework18Result (full, 15-min cache)
GET  /api/v1/framework18/status/simple   → Framework18SimpleResult (lightweight)
POST /api/v1/framework18/refresh         → invalidate cache, re-fetch from Polygon

Architecture notes:
  /status/simple is registered BEFORE /status so FastAPI does not
  interpret "simple" as a path variable.

  Framework 18 is portfolio-level — no {ticker} path parameter.
  The result does NOT change on ticker change; consuming frameworks
  call /status/simple and apply the result portfolio-wide.

  Cache is a module-level dict with 15-minute TTL (no Redis in V1).
  POST /refresh force-clears the cache and calls Polygon.io immediately.

  Consuming frameworks (F6, F4, Factor 9, F16) call /status/simple.
  They NEVER independently check SPY weekly trend.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.framework18 import Framework18Result, Framework18SimpleResult
from atlas.services.framework18_service import (
    cache_invalidate,
    evaluate_framework18,
    get_f18_simple,
)

router = APIRouter(prefix="/framework18", tags=["framework18"])


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------


@router.get("/status/simple", response_model=Framework18SimpleResult)
async def get_f18_status_simple(
    session: AsyncSession = Depends(get_db_session),
) -> Framework18SimpleResult:
    """Lightweight F18 status for consuming frameworks.

    Framework 6, Framework 4, Factor 9, and Framework 16 call this endpoint.
    They NEVER independently compute the SPY weekly trend.
    Cached 15 minutes — weekly closes do not change intraday.
    """
    cached = get_f18_simple()
    if cached is not None:
        return cached

    result = await evaluate_framework18(session)
    return Framework18SimpleResult(
        f18_status=result.f18_status,
        f18_active=result.f18_active,
        consecutive_weeks_down=result.consecutive_weeks_down,
        consecutive_threshold=result.consecutive_threshold,
        add_reduction_pct=result.add_reduction_pct,
        no_speculative_starters=(
            result.actions.no_speculative_starters if result.actions else False
        ),
        tier3_adds_blocked=(
            result.actions.tier3_adds_blocked if result.actions else False
        ),
        data_gap_severity=result.data_gap_severity,
        spy_data_available=result.spy_data_available,
    )


@router.get("/status", response_model=Framework18Result)
async def get_f18_status(
    session: AsyncSession = Depends(get_db_session),
) -> Framework18Result:
    """Full Framework 18 evaluation result.

    Includes SPY weekly closes, candle dates, actions, Factor 9 impact,
    and data availability flags.
    Cached 15 minutes in module-level dict (no Redis in V1).
    Re-fetches from Polygon.io after TTL expires.
    """
    cached_full = None
    # Check the full result cache directly (not via get_f18_simple).
    from atlas.services.framework18_service import _cache_get

    cached_full = _cache_get()
    if cached_full is not None:
        return Framework18Result(
            **{
                **cached_full.model_dump(),
                "cache_hit": True,
            }
        )

    return await evaluate_framework18(session)


# ---------------------------------------------------------------------------
# Refresh route
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=Framework18Result)
async def refresh_f18(
    session: AsyncSession = Depends(get_db_session),
) -> Framework18Result:
    """Force cache clear and re-fetch SPY weekly closes from Polygon.io.

    Clears the 15-minute module-level cache immediately.
    Calls Polygon.io fresh.
    Returns the new Framework18Result with cache_hit=False.
    Use this when a new week has just closed and you want the gate
    to reflect the new weekly candle without waiting for TTL expiry.
    """
    cache_invalidate()
    return await evaluate_framework18(session)
