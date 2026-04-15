"""API route for market conditions (Brent crude + VIX).

GET /api/v1/market/conditions

Returns the current Brent crude oil price and VIX level.
This endpoint is ticker-independent; the frontend caches it once and uses
it across all tickers to evaluate regime rules locally, eliminating per-ticker
round-trips to the regime-modifier endpoint.
"""

from fastapi import APIRouter

from atlas.schemas.market_conditions import MarketConditionsResponse
from atlas.services.market_conditions_service import MarketConditionsService

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/conditions", response_model=MarketConditionsResponse)
async def get_market_conditions() -> MarketConditionsResponse:
    """Return current Brent crude price and VIX level.

    Both values are null when the upstream data source is unavailable.
    The ``brent_prev_price`` field carries the previous daily close so the
    caller can evaluate the two-consecutive-closes condition for Rule 3.
    """
    service = MarketConditionsService()
    return await service.get_conditions()
