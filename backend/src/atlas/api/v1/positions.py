"""API routes for portfolio positions — CRUD operations."""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.position import PositionCreate, PositionResponse, PositionUpdate
from atlas.services.market_data_service import MarketDataService
from atlas.services.position_service import PositionService

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    session: AsyncSession = Depends(get_db_session),
) -> list[PositionResponse]:
    """Return all saved portfolio positions ordered by ticker."""
    service = PositionService(session)
    return await service.list_positions()  # type: ignore[return-value]


@router.post("", response_model=PositionResponse, status_code=201)
async def create_position(
    data: PositionCreate,
    session: AsyncSession = Depends(get_db_session),
) -> PositionResponse:
    """Add a new ticker/share-count pair to the portfolio.

    Returns 409 if the ticker already exists.
    """
    service = PositionService(session)
    existing = await service.get_by_ticker(data.ticker)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Position for {data.ticker} already exists. Use PATCH to update shares.",
        )
    return await service.create_position(data)  # type: ignore[return-value]


@router.patch("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: int,
    data: PositionUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PositionResponse:
    """Update the share count for an existing position."""
    service = PositionService(session)
    position = await service.update_shares(position_id, data.shares)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
    return position  # type: ignore[return-value]


@router.delete("/{position_id}", status_code=204)
async def delete_position(
    position_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a position from the portfolio."""
    service = PositionService(session)
    deleted = await service.delete_position(position_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")


@router.post("/sync", response_model=list[PositionResponse])
async def sync_market_data(
    session: AsyncSession = Depends(get_db_session),
) -> list[PositionResponse]:
    """Fetch live quotes from Polygon and update all position market-data fields.

    Returns 503 when ``POLYGON_API_KEY`` is not configured.
    Returns the full updated position list after sync.
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
        return await service.sync_positions()  # type: ignore[return-value]
