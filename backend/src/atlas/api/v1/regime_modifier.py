"""API route for the ATLAS Regime Modifier.

GET /api/v1/regime-modifier/{ticker}?active_war=false

Fetches live Brent crude and VIX values from Polygon.io, retrieves the base
Framework Score for the ticker, and applies market-regime rules to produce an
adjusted conviction score with cash-management guidance.

Rule summary (applied in priority order):
  Rule 1 — Crisis : active_war OR Brent > $110 OR VIX > 35        → score -10
  Rule 2 — Caution: Brent in [$95, $110] AND VIX in [24, 35]      → score -5
  Rule 3 — Clear  : Brent < $95 (2 consecutive closes) AND VIX < 24 → score +5

Returns 503 when POLYGON_API_KEY is not configured.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.regime_modifier_service import RegimeModifierService

router = APIRouter(prefix="/regime-modifier", tags=["regime-modifier"])


@router.get("/{ticker}", response_model=RegimeModifierResponse)
async def get_regime_modifier(
    ticker: str,
    active_war: bool = False,
    base_score: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> RegimeModifierResponse:
    """Apply market-regime rules to the Framework Score for a single ticker.

    Concurrently fetches Brent crude price, VIX level, and the base Framework
    Score, then applies whichever of the three regime rules fires first.

    Returns:
      - adjusted_score: framework score modified by the triggered rule (0-100)
      - rule_triggered: which rule fired (1, 2, 3) or None for normal conditions
      - min_cash_usd / max_cash_usd: cash to hold against this position in USD
      - min_cash_pct / max_cash_pct: same amounts expressed as percentage of position
      - output_text: human-readable cash management instruction
      - brent_price / vix_value: live market conditions used for rule evaluation

    Returns 503 when POLYGON_API_KEY is not configured (required for Brent,
    VIX, and F1 Momentum data).
    """
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
        active_war,
        provided_base_score=base_score,
    )
