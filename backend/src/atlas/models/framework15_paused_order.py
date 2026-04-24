"""SQLAlchemy ORM model for Framework 15 — paused orders per session."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    DateTime,
    Date,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework15PausedOrder(Base):
    """One row per order paused when F15 fires for a session.

    The unique constraint (session_date, order_id) prevents the same order
    from being paused twice in the same session if evaluate is called again
    after the halt is already stored.

    review_status transitions: PENDING_REVIEW → KEPT | MODIFIED | CANCELLED.
    """

    __tablename__ = "framework15_paused_orders"
    __table_args__ = (
        UniqueConstraint(
            "session_date", "order_id", name="uq_f15_paused_session_order"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Trading day for which this order was paused.
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Foreign key to gtc_orders.id (not enforced as FK to avoid cascade issues).
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ticker symbol for display.
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)

    # Order type string (e.g. "LIMIT", "MARKET", "GTC").
    order_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # UTC timestamp when this specific order was paused.
    paused_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Operator review decision: PENDING_REVIEW | KEPT | MODIFIED | CANCELLED.
    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="PENDING_REVIEW",
    )

    # UTC timestamp when the operator reviewed this order.
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Display name of the reviewer.
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Final operator decision string.
    review_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
