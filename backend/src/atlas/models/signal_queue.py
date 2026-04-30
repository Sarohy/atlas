"""SQLAlchemy ORM model for the signal queue.

When Framework 11 detects a cash floor violation, buy signals from consuming
frameworks (F3, F4, Section 17) are queued here rather than cancelled.  When
the floor is restored, queued signals are released for re-evaluation.

Signal lifecycle:
  QUEUED    — floor violated; signal held pending cash restoration
  RELEASED  — floor restored; signal re-enters evaluation pipeline
  CANCELLED — operator manually cancelled the queued signal

The decision trace and signal_queue table are append-friendly:
  - QUEUED → RELEASED: set status='RELEASED', released_at=now()
  - QUEUED → CANCELLED: set status='CANCELLED', cancelled_at=now()
  - Never DELETE rows; they form part of the audit trail.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class SignalQueueEntry(Base):
    """Queued buy signal held due to a Framework 11 cash floor violation."""

    __tablename__ = "signal_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Ticker the signal applies to.
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)

    # Signal action (e.g. "ADD", "PARTIAL_ADD").
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    # Conviction score at time of queueing.
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
    )

    # Human-readable reason this signal was queued.
    queue_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Signal lifecycle state: "QUEUED" | "RELEASED" | "CANCELLED".
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")

    queued_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    released_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
