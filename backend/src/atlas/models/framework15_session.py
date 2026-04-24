"""SQLAlchemy ORM model for Framework 15 — per-session VIX halt state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework15Session(Base):
    """One row per trading day — tracks whether F15 fired and override state.

    The unique constraint on session_date ensures a single authoritative record
    per session.  The service uses ON CONFLICT DO UPDATE when writing halt state
    so that a single evaluate call is always idempotent.
    """

    __tablename__ = "framework15_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One row per calendar date (trading day).
    session_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)

    # VIX value at session open (first minute candle close/open after market open).
    session_open_vix: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )

    # Whether F15 halt fired for this session.
    f15_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # UTC timestamp when F15 first fired.
    f15_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # VIX level at the moment F15 triggered.
    vix_at_trigger: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )

    # Spike size = vix_at_trigger - session_open_vix.
    spike_size: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )

    # Alert severity at the time of trigger (CRITICAL / HIGH).
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Framework 2 regime at the time of trigger.
    regime_at_trigger: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # How many non-stop buy orders were paused when F15 triggered.
    orders_paused_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Whether a human override was applied for this session.
    override_applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Written justification for the override.
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # UTC timestamp when the override was applied.
    override_applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
