"""ORM model for Rule 4 (Portfolio Fit) — operator's daily YES/NO per ticker.

Section 16 Rule 4 only PASSES when there is a row for this ticker dated TODAY
with fits_portfolio = TRUE.  Stale or missing rows fail the gate.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Rule4PortfolioFit(Base):
    """Operator-set portfolio-fit decision for one ticker on one date."""

    __tablename__ = "rule4_portfolio_fit"

    __table_args__ = (
        UniqueConstraint(
            "ticker", "fit_date",
            name="uq_rule4_portfolio_fit_ticker_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    fit_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fits_portfolio: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cluster_gap: Mapped[str | None] = mapped_column(Text, nullable=True)
    redundancy_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    set_by: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
