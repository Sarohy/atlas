"""SQLAlchemy ORM model for a portfolio position."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Position(Base):
    """A single holding in the ATLAS portfolio.

    ``ticker`` is unique — one record per symbol at all times.
    ``shares`` is stored with 4 decimal places for fractional-share accuracy.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Maximum ticker length on US exchanges is 5 chars; 20 gives future headroom.
    TICKER_MAX_LEN = 20  # e.g. "GOOGL", "BRK.B"
    ticker: Mapped[str] = mapped_column(
        String(TICKER_MAX_LEN),
        unique=True,
        nullable=False,
        index=True,
    )

    # Human-readable company name from Polygon — stored so we don't re-fetch.
    COMPANY_NAME_MAX_LEN = 200
    company_name: Mapped[str] = mapped_column(
        String(COMPANY_NAME_MAX_LEN),
        nullable=False,
    )

    # Shares held — 15 digits total, 4 decimal places.
    shares: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
    )

    # --- Market data columns — populated by the /sync endpoint ---

    # Latest trade price from Polygon session.price or last_trade.price.
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

    # Position market value: shares × current_price.
    position_value: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4),
        nullable=True,
    )

    # Rolling 1-year beta vs SPY — measures sensitivity to broad market moves.
    # β > 1: more volatile than market; β < 1: less volatile; β < 0: inverse.
    beta: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=8, scale=4),
        nullable=True,
    )

    # Timestamp of the last successful Polygon sync for this position.
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
        return f"<Position ticker={self.ticker!r} shares={self.shares}>"
