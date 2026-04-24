"""SQLAlchemy ORM model for grok_scores.

Stores operator-entered Grok conviction scores used for Claude vs Grok
reconciliation under Rule 16.1.  One row per (ticker, score_date) pair.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class GrokScore(Base):
    """Operator-entered Grok conviction score for a specific ticker and date."""

    __tablename__ = "grok_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    TICKER_MAX_LEN = 10
    ticker: Mapped[str] = mapped_column(
        String(TICKER_MAX_LEN), nullable=False, index=True
    )

    # The Friday rescore date this score applies to.
    score_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Grok conviction score - same 0-100 scale as Atlas conviction score.
    grok_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    # Operator who entered this score.
    ENTERED_BY_MAX_LEN = 100
    entered_by: Mapped[str] = mapped_column(
        String(ENTERED_BY_MAX_LEN), nullable=False
    )

    # Optional context notes.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("ticker", "score_date", name="uq_grok_scores_ticker_date"),
    )
