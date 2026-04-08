"""Business logic for managing watchlist items."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.watchlist import WatchlistItem
from atlas.schemas.watchlist import WatchlistItemCreate


class WatchlistService:
    """All database interactions for the watchlist feature live here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_items(self) -> list[WatchlistItem]:
        """Return all watchlist items ordered alphabetically by ticker symbol."""
        result = await self._session.execute(
            select(WatchlistItem).order_by(WatchlistItem.ticker)
        )
        return list(result.scalars().all())

    async def get_by_ticker(self, ticker: str) -> WatchlistItem | None:
        """Fetch a watchlist item by its symbol (case-insensitive)."""
        result = await self._session.execute(
            select(WatchlistItem).where(WatchlistItem.ticker == ticker.upper())
        )
        return result.scalar_one_or_none()

    async def create_item(self, data: WatchlistItemCreate) -> WatchlistItem:
        """Insert a new watchlist item and return the persisted record."""
        item = WatchlistItem(
            ticker=data.ticker,
            company_name=data.company_name,
        )
        self._session.add(item)
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def delete_item(self, item_id: int) -> bool:
        """Delete a watchlist item by id. Returns True on success, False if not found."""
        item = await self._session.get(WatchlistItem, item_id)
        if item is None:
            return False
        await self._session.delete(item)
        await self._session.flush()
        return True
