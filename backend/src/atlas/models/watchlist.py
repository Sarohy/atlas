"""SQLAlchemy ORM model for a watchlist item."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class WatchlistItem(Base):
    """A single ticker on the ATLAS watchlist.

    Unlike portfolio tickers, watchlist items carry no share count or position
    value — they are purely for monitoring price and risk metrics.
    """

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Maximum ticker length on US exchanges is 5 chars; 20 gives future headroom.
    TICKER_MAX_LEN = 20
    ticker: Mapped[str] = mapped_column(
        String(TICKER_MAX_LEN),
        unique=True,
        nullable=False,
        index=True,
    )

    # Human-readable company name — stored to avoid redundant Polygon lookups.
    COMPANY_NAME_MAX_LEN = 200
    company_name: Mapped[str] = mapped_column(
        String(COMPANY_NAME_MAX_LEN),
        nullable=False,
    )

    # --- Market-data columns — populated by the /watchlist/sync endpoint ---

    # Latest trade price from the Polygon snapshot.
    current_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=True,
    )

    # Prior session close used to calculate intraday change.
    previous_close: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=True,
    )

    # Intraday dollar change: current_price − previous_close.
    day_change: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=True,
    )

    # Intraday percentage change (e.g. 1.25 means +1.25 %).
    day_change_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4),
        nullable=True,
    )

    # Rolling 1-year beta vs SPY.
    beta: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4),
        nullable=True,
    )

    # Timestamp of the last successful Polygon sync for this item.
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<WatchlistItem ticker={self.ticker!r}>"
