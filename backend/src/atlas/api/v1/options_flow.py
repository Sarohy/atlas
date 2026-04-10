"""API routes for the F4 Options Flow calculator."""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.options_flow import OptionsFlowResponse
from atlas.services.options_flow_service import OptionsFlowService

router = APIRouter(prefix="/options-flow", tags=["options-flow"])


@router.get("/{ticker}", response_model=OptionsFlowResponse)
async def get_options_flow(ticker: str) -> OptionsFlowResponse:
    """Compute the F4 Options Flow score for a single ticker.

    Fetches data from Unusual Whales (flow alerts, options volume, dark pool)
    and rolls it into a 0-100 composite F4 score using the five weighted
    sub-indicators defined in the Factor_Mapping_Guide:
      Whale Block Size (35%), Call/Put Ratio (20%), Volume vs OI (20%),
      Dark Pool Print (15%), Sweep Type (10%).

    The collar flag is raised when a protective put + covered call structure
    is detected — the score is then capped at 68 per guide rules.

    Returns 503 when UNUSUAL_WHALES_API_KEY is not configured.
    """
    settings = get_settings()
    if not settings.unusual_whales_api_key:
        raise HTTPException(
            status_code=503,
            detail="Options flow analysis unavailable: UNUSUAL_WHALES_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = OptionsFlowService(api_key=settings.unusual_whales_api_key)
    return await service.compute_options_flow(normalised)
