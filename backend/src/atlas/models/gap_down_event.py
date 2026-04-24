"""SQLAlchemy ORM model for gap_down_events (Section 16.2).

One row per overnight gap-down event that exceeds the configured threshold.
The 48-hour hold window and 72-hour rescore timestamp are stored here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class GapDownEvent(Base):
    """A single Rule 16.2 gap-down event for a ticker.

    Multiple events are possible for the same ticker across different dates.
    """

    __tablename__ = "gap_down_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    TICKER_MAX_LEN = 10
    ticker: Mapped[str] = mapped_column(
        String(TICKER_MAX_LEN), nullable=False, index=True
    )

    # Calendar date of the gap-down event.
    event_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Calculated as (prev_close - open_price) / prev_close * 100 (positive = gap down).
    gap_down_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)

    # Prices at open — stored for audit trail.
    prev_close: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    # Earliest timestamp when the hold window expires.
    hold_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Timestamp at which the operator must rescore.
    rescore_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # HOLDING | RESCORED | RESOLVED
    STATUS_MAX_LEN = 20
    status: Mapped[str] = mapped_column(
        String(STATUS_MAX_LEN), nullable=False, server_default="HOLDING"
    )

    # Score obtained when the operator rescores (written post-rescore).
    rescore_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Timestamp when this event was fully resolved.
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
