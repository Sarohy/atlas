"""SQLAlchemy ORM model for operator-maintained beta vs NVDA per holding."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class PortfolioBeta(Base):
    """One row per portfolio ticker — stores NVDA beta maintained by the operator.

    The operator updates this table after each quarterly review.
    Framework 19 reads from this table on every evaluation.
    No automated beta calculation in V1.
    If a ticker is missing: F19 treats beta as unknown and pauses its buy
    orders conservatively.
    """

    __tablename__ = "portfolio_beta"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Unique ticker symbol (e.g. "MRVL", "MU").
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)

    # Beta value vs NVDA.  4 decimal places; operator enters this.
    beta_vs_nvda: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False
    )

    # Source description (e.g. "Bloomberg", "Operator estimate", "Yahoo Finance").
    beta_source: Mapped[str] = mapped_column(String(50), nullable=False)

    # Date the beta value was last confirmed by the operator.
    last_updated: Mapped[date] = mapped_column(Date, nullable=False)

    # Name of the person who last updated the beta.
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Free-form notes (e.g. "Based on 2-year weekly regression vs NVDA").
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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
