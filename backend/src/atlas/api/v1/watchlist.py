"""API routes for the watchlist — add/remove tickers to watch, sync market data."""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.watchlist import WatchlistItemCreate, WatchlistItemResponse
from atlas.services.market_data_service import MarketDataService
from atlas.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemResponse])
async def list_watchlist(
    session: AsyncSession = Depends(get_db_session),
) -> list[WatchlistItemResponse]:
    """Return all watchlist items ordered by symbol."""
    service = WatchlistService(session)
    return await service.list_items()  # type: ignore[return-value]


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def add_to_watchlist(
    data: WatchlistItemCreate,
    session: AsyncSession = Depends(get_db_session),
) -> WatchlistItemResponse:
    """Add a ticker to the watchlist.

    Returns 409 if the ticker is already being watched.
    """
    service = WatchlistService(session)
    existing = await service.get_by_ticker(data.ticker)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ticker {data.ticker} is already on the watchlist.",
        )
    return await service.create_item(data)  # type: ignore[return-value]


@router.delete("/{item_id}", status_code=204)
async def remove_from_watchlist(
    item_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a ticker from the watchlist."""
    service = WatchlistService(session)
    deleted = await service.delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Watchlist item {item_id} not found.")


@router.post("/sync", response_model=list[WatchlistItemResponse])
async def sync_watchlist_market_data(
    session: AsyncSession = Depends(get_db_session),
) -> list[WatchlistItemResponse]:
    """Fetch live quotes from Polygon and update all watchlist market-data fields.

    Returns 503 when ``POLYGON_API_KEY`` is not configured.
    Returns the full updated watchlist after sync.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Market data sync is unavailable: POLYGON_API_KEY is not configured.",
        )

    async with httpx.AsyncClient() as client:
        service = MarketDataService(
            api_key=settings.polygon_api_key,
            session=session,
            client=client,
        )
        return await service.sync_watchlist_items()  # type: ignore[return-value]
