"""SQLAlchemy ORM models for Section 17 — LEAPS Strategy (V1).

Two tables:
  leaps_positions  — manual LEAPS entries tracked by the investor
  leaps_iv_history — time-series of IV readings per position

V1 scope: read-only tracking.  Positions are created via direct DB writes or
future admin interface; no execution engine exists yet.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas.db.base import Base


class LeapsPosition(Base):
    """A tracked LEAPS option position."""

    __tablename__ = "leaps_positions"

    # Maximum ticker length mirroring tickers table.
    _TICKER_MAX_LEN: int = 20
    _OPTION_SYMBOL_MAX_LEN: int = 40
    _OPTION_TYPE_MAX_LEN: int = 4   # CALL / PUT
    _STATUS_MAX_LEN: int = 20       # OPEN, CLOSED, EXPIRED
    _NOTES_MAX_LEN: int = 500

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ticker: Mapped[str] = mapped_column(
        String(_TICKER_MAX_LEN),
        nullable=False,
        index=True,
    )

    # Full OCC option symbol, e.g. "AAPL240119C00150000".
    option_symbol: Mapped[str] = mapped_column(
        String(_OPTION_SYMBOL_MAX_LEN),
        unique=True,
        nullable=False,
    )

    expiration_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    strike_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    # CALL or PUT.
    option_type: Mapped[str] = mapped_column(
        String(_OPTION_TYPE_MAX_LEN),
        nullable=False,
    )

    # Number of contracts (each contract = 100 shares).
    contracts: Mapped[int] = mapped_column(nullable=False)

    # Price paid per contract at entry (per-share basis, not per-contract).
    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
    )

    # IV at the time of entry — stored for comparison.
    iv_at_entry: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=True,
    )

    # OPEN, CLOSED, EXPIRED.
    status: Mapped[str] = mapped_column(
        String(_STATUS_MAX_LEN),
        nullable=False,
        default="OPEN",
    )

    notes: Mapped[str | None] = mapped_column(
        String(_NOTES_MAX_LEN),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to IV history.
    iv_history: Mapped[list[LeapsIvHistory]] = relationship(
        "LeapsIvHistory",
        back_populates="position",
        cascade="all, delete-orphan",
    )


class LeapsIvHistory(Base):
    """Time-series IV readings for a LEAPS position.

    Written each time the LEAPS service fetches current IV for an open position.
    Used to compute IV percentile over rolling history.
    """

    __tablename__ = "leaps_iv_history"

    _OPTION_SYMBOL_MAX_LEN: int = 40

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # FK to leaps_positions (cascade delete).
    position_id: Mapped[int] = mapped_column(
        ForeignKey("leaps_positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Redundant ticker for faster direct queries.
    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Option symbol for the specific contract.
    option_symbol: Mapped[str] = mapped_column(
        String(_OPTION_SYMBOL_MAX_LEN),
        nullable=False,
    )

    # Calendar date of the IV reading.
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)

    # IV as a decimal (e.g. 0.45 = 45% IV).
    iv_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=4),
        nullable=False,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    position: Mapped[LeapsPosition] = relationship(
        "LeapsPosition",
        back_populates="iv_history",
    )
