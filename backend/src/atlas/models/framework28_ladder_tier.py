"""SQLAlchemy ORM model for the framework28_ladder_tiers table.

These rows are the SINGLE SOURCE OF TRUTH for war duration portfolio guidance.
The F28 service reads ALL active rows and matches against current conflict
duration and Brent price. NEVER hardcode tier thresholds in service code.

Tier matching: find active tier where
  duration_min_days <= conflict_duration_days <= duration_max_days (NULL = open)
  AND brent_range_low <= brent_price <= brent_range_high (NULL = open)
When multiple tiers match, use the one with the highest tier_order.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework28LadderTier(Base):
    """One row per war duration ladder tier (4 tiers seeded by migration).

    Tier 4 has duration_max_days=NULL (91+ days) and brent_range_high=NULL.
    """

    __tablename__ = "framework28_ladder_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Tier severity order: 1 = mild, 4 = most severe
    tier_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    # Minimum conflict duration in days (inclusive)
    duration_min_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Maximum conflict duration in days (inclusive); NULL = open-ended
    duration_max_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Minimum Brent price in USD/barrel (inclusive)
    brent_range_low: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    # Maximum Brent price in USD/barrel (inclusive); NULL = open-ended
    brent_range_high: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Fed policy implication text for morning briefing
    fed_implication: Mapped[str] = mapped_column(Text, nullable=False)

    # Portfolio action guidance text — shown verbatim in morning briefing
    portfolio_action: Mapped[str] = mapped_column(Text, nullable=False)

    # Soft-delete flag — False means this tier has been superseded
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
