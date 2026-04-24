"""SQLAlchemy ORM model for exit_rule_cycles (Section 16.1).

Tracks the two-cycle score-based exit state per ticker.  One row per
held ticker.  Updated (not replaced) as cycle state advances.

State machine:
  CLEAR → CYCLE_ONE → CYCLE_ONE_PAUSED ↔ CYCLE_ONE
        ↓ (next Friday still < 55, no pause/deferral)
        CYCLE_TWO → TRIM_TRIGGERED
        ↓ (score < 45 at any point)
        FULL_EXIT_TRIGGERED
        ↓ (F12 no-fly active when trim would fire)
        DEFERRED → (resumes as CYCLE_TWO after catalyst)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base

# Valid cycle status values — kept here as class constants for clarity.
_VALID_STATUSES = frozenset({
    "CLEAR",
    "CYCLE_ONE",
    "CYCLE_ONE_PAUSED",
    "CYCLE_TWO",
    "DEFERRED",
    "TRIM_TRIGGERED",
    "FULL_EXIT_TRIGGERED",
})


class ExitRuleCycle(Base):
    """One row per ticker — the current exit rule cycle state.

    Updated in-place as cycle state advances.  All historic changes are
    captured in the Decision Trace (append-only audit log).
    """

    __tablename__ = "exit_rule_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One record per holding — unique per ticker symbol.
    TICKER_MAX_LEN = 10
    ticker: Mapped[str] = mapped_column(
        String(TICKER_MAX_LEN), unique=True, nullable=False, index=True
    )

    # Current state in the Rule 16.1 state machine.
    STATUS_MAX_LEN = 30
    cycle_status: Mapped[str] = mapped_column(
        String(STATUS_MAX_LEN), nullable=False, server_default="CLEAR"
    )

    # Date and score at which Cycle One was triggered.
    cycle_one_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cycle_one_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Date and score at which Cycle Two was triggered.
    cycle_two_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cycle_two_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # True when a Claude vs Grok reconciliation gap > threshold is pending.
    reconciliation_pause: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Operator-entered Grok conviction score for reconciliation comparison.
    grok_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Claude (F1) conviction score at the time of cycle trigger.
    claude_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Whether the trim action has been recorded as executed.
    trim_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Whether the full-exit action has been recorded as executed.
    full_exit_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Earliest date the trim window reopens after a F12 deferral.
    deferred_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Human override: when True all automated exit signals are suppressed.
    override_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Logged reason for override — required when override_active = True.
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Who set the override.
    OVERRIDE_BY_MAX_LEN = 100
    override_set_by: Mapped[str | None] = mapped_column(
        String(OVERRIDE_BY_MAX_LEN), nullable=True
    )

    override_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
