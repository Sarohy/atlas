"""Business logic for managing portfolio positions."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.position import Position
from atlas.schemas.position import PositionCreate


class PositionService:
    """All database interactions for the positions feature live here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_positions(self) -> list[Position]:
        """Return all positions ordered alphabetically by ticker."""
        result = await self._session.execute(select(Position).order_by(Position.ticker))
        return list(result.scalars().all())

    async def get_by_ticker(self, ticker: str) -> Position | None:
        """Fetch a position by its ticker symbol (case-insensitive)."""
        result = await self._session.execute(
            select(Position).where(Position.ticker == ticker.upper())
        )
        return result.scalar_one_or_none()

    async def create_position(self, data: PositionCreate) -> Position:
        """Insert a new position and return the persisted record."""
        position = Position(
            ticker=data.ticker,
            company_name=data.company_name,
            shares=data.shares,
        )
        self._session.add(position)
        await self._session.flush()
        await self._session.refresh(position)
        return position

    async def update_shares(self, position_id: int, shares: Decimal) -> Position | None:
        """Update the share count for a position. Returns None if not found."""
        position = await self._session.get(Position, position_id)
        if position is None:
            return None
        position.shares = shares
        await self._session.flush()
        await self._session.refresh(position)
        return position

    async def delete_position(self, position_id: int) -> bool:
        """Delete a position by id. Returns True on success, False if not found."""
        position = await self._session.get(Position, position_id)
        if position is None:
            return False
        await self._session.delete(position)
        await self._session.flush()
        return True
