"""SQLAlchemy ORM model for Framework 12 — non-earnings catalyst events."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class CatalystEvent(Base):
    """A manually entered non-earnings catalyst for a held ticker.

    EARNINGS catalysts are owned by Framework 7 — not stored here.
    Operator enters INDEX_INCLUSION, PRODUCT_LAUNCH, PARTNERSHIP,
    ACQUISITION, and OTHER types through the morning briefing UI.
    """

    __tablename__ = "catalyst_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Ticker this catalyst belongs to (e.g. "CRDO").
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # One of: INDEX_INCLUSION, PRODUCT_LAUNCH, PARTNERSHIP, ACQUISITION, OTHER
    catalyst_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Confirmed date of the catalyst event.
    catalyst_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Optional operator-supplied description.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ACTIVE = currently relevant; PASSED = post-event; CANCELLED = operator withdrew
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="ACTIVE"
    )

    # Operator who entered the event (display name, not auth user ID).
    entered_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
