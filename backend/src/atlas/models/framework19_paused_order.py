"""SQLAlchemy ORM model for Framework 19 — buy orders paused per session."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework19PausedOrder(Base):
    """One row per order paused when F19 fires for a session.

    The unique constraint (session_date, order_id) prevents the same order
    from being paused twice in the same session.

    review_status transitions:
      PENDING → KEPT | MODIFIED | CANCELLED
    """

    __tablename__ = "framework19_paused_orders"
    __table_args__ = (
        UniqueConstraint(
            "session_date", "order_id", name="uq_f19_paused_session_order"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Trading day for which this order was paused.
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Foreign key to gtc_orders.id (not enforced to avoid cascade issues).
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ticker symbol for display.
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)

    # Order type string (e.g. "GTC", "LIMIT", "MARKET").
    order_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Beta vs NVDA at the time of the pause (from portfolio_beta table).
    beta_vs_nvda: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    # Whether this ticker's beta exceeds the f19_beta_threshold.
    is_high_beta: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # UTC timestamp when the order was paused.
    paused_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Human review status.
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="PENDING"
    )

    # UTC timestamp when the review was completed.
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Decision made during review (KEPT, MODIFIED, CANCELLED).
    review_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Operator who reviewed (audit trail).
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
