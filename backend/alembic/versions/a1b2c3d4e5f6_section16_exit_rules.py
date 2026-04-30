"""Section 16 Exit Rules — database tables and config seeds.

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-04-27 00:00:00.000000

Creates four new tables:
  geo_flag_history   — daily snapshot of geopolitical flag state (for Friday rescore)
  exit_rule_cycles   — two-cycle score-based exit tracking per ticker (16.1)
  gap_down_events    — overnight gap-down events and hold windows (16.2)
  grok_scores        — operator-entered Grok conviction scores for reconciliation

Seeds atlas_config with S16 spec constants (all prefixed s16_).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. geo_flag_history — one row per trading date, human-set only.
    #    Used by Section 16 to reconstruct Friday regime snapshots.
    # ------------------------------------------------------------------
    op.create_table(
        "geo_flag_history",
        sa.Column("flag_date", sa.Date(), nullable=False),
        sa.Column("flag_state", sa.String(20), nullable=False),
        sa.Column("set_by", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("flag_date"),
    )

    # ------------------------------------------------------------------
    # 2. exit_rule_cycles — Rule 16.1 two-cycle exit tracking per ticker.
    # ------------------------------------------------------------------
    op.create_table(
        "exit_rule_cycles",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        # Unique per ticker — one active cycle record per holding.
        sa.Column("ticker", sa.String(10), nullable=False),
        # CLEAR | CYCLE_ONE | CYCLE_ONE_PAUSED | CYCLE_TWO | DEFERRED |
        # TRIM_TRIGGERED | FULL_EXIT_TRIGGERED
        sa.Column("cycle_status", sa.String(30), nullable=False, server_default="CLEAR"),
        sa.Column("cycle_one_date", sa.Date(), nullable=True),
        sa.Column("cycle_one_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("cycle_two_date", sa.Date(), nullable=True),
        sa.Column("cycle_two_score", sa.Numeric(5, 2), nullable=True),
        # True when reconciliation (Claude vs Grok gap > 8) is pending.
        sa.Column("reconciliation_pause", sa.Boolean(), nullable=False, server_default="false"),
        # Operator-entered Grok score for reconciliation.
        sa.Column("grok_score", sa.Numeric(5, 2), nullable=True),
        # Claude (F1) score at time of cycle trigger.
        sa.Column("claude_score", sa.Numeric(5, 2), nullable=True),
        # True after trim or exit action has been executed.
        sa.Column("trim_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("full_exit_triggered", sa.Boolean(), nullable=False, server_default="false"),
        # Earliest date the trim window reopens after F12 deferral.
        sa.Column("deferred_until", sa.Date(), nullable=True),
        # Human override: True suppresses all automated exit signals.
        sa.Column("override_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("override_set_by", sa.String(100), nullable=True),
        sa.Column("override_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_exit_rule_cycles_ticker", "exit_rule_cycles", ["ticker"])

    # ------------------------------------------------------------------
    # 3. gap_down_events — Rule 16.2 overnight gap-down tracking.
    # ------------------------------------------------------------------
    op.create_table(
        "gap_down_events",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("gap_down_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("prev_close", sa.Numeric(15, 4), nullable=False),
        sa.Column("open_price", sa.Numeric(15, 4), nullable=False),
        # Earliest timestamp at which the hold window expires.
        sa.Column("hold_until", sa.DateTime(timezone=True), nullable=False),
        # Timestamp at which the operator should rescore using latest data.
        sa.Column("rescore_at", sa.DateTime(timezone=True), nullable=False),
        # HOLDING | RESCORED | RESOLVED
        sa.Column("status", sa.String(20), nullable=False, server_default="HOLDING"),
        # Score obtained at rescore time (written post-rescore).
        sa.Column("rescore_score", sa.Numeric(5, 2), nullable=True),
        # Timestamp when this event was closed out.
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gap_down_events_ticker", "gap_down_events", ["ticker"])

    # ------------------------------------------------------------------
    # 4. grok_scores — operator-entered Grok scores for reconciliation.
    # ------------------------------------------------------------------
    op.create_table(
        "grok_scores",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("grok_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("entered_by", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "score_date", name="uq_grok_scores_ticker_date"),
    )
    op.create_index("ix_grok_scores_ticker", "grok_scores", ["ticker"])

    # ------------------------------------------------------------------
    # 5. atlas_config seeds — S16 spec constants.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            "INSERT INTO atlas_config (key, value, description) VALUES "
            "('s16_score_below_55_threshold', '55', "
            "'Rule 16.1: score below this triggers cycle one watch'), "
            "('s16_score_below_45_threshold', '45', "
            "'Rule 16.1: score below this triggers immediate full exit'), "
            "('s16_trim_pct_cycle_two', '50', "
            "'Rule 16.1: percent of position to trim on cycle two'), "
            "('s16_trim_window_trading_days', '5', "
            "'Rule 16.1: trading days within which cycle-two trim must execute'), "
            "('s16_full_exit_trading_days', '3', "
            "'Rule 16.1: trading days within which full exit must execute for score < 45'), "
            "('s16_gap_down_threshold_pct', '20', "
            "'Rule 16.2: overnight gap down percent that triggers hold window'), "
            "('s16_gap_down_hold_hours', '48', "
            "'Rule 16.2: hours to hold before action after gap-down trigger'), "
            "('s16_gap_down_rescore_hours', '72', "
            "'Rule 16.2: hours after gap-down event at which rescore must occur'), "
            "('s16_appreciation_soft_cap_pct', '8', "
            "'Rule 16.3: position pct of NAV above which no new capital is deployed'), "
            "('s16_appreciation_hard_cap_pct', '10', "
            "'Rule 16.3: position pct of NAV above which 20% trim is considered'), "
            "('s16_appreciation_trim_size_pct', '20', "
            "'Rule 16.3: percent of position to trim when hard cap is breached'), "
            "('s16_put_flow_threshold_usd', '500000', "
            "'Rule 16.4: minimum bearish dark pool flow USD to satisfy condition 1'), "
            "('s16_put_earnings_days', '20', "
            "'Rule 16.4: max days to earnings for condition 2 to be satisfied'), "
            "('s16_reconciliation_gap_threshold', '8', "
            "'Rule 16.1: Claude vs Grok score gap that triggers reconciliation pause'), "
            "('s16_catalyst_deferral_days', '10', "
            "'Rule 16.1: max trading days to defer trim window when F12 no-fly active') "
            "ON CONFLICT (key) DO NOTHING"
        )
    )


def downgrade() -> None:
    # Remove config seeds first, then drop tables in reverse creation order.
    op.execute(
        sa.text(
            "DELETE FROM atlas_config WHERE key IN ("
            "'s16_score_below_55_threshold', 's16_score_below_45_threshold', "
            "'s16_trim_pct_cycle_two', 's16_trim_window_trading_days', "
            "'s16_full_exit_trading_days', 's16_gap_down_threshold_pct', "
            "'s16_gap_down_hold_hours', 's16_gap_down_rescore_hours', "
            "'s16_appreciation_soft_cap_pct', 's16_appreciation_hard_cap_pct', "
            "'s16_appreciation_trim_size_pct', 's16_put_flow_threshold_usd', "
            "'s16_put_earnings_days', 's16_reconciliation_gap_threshold', "
            "'s16_catalyst_deferral_days')"
        )
    )
    op.drop_index("ix_grok_scores_ticker", table_name="grok_scores")
    op.drop_table("grok_scores")
    op.drop_index("ix_gap_down_events_ticker", table_name="gap_down_events")
    op.drop_table("gap_down_events")
    op.drop_index("ix_exit_rule_cycles_ticker", table_name="exit_rule_cycles")
    op.drop_table("exit_rule_cycles")
    op.drop_table("geo_flag_history")
