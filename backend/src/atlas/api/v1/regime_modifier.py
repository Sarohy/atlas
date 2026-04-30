"""API route for the ATLAS Regime Modifier."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.regime_modifier import GeopoliticalState, RegimeModifierResponse
from atlas.services.regime_modifier_service import RegimeModifierService

router = APIRouter(prefix="/regime-modifier", tags=["regime-modifier"])


@router.get("/{ticker}", response_model=RegimeModifierResponse)
async def get_regime_modifier(
    ticker: str,
    geopolitical_state: GeopoliticalState = "NONE",
    base_score: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> RegimeModifierResponse:
    """Apply market-regime rules to the Framework Score for a single ticker."""
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Regime Modifier unavailable: POLYGON_API_KEY is not configured. "
                "This key is required for Brent crude, VIX, and F1 Momentum data."
            ),
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = RegimeModifierService(
        polygon_api_key=settings.polygon_api_key,
        alphavantage_api_key=settings.alphavantage_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
        session=session,
    )
    return await service.compute_regime_modifier(
        normalised,
        geopolitical_state,
        provided_base_score=base_score,
    )
