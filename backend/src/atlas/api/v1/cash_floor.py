"""API route for Framework 5 — Cash Floor.

GET /api/v1/cash-floor/{ticker}

Determines the minimum cash reserve the investor must hold against a
portfolio position, based on the current Framework 2 (Regime Modifier) rule.

Cash floor rules
----------------
CRISIS         → 35–40 % of position value   "Binary weekend risk, high beta protection"
CAUTION        → 25–35 % of position value   "Deploy T1 only"
CLEAR          → 10–12 % of position value   "Hedge portfolio serves as macro buffer"
FULLY_DEPLOYED → 10 %    of position value   "Never touch this floor"

The endpoint calls the Regime Modifier service internally (Framework 2) to
derive the live rule, then looks up the ticker's position value from the
portfolio database.  Returns 503 when POLYGON_API_KEY is not configured.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.cash_floor import CashFloorResponse
from atlas.services.cash_floor_service import CashFloorService

router = APIRouter(prefix="/cash-floor", tags=["cash-floor"])


@router.get("/{ticker}", response_model=CashFloorResponse)
async def get_cash_floor(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> CashFloorResponse:
    """Return the Framework 5 cash-floor guidance for ``ticker``.

    Internally fetches the live Framework 2 regime rule (Brent crude + VIX)
    and the ticker's current portfolio position value, then returns:

    - ``condition``         : CRISIS | CAUTION | CLEAR | FULLY_DEPLOYED
    - ``rationale``         : Human-readable reason for the floor level
    - ``floor_pct_min/max`` : Cash floor as a fraction of position value
    - ``floor_usd_min/max`` : Cash floor in USD (None when ticker is not in portfolio)
    - ``position_value_usd``: Current portfolio position value in USD
    - ``brent_price``       : Brent crude price used for rule evaluation
    - ``vix_value``         : VIX level used for rule evaluation
    - ``rule_triggered``    : Framework 2 rule number (1/2/3/None)

    Returns 503 when POLYGON_API_KEY is not configured (required for Brent,
    VIX, and F1 Momentum data used by the Regime Modifier).
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cash Floor unavailable: POLYGON_API_KEY is not configured. "
                "This key is required for Brent crude, VIX, and Framework 2 data."
            ),
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = CashFloorService(
        polygon_api_key=settings.polygon_api_key,
        alphavantage_api_key=settings.alphavantage_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
        session=session,
    )
    return await service.compute_cash_floor(normalised)
