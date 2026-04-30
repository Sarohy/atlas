"""API routes for Framework 29 - Capitulation / Re-Entry AND Gate.

GET  /api/v1/framework29/signals          → Framework29Result (full evaluation)
GET  /api/v1/framework29/signals/status   → Framework29GateStatus (lightweight)
POST /api/v1/framework29/refresh          → clear cache + re-evaluate

Signals 1-4 are evaluated automatically from live market data (Polygon, Unusual Whales).
Signal 5 (geo flag) is controlled via the regime modifier endpoint (Framework 2).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.framework29 import (
    Framework29GateStatus,
    Framework29Result,
)
from atlas.services.framework29_service import (
    _cache_invalidate,
    evaluate_framework29,
    get_gate_status,
)

router = APIRouter(prefix="/framework29", tags=["framework29"])


@router.get("/signals", response_model=Framework29Result)
async def get_framework29_signals() -> Framework29Result:
    """Return the full Framework 29 evaluation (all 5 signals + gate status)."""
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Framework 29 unavailable: POLYGON_API_KEY is not configured. "
                "VIX, Brent, and breadth index data require a Polygon.io key."
            ),
        )
    return await evaluate_framework29(
        polygon_api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key,
    )


@router.get("/signals/status", response_model=Framework29GateStatus)
async def get_framework29_gate_status() -> Framework29GateStatus:
    """Return lightweight gate status from cache.  Triggers full evaluation if cache is empty."""
    cached = get_gate_status()
    if cached is not None:
        return cached

    # Nothing in cache — run a full evaluation.
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Framework 29 unavailable: POLYGON_API_KEY is not configured.",
        )
    result = await evaluate_framework29(
        polygon_api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key,
    )
    return Framework29GateStatus(
        and_gate_passed=result.and_gate_passed,
        signals_confirmed=result.signals_confirmed,
        signals_unavailable=result.signals_unavailable,
        gate_status=result.gate_status,
        data_gap_severity=result.data_gap_severity,
    )




@router.post("/refresh", response_model=Framework29Result)
async def refresh_framework29() -> Framework29Result:
    """Invalidate the in-memory cache and re-evaluate all 5 signals."""
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Framework 29 unavailable: POLYGON_API_KEY is not configured.",
        )
    _cache_invalidate()
    return await evaluate_framework29(
        polygon_api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key,
    )
