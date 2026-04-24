"""SQLAlchemy ORM model for the framework27_contagion_map table.

These rows are the SINGLE SOURCE OF TRUTH for supply chain contagion trigger
rules. The F27 service reads ALL active rows and evaluates each trigger type
against current conditions.

NEVER hardcode ticker names, thresholds, or trigger types in service code.
All values must come from rows in this table.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework27ContagionMap(Base):
    """One row per (ticker, trigger_type) contagion rule.

    Multiple rows for the same ticker are allowed (different trigger types).
    Service reads all active=True rows and evaluates each rule independently.
    """

    __tablename__ = "framework27_contagion_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Stock ticker symbol
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)

    # Description of the primary risk the ticker faces
    primary_risk: Mapped[str] = mapped_column(Text, nullable=False)

    # Secondary exposure pathway that connects the trigger to the ticker
    secondary_exposure: Mapped[str] = mapped_column(Text, nullable=False)

    # One of: HORMUZ_CLOSURE_DAYS, ASIA_FREIGHT_DISRUPTION_PCT,
    #         OIL_PRICE_SUSTAINED_DAYS, DISRUPTION_DURATION_DAYS,
    #         METALS_DISRUPTION, INDIUM_SUPPLY_DISRUPTION
    contagion_trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Human-readable description of when this trigger fires
    trigger_condition: Mapped[str] = mapped_column(Text, nullable=False)

    # Numeric threshold value; NULL for operator-flag trigger types
    trigger_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Unit for the threshold: 'days', 'pct', 'usd_per_barrel'; NULL for operator-flag types
    trigger_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # How many days the condition must persist; NULL if instantaneous
    trigger_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # What action the morning briefing should recommend when triggered
    action_on_trigger: Mapped[str] = mapped_column(Text, nullable=False)

    # Soft-delete flag — False means this rule has been superseded
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
