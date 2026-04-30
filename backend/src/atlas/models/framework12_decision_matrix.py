"""ORM model for the Framework 12 Decision Matrix priority rows.

Each row defines a sizing tier — Section 16 PASS feeds into here, the matrix
selects the highest-priority matching row, and the row's size_min_pct /
size_max_pct (% of NAV) drives the recommended USD position size.

Rows are seeded by Alembic migration; operator may toggle `active` to disable
a row without deleting it.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class Framework12DecisionMatrix(Base):
    """One priority row in the Framework 12 decision matrix."""

    __tablename__ = "framework12_decision_matrix"

    __table_args__ = (
        UniqueConstraint(
            "priority_code", name="uq_decision_matrix_priority_code",
        ),
        CheckConstraint(
            "track IS NULL OR track IN ('TRACK_A', 'TRACK_B')",
            name="ck_decision_matrix_track",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    priority_code: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_label: Mapped[str] = mapped_column(String(100), nullable=False)
    track: Mapped[str | None] = mapped_column(String(10), nullable=True)
    earnings_max_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earnings_min_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    underweight_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    strong_flow_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    size_min_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4), nullable=False,
    )
    size_max_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4), nullable=False,
    )
    timing_rule: Mapped[str] = mapped_column(Text, nullable=False)
    is_watchlist_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
