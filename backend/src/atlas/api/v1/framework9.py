"""API routes for Framework 9 — Options Flow Signal Hierarchy.

GET  /api/v1/framework9/{ticker}          → Framework9Result (full evaluation)
GET  /api/v1/framework9/{ticker}/signals  → breakdown dict (raw signal detail)
POST /api/v1/framework9/{ticker}/refresh  → clears in-memory cache + re-evaluates
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.framework9 import Framework9Result
from atlas.services.framework9_service import _cache, evaluate_framework9

router = APIRouter(prefix="/framework9", tags=["framework9"])


@router.get("/{ticker}", response_model=Framework9Result)
async def get_framework9(ticker: str) -> Framework9Result:
    """Return the Framework 9 options flow evaluation for *ticker*."""
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    settings = get_settings()
    return await evaluate_framework9(
        normalised,
        settings.unusual_whales_api_key,
        settings.polygon_api_key,
        settings.alphavantage_api_key,
    )


@router.get("/{ticker}/signals")
async def get_framework9_signals(ticker: str) -> dict[str, object]:
    """Return only the raw signal breakdown for *ticker* (lightweight)."""
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    settings = get_settings()
    result = await evaluate_framework9(
        normalised,
        settings.unusual_whales_api_key,
        settings.polygon_api_key,
        settings.alphavantage_api_key,
    )
    return result.breakdown


@router.post("/{ticker}/refresh", response_model=Framework9Result)
async def refresh_framework9(ticker: str) -> Framework9Result:
    """Invalidate the in-memory cache for *ticker* then re-evaluate."""
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    # Purge all cache entries for this ticker.
    keys_to_remove = [k for k in _cache if k.endswith(f":{normalised}")]
    for key in keys_to_remove:
        del _cache[key]

    settings = get_settings()
    return await evaluate_framework9(
        normalised,
        settings.unusual_whales_api_key,
        settings.polygon_api_key,
        settings.alphavantage_api_key,
    )
