"""API routes for the F2 Earnings Quality calculator."""

import httpx
from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.earnings import EarningsResponse
from atlas.services.earnings_service import EarningsService

router = APIRouter(prefix="/earnings", tags=["earnings"])


@router.get("/{ticker}", response_model=EarningsResponse)
async def get_earnings(ticker: str) -> EarningsResponse:
    """Compute the F2 Earnings Quality score for a single ticker.

    Fetches quarterly income statements, EPS history, and the latest
    earnings call transcript from Alpha Vantage, then scores them across
    five weighted indicators to produce a 0-100 composite F2 score.

    Returns 503 when ``ALPHAVANTAGE_API_KEY`` is not configured.
    """
    settings = get_settings()
    if not settings.alphavantage_api_key:
        raise HTTPException(
            status_code=503,
            detail="Earnings analysis unavailable: ALPHAVANTAGE_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    async with httpx.AsyncClient() as client:
        service = EarningsService(api_key=settings.alphavantage_api_key, client=client)
        return await service.compute_earnings(normalised)
