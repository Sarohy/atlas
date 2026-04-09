"""API routes for the F3 Analyst Conviction calculator."""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.analyst import AnalystResponse
from atlas.services.analyst_service import AnalystService

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.get("/{ticker}", response_model=AnalystResponse)
async def get_analyst(ticker: str) -> AnalystResponse:
    """Compute the F3 Analyst Conviction score for a single ticker.

    Fetches consensus ratings and PT revision data from Benzinga, current
    price from Polygon.io, then rolls them into a 0-100 composite F3 score
    using the four weighted sub-indicators defined in the Factor_Mapping_Guide:
      Consensus Rating (35%), Analyst Count (10%),
      PT vs Current Price (30%), PT Revision Direction (25%).

    Returns 503 when BENZINGA_API_KEY is not configured.
    """
    settings = get_settings()
    if not settings.benzinga_api_key:
        raise HTTPException(
            status_code=503,
            detail="Analyst analysis unavailable: BENZINGA_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = AnalystService(
        benzinga_api_key=settings.benzinga_api_key,
        polygon_api_key=settings.polygon_api_key,
    )
    return await service.compute_analyst(normalised)
