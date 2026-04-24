"""SQLAlchemy ORM model for Framework 19 — per-session NVDA kill-switch state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework19Session(Base):
    """One row per trading day — tracks whether F19 kill switch fired.

    The unique constraint on session_date ensures a single authoritative record
    per session.  Once f19_triggered = True it never reverts within the session —
    even if NVDA recovers.  This is the hard-fail prevention mechanism.
    """

    __tablename__ = "framework19_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One row per calendar date (trading day).
    session_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)

    # Whether the kill switch fired this session.
    f19_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # UTC timestamp when F19 first fired.
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # NVDA price at the moment the threshold was breached.
    nvda_price_at_trigger: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )

    # NVDA drop percentage at trigger.
    nvda_drop_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )

    # Duration in minutes over which the drop was observed.
    drop_window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Peak NVDA price within the measurement window.
    peak_price_in_window: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )

    # Framework 2 regime active at the moment of trigger.
    regime_at_trigger: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # How many buy orders were paused when F19 triggered.
    orders_paused_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # JSON-encoded list of high-beta ticker names blocked for market orders.
    high_beta_names_blocked: Mapped[str | None] = mapped_column(Text, nullable=True)

    # UTC timestamp when the alert was sent.
    alert_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # How many minutes elapsed between trigger and alert (for SLA monitoring).
    alert_sent_within_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
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
