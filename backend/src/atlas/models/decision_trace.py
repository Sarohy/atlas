"""SQLAlchemy ORM model for the ATLAS Decision Trace — append-only audit log.

CRITICAL: This table is APPEND-ONLY.  Never UPDATE or DELETE from this table.
Every block, override, and conflict resolution is permanently logged here.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class DecisionTrace(Base):
    """A single immutable entry in the ATLAS decision audit log.

    Written by Framework 12 on every block, override, and deferral event.
    Readable by the morning briefing and Framework 16 master sync.
    """

    __tablename__ = "decision_trace"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Stable public identifier for this decision.
    decision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        server_default=func.gen_random_uuid().cast(Text),
        index=True,
    )

    # Millisecond-precision UTC timestamp.
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # What triggered this entry: "FRAMEWORK_12", "FRAMEWORK_12_CONFLICT", etc.
    trigger: Mapped[str] = mapped_column(String(100), nullable=False)

    # BLOCK, DEFER, OVERRIDE
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Ticker this decision relates to (None for portfolio-level decisions).
    ticker: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Catalyst type that triggered the block (e.g. "EARNINGS").
    catalyst_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ISO date string of the active catalyst.
    catalyst_date: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Calendar days until catalyst at time of logging.
    days_to_catalyst: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON list of blocked action strings: ["COVERED_CALL", "PARTIAL_SELL", "TRIM"]
    actions_blocked: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Snapshot of all framework states at the time of the decision.
    framework_states: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Regime snapshot: VIX, Brent, yield spread, S&P.
    regime_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps of each data source used.
    data_freshness: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # True when a human override was applied to this decision.
    human_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Written override justification (required when human_override = True).
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Specific action that was overridden (e.g. "COVERED_CALL").
    override_action: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Human-readable resolution summary.
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    # True = entry will be shown in the next morning briefing.
    visible_in_briefing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
