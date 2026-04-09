"""API route for the ATLAS Framework Score.

GET /api/v1/framework-score/{ticker}

Aggregates F1-F5 scores using the Factor_Mapping_Guide weightings, adds the
Brent-crude regime modifier, and returns the complete Framework Score response.

Returns 503 when the minimum required API key (POLYGON_API_KEY) is not set.
Other factor services degrade gracefully to a neutral score of 50 when their
respective API keys are absent.
"""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.framework_score import FrameworkScoreResponse
from atlas.services.framework_score_service import FrameworkScoreService

router = APIRouter(prefix="/framework-score", tags=["framework-score"])


@router.get("/{ticker}", response_model=FrameworkScoreResponse)
async def get_framework_score(ticker: str) -> FrameworkScoreResponse:
    """Compute the complete ATLAS Framework Score for a single ticker.

    Aggregates five factor scores (F1-F5) with their Factor_Mapping_Guide
    weightings, fetches the current Brent crude price to determine the regime
    modifier, and returns:

    - Per-factor breakdowns (score, weight, contribution, grade)
    - Regime info (label, Brent price, modifier, cash floor)
    - Raw total (weighted sum before modifier, max 95)
    - Final score (raw_total + modifier, clamped 0-100)
    - Recommended action (MAXIMUM POSITION / HOLD / ADD / REDUCE / EXIT)
    - F5 hard block flag (Altman Z < 1.8)
    - Human-readable flags for any degraded factors

    Returns 503 when POLYGON_API_KEY is not configured (required for F1
    Momentum and Brent crude price).  All other factor services degrade to
    a neutral score of 50 when their API keys are absent.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Framework Score unavailable: POLYGON_API_KEY is not configured. "
                "This key is required for F1 Momentum and Brent crude regime detection."
            ),
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = FrameworkScoreService(
        polygon_api_key=settings.polygon_api_key,
        alphavantage_api_key=settings.alphavantage_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
    )
    return await service.compute_framework_score(normalised)
