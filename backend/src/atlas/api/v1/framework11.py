"""API routes for Framework 11 — Cash Floor Enforcer.

GET  /api/v1/framework11/status        → Framework11Result (full evaluation)
GET  /api/v1/framework11/status/simple → Framework11SimpleResult (lightweight)
GET  /api/v1/framework11/queue         → Framework11QueueResponse (queued signals)
POST /api/v1/framework11/refresh       → clear cache + re-evaluate
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.framework11 import (
    Framework11QueueResponse,
    Framework11Result,
    Framework11SimpleResult,
)
from atlas.services.framework11_service import (
    _cache_invalidate,
    evaluate_framework11,
    get_f11_simple,
)

router = APIRouter(prefix="/framework11", tags=["framework11"])


def _get_api_keys() -> dict[str, str]:
    """Return all API keys from settings."""
    settings = get_settings()
    return {
        "polygon_api_key": settings.polygon_api_key or "",
        "alphavantage_api_key": settings.alphavantage_api_key or "",
        "transcript_api_key": settings.earnings_transcript_api_key or "",
        "benzinga_api_key": settings.benzinga_api_key or "",
        "unusual_whales_api_key": settings.unusual_whales_api_key or "",
        "sec_api_key": settings.sec_api_key or "",
    }


@router.get("/status", response_model=Framework11Result)
async def get_framework11_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Framework11Result:
    """Return the full Framework 11 cash floor evaluation.

    Cached for 2 minutes.  Fetches regime from Framework 2 and NAV from
    portfolio DB in parallel.  Evaluates all open GTC buy orders for
    proximity classification and window oversubscription check.
    """
    keys = _get_api_keys()
    return await evaluate_framework11(session=session, **keys)


@router.get("/status/simple", response_model=Framework11SimpleResult)
async def get_framework11_status_simple(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Framework11SimpleResult:
    """Return lightweight Framework 11 status for consuming frameworks.

    Returns cached result when available.  Triggers full evaluation if cache
    is empty.  Intended for Framework 4, Section 17 LEAPS, and Framework 16.
    """
    # Try cache first (sync, no DB needed).
    cached_simple = get_f11_simple()
    if cached_simple is not None:
        return cached_simple

    # Cache miss — run full evaluation.
    keys = _get_api_keys()
    result = await evaluate_framework11(session=session, **keys)
    return Framework11SimpleResult(
        floor_status=result.floor_status,
        floor_violated=result.floor_violated,
        all_buys_blocked=result.all_buys_blocked,
        floor_pct=result.floor_pct,
        cash_pct=result.cash_pct,
        shortfall_usd=result.shortfall_usd,
        gtc_window_usd=result.gtc_window_usd,
        gtc_oversubscribed=result.gtc_oversubscribed,
        data_gap_severity=result.data_gap_severity,
    )


@router.get("/queue", response_model=Framework11QueueResponse)
async def get_framework11_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Framework11QueueResponse:
    """Return all buy signals currently queued due to a cash floor violation.

    Reads directly from the signal_queue table; does not refresh the F11 cache.
    """
    from atlas.services.framework11_service import _fetch_queued_signals

    signals = await _fetch_queued_signals(session)
    return Framework11QueueResponse(queued_signals=signals, count=len(signals))


@router.post("/refresh", response_model=Framework11Result)
async def refresh_framework11(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Framework11Result:
    """Force cache clear and re-evaluate Framework 11.

    For operator use when cash balance changes (e.g. after a sell fills
    and cash is restored above the floor).  Clears the 2-minute cache and
    immediately runs a fresh evaluation.
    """
    _cache_invalidate()
    keys = _get_api_keys()
    return await evaluate_framework11(session=session, **keys)
