"""API routes for the F1 Momentum calculator."""

import httpx
from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.momentum import MomentumResponse
from atlas.services.momentum_service import MomentumService

router = APIRouter(prefix="/momentum", tags=["momentum"])


@router.get("/{ticker}", response_model=MomentumResponse)
async def get_momentum(ticker: str) -> MomentumResponse:
    """Compute the F1 Momentum score for a single ticker.

    Fetches one year of daily bars from Polygon.io, computes RSI, MACD,
    MA alignment, 52-week position, 1M/6M performance, and sector relative
    momentum, then rolls them into a 0-100 composite F1 score.

    Returns 503 when ``POLYGON_API_KEY`` is not configured.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Momentum analysis unavailable: POLYGON_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    async with httpx.AsyncClient() as client:
        service = MomentumService(api_key=settings.polygon_api_key, client=client)
        return await service.compute_momentum(normalised)
