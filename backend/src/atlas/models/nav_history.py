"""SQLAlchemy ORM model for portfolio NAV history — used by Framework 30.

One row per calendar date.  Written by the F30 service when current NAV is
computed.  The 90-day rolling peak is queried via MAX(nav_value) over the last
90 calendar days.

This table is append-only: never UPDATE or DELETE rows.  New snapshots are
written by the F30 service each time it evaluates drawdown.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class NavHistory(Base):
    """Daily NAV snapshot for portfolio drawdown tracking."""

    __tablename__ = "nav_history"

    __table_args__ = (
        UniqueConstraint("date", name="uq_nav_history_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Calendar date of the NAV snapshot — one row per day.
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)

    # Portfolio NAV in USD at the time of snapshot.  Stored as 2-decimal USD.
    nav_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
    )

    # Peak NAV over the preceding 90 days (inclusive of this date) — denormalised
    # for fast lookback queries.  Recomputed on each write.
    peak_90d: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=True,
    )

    # Drawdown percentage relative to peak_90d (0-100 scale, e.g. 12.5 = 12.5%).
    # Null when peak_90d is null (insufficient history).
    drawdown_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
