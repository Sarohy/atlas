"""ORM model for ticker → Track assignment (Track A or Track B).

One row per ticker.  Operator assigns the track up-front; Section 16 reads it
on every evaluation to decide which gate rules apply.
"""

from __future__ import annotations

import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class TickerTrackAssignment(Base):
    """Track assignment for a single ticker."""

    __tablename__ = "ticker_track_assignment"

    __table_args__ = (
        UniqueConstraint("ticker", name="uq_ticker_track_assignment_ticker"),
        CheckConstraint(
            "track IN ('TRACK_A', 'TRACK_B')",
            name="ck_ticker_track_assignment_track",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    track: Mapped[str] = mapped_column(String(10), nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(100), nullable=False)
    assigned_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
