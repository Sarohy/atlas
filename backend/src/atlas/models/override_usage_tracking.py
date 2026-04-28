"""ORM model for override usage tracking — one override allowed per earnings cycle.

When the Section 16 Rule 1 gate fails on Track A but the override conditions
are met, the operator may use ONE override per earnings cycle for the ticker.
This table records that the override was consumed.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class OverrideUsageTracking(Base):
    """One row per (ticker, earnings_cycle) — records override consumption."""

    __tablename__ = "override_usage_tracking"

    __table_args__ = (
        UniqueConstraint(
            "ticker", "earnings_cycle_start",
            name="uq_override_usage_ticker_cycle",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    earnings_cycle_start: Mapped[datetime.date] = mapped_column(
        Date, nullable=False,
    )
    earnings_cycle_end: Mapped[datetime.date] = mapped_column(
        Date, nullable=False,
    )
    override_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    override_used_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    override_used_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
