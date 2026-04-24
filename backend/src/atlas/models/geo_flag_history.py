"""SQLAlchemy ORM model for geo_flag_history.

Stores one row per trading date recording the geopolitical flag state
as set by the operator on that day.  Used by Section 16 to reconstruct
Friday regime snapshots when recalculating prior-week conviction scores.

CRITICAL: This table is HUMAN-SET ONLY.  The system never auto-populates it.
Framework 17 writes here whenever the operator sets the geo flag via
POST /api/v1/framework17/flag.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class GeoFlagHistory(Base):
    """One row per trading date: the most recent geo flag state for that day."""

    __tablename__ = "geo_flag_history"

    # Date PK — one canonical record per calendar date.
    flag_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # One of: 'NONE', 'DE_ESCALATING', 'ACTIVE'
    FLAG_STATE_MAX_LEN = 20
    flag_state: Mapped[str] = mapped_column(
        String(FLAG_STATE_MAX_LEN), nullable=False
    )

    # Operator who set the flag on this date.
    SET_BY_MAX_LEN = 100
    set_by: Mapped[str] = mapped_column(String(SET_BY_MAX_LEN), nullable=False)

    # Optional operator notes for audit trail.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
