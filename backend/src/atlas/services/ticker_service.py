"""Business logic for managing portfolio tickers."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.ticker import Ticker
from atlas.schemas.ticker import TickerCreate


class TickerService:
    """All database interactions for the tickers feature live here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tickers(self) -> list[Ticker]:
        """Return all tickers ordered alphabetically by ticker symbol."""
        result = await self._session.execute(select(Ticker).order_by(Ticker.ticker))
        return list(result.scalars().all())

    async def get_by_ticker(self, ticker: str) -> Ticker | None:
        """Fetch a ticker by its symbol (case-insensitive)."""
        result = await self._session.execute(
            select(Ticker).where(Ticker.ticker == ticker.upper())
        )
        return result.scalar_one_or_none()

    async def create_ticker(self, data: TickerCreate) -> Ticker:
        """Insert a new ticker and return the persisted record."""
        ticker = Ticker(
            ticker=data.ticker,
            company_name=data.company_name,
            shares=data.shares,
        )
        self._session.add(ticker)
        await self._session.flush()
        await self._session.refresh(ticker)
        return ticker

    async def update_shares(self, ticker_id: int, shares: Decimal) -> Ticker | None:
        """Update the share count for a ticker. Returns None if not found."""
        ticker = await self._session.get(Ticker, ticker_id)
        if ticker is None:
            return None
        ticker.shares = shares
        await self._session.flush()
        await self._session.refresh(ticker)
        return ticker

    async def delete_ticker(self, ticker_id: int) -> bool:
        """Delete a ticker by id. Returns True on success, False if not found."""
        ticker = await self._session.get(Ticker, ticker_id)
        if ticker is None:
            return False
        await self._session.delete(ticker)
        await self._session.flush()
        return True
