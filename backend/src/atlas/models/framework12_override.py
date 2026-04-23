"""SQLAlchemy ORM model for Framework 12 — per-action human overrides."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework12Override(Base):
    """A human-approved override for one specific blocked action on one ticker.

    Overrides are action-specific — an override for COVERED_CALL does NOT
    unblock PARTIAL_SELL or TRIM.  Each blocked action requires its own
    separate written override.

    Overrides expire at override_expires_at.  Expired records are kept for
    audit purposes (set override_active = False rather than deleting).
    """

    __tablename__ = "framework12_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Ticker this override applies to.
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # One of: COVERED_CALL, PARTIAL_SELL, TRIM
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Mandatory written reason (cannot be empty).
    override_reason: Mapped[str] = mapped_column(Text, nullable=False)

    # False once the override has been manually revoked or has expired.
    override_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Operator-set expiry — override is inactive after this timestamp.
    override_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Display name of the operator who entered the override.
    entered_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
