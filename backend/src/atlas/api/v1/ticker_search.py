"""API routes for ticker search via Polygon.io."""

import httpx
from fastapi import APIRouter, HTTPException, Query

from atlas.config import get_settings
from atlas.schemas.ticker import TickerSearchResult
from atlas.services.ticker_search_service import TickerSearchService

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("/search", response_model=list[TickerSearchResult])
async def search_tickers(
    q: str = Query(..., min_length=1, description="Ticker symbol or company name to search for"),
) -> list[TickerSearchResult]:
    """Search active tickers via the Polygon.io reference API.

    Returns 503 when ``POLYGON_API_KEY`` is not configured.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Ticker search is unavailable: POLYGON_API_KEY is not configured.",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        service = TickerSearchService(api_key=settings.polygon_api_key, client=client)
        return await service.search(q)
