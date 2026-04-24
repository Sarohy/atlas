"""SQLAlchemy ORM model for the manual_contagion_flags table.

Operator-confirmed supply chain disruption events for trigger types that
cannot be determined from market data alone:
  - ASIA_FREIGHT_DISRUPTION_PCT
  - METALS_DISRUPTION
  - INDIUM_SUPPLY_DISRUPTION

The F27 service checks for an active flag of each type for today's session.
Only an operator can write to this table via the manual-flag endpoint.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class ManualContagionFlag(Base):
    """One row per operator-confirmed disruption event.

    Service queries: most recent active=True row per trigger_type for today's
    session_date. If none exists and no carry-forward flag exists, trigger
    is treated as NOT_FLAGGED.
    """

    __tablename__ = "manual_contagion_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One of: ASIA_FREIGHT_DISRUPTION_PCT, METALS_DISRUPTION, INDIUM_SUPPLY_DISRUPTION
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Operator identifier
    flagged_by: Mapped[str] = mapped_column(String(100), nullable=False)

    # Timestamp when the operator confirmed this disruption
    flagged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Optional operator notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The trading session this flag applies to
    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Active flag — operator can deactivate a flag without deleting it
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
