"""SQLAlchemy ORM model for position clusters."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas.db.base import Base

if TYPE_CHECKING:
    from atlas.models.ticker import Ticker


class Cluster(Base):
    """A user-defined grouping for portfolio positions.

    Tickers may be assigned to at most one cluster.
    The colour is stored as a 7-character hex string (#RRGGBB).
    """

    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Human-readable cluster name — e.g. "AI Core", "Energy".
    CLUSTER_NAME_MAX_LEN = 100
    name: Mapped[str] = mapped_column(
        String(CLUSTER_NAME_MAX_LEN),
        unique=True,
        nullable=False,
    )

    # Display colour as a 7-char hex string, e.g. "#4a90d9".
    CLUSTER_COLOR_MAX_LEN = 10
    color: Mapped[str] = mapped_column(
        String(CLUSTER_COLOR_MAX_LEN),
        nullable=False,
        default="#4a90d9",
    )

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

    # Back-reference: all tickers assigned to this cluster.
    tickers: Mapped[list[Ticker]] = relationship(
        "Ticker",
        back_populates="cluster",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Cluster name={self.name!r} color={self.color!r}>"
