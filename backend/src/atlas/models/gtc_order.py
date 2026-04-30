"""SQLAlchemy ORM model for GTC (Good-Till-Cancelled) orders.

Tracks open GTC buy orders for the Framework 11 GTC aggregate window
calculation.  Framework 11 uses this table to determine whether the sum of
near-money GTC notional exceeds the safe deployment window.

GTC proximity classification (done in service, not in model):
  near-money:  limit_price within 8 % of current market price
  deep-OTM:    limit_price more than 8 % below market → exempt from window
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class GtcOrder(Base):
    """Open GTC buy order tracked for Framework 11 window calculation."""

    __tablename__ = "gtc_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Ticker symbol (e.g. "MU", "MRVL").
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)

    # Limit price per share in USD.
    limit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4),
        nullable=False,
    )

    # Number of shares in the order.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Order side — must be "BUY" or "SELL".  F11 only evaluates BUY orders.
    side: Mapped[str] = mapped_column(String(4), nullable=False)

    # Order status: "OPEN" | "FILLED" | "CANCELLED".
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")

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
