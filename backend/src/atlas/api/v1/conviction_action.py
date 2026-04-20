"""API route for Framework 6 — Conviction Action.

GET /api/v1/conviction-action/{ticker}

Determines an investor action tier by reading the regime-adjusted Framework
Score (Framework 1 combined score after applying Framework 2 Regime Modifier)
and mapping it to one of five conviction tiers.

Conviction tiers
----------------
score > 80   → HOLD  : "You already own this stock"
                        Hold everything / Buy more on every dip
72 ≤ score ≤ 80 → READY : "Ready to buy"
                           Deploy T2 and T3 tranches / Serious capital
65 ≤ score < 72 → EARLY : "Early thesis developing"
                           Small positions only / Buy options not shares
60 ≤ score < 65 → RADAR : "On radar, unconfirmed"
                           Zero capital deployed / Monitor every Sunday only
score < 60   → EXIT  : "EXIT"
                        Sell on Next bounce

Returns 503 when POLYGON_API_KEY is not configured.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.conviction_action import ConvictionActionResponse
from atlas.services.conviction_action_service import ConvictionActionService

router = APIRouter(prefix="/conviction-action", tags=["conviction-action"])


@router.get("/{ticker}", response_model=ConvictionActionResponse)
async def get_conviction_action(
    ticker: str,
    base_score: int | None = None,
    adjusted_score: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> ConvictionActionResponse:
    """Return the Framework 6 conviction-action guidance for ``ticker``.

    Internally calls Framework 2 (Regime Modifier) to obtain the live
    regime-adjusted Framework Score, then maps it to a conviction tier.

    Returns:
      - ``adjusted_score``: regime-adjusted framework score used for tier
      - ``base_score``     : pre-regime framework score
      - ``rule``           : active regime rule (CRISIS/CAUTION/CLEAR/NORMAL)
      - ``tier_key``       : HOLD | READY | EARLY | RADAR | EXIT
      - ``status``         : human-readable tier status label
      - ``actions``        : ordered list of recommended action lines
      - ``tone``           : UI colour hint (green/cyan/yellow/orange/red)

    Returns 503 when POLYGON_API_KEY is not configured.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Conviction Action unavailable: POLYGON_API_KEY is not configured. "
                "This key is required for Framework Score and Regime Modifier data."
            ),
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = ConvictionActionService(
        polygon_api_key=settings.polygon_api_key,
        alphavantage_api_key=settings.alphavantage_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
        session=session,
    )
    return await service.compute_conviction_action(
        normalised,
        provided_base_score=base_score,
        provided_adjusted_score=adjusted_score,
    )
