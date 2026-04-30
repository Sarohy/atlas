"""SQLAlchemy ORM model for the geopolitical_flag table.

CRITICAL: This table is the SINGLE SOURCE OF TRUTH for geopolitical state.
The system NEVER auto-sets this flag — only a human operator can write to it
via POST /api/v1/framework17/flag.

Valid stored flag_state values: 'NONE', 'DE_ESCALATING', 'ACTIVE'.
The 'NOT_SET' state is runtime-only and indicates no rows exist for the query.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class GeopoliticalFlag(Base):
    """One row per operator flag-setting action.

    The F17 service queries the most recent row for today's session_date.
    If no row exists for today, it carries forward the most recent historical row.
    If no historical row exists at all, it returns NOT_SET.
    """

    __tablename__ = "geopolitical_flag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One of: 'NONE', 'DE_ESCALATING', 'ACTIVE'
    flag_state: Mapped[str] = mapped_column(String(20), nullable=False)

    # Operator identifier (username, IP, or label)
    set_by: Mapped[str] = mapped_column(String(100), nullable=False)

    # Timestamp when the operator set this flag
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # When the conflict started — used by F28 to calculate duration_days.
    # NULL means no conflict start date provided.
    conflict_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Optional operator notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The trading session this flag was set for
    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
