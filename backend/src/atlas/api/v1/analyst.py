"""API routes for the F3 Analyst Conviction calculator."""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.analyst import AnalystResponse
from atlas.services.analyst_service import AnalystService

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.get("/{ticker}", response_model=AnalystResponse)
async def get_analyst(ticker: str) -> AnalystResponse:
    """Compute the F3 Analyst Conviction score for a single ticker.

    Fetches analyst consensus data from Polygon.io — buy/hold/sell breakdown,
    consensus price target, prior price target, and recent rating changes —
    then rolls them into a 0-100 composite F3 score.

    Returns 503 when ``POLYGON_API_KEY`` is not configured.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Analyst analysis unavailable: POLYGON_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = AnalystService(api_key=settings.polygon_api_key)
    return await service.compute_analyst(normalised)
