"""Framework 15 — VIX Regime Override database tables.

Revision ID: f2a3b4c5d6e7
Revises: e4f5a6b7c8d9
Create Date: 2026-04-24 00:00:00.000000

Creates two new tables:
  - framework15_sessions     — per-session VIX halt state (one row per trading day)
  - framework15_paused_orders — orders paused when F15 fires

Seeds atlas_config with F15 spec constants.
All threshold values seeded here — never hardcoded in application code.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Seed F15 config keys into existing atlas_config table.
    # ON CONFLICT DO NOTHING — idempotent across re-runs.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO atlas_config (key, value, description) VALUES
              ('f15_spike_threshold_points',
               '5',
               'Framework 15: VIX intraday spike threshold in points above session open'),
              ('f15_session_start_et',
               '09:30',
               'Framework 15: US equity market session open time (America/New_York)'),
              ('f15_session_end_et',
               '16:00',
               'Framework 15: US equity market session close time (America/New_York)')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )

    # ------------------------------------------------------------------
    # framework15_sessions — one row per trading day
    # Stores whether F15 fired, at what VIX level, and override state.
    # ------------------------------------------------------------------
    op.create_table(
        "framework15_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_date", sa.Date, nullable=False, unique=True),
        sa.Column("session_open_vix", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "f15_triggered",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "f15_triggered_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("vix_at_trigger", sa.Numeric(6, 2), nullable=True),
        sa.Column("spike_size", sa.Numeric(6, 2), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("regime_at_trigger", sa.String(30), nullable=True),
        sa.Column(
            "orders_paused_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "override_applied",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column(
            "override_applied_at", sa.DateTime(timezone=True), nullable=True
        ),
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
            nullable=False,
        ),
    )

    op.create_index(
        "idx_f15_sessions_date",
        "framework15_sessions",
        ["session_date"],
        postgresql_using="btree",
    )

    # ------------------------------------------------------------------
    # framework15_paused_orders — orders paused when F15 fires
    # One row per order paused per session.
    # ON CONFLICT DO NOTHING prevents duplicate rows on re-trigger.
    # ------------------------------------------------------------------
    op.create_table(
        "framework15_paused_orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_date", sa.Date, nullable=False),
        sa.Column("order_id", sa.Integer, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(50), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "review_status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'PENDING_REVIEW'"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("review_decision", sa.String(30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "session_date",
            "order_id",
            name="uq_f15_paused_session_order",
        ),
    )

    op.create_index(
        "idx_f15_paused_session",
        "framework15_paused_orders",
        ["session_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_f15_paused_session", table_name="framework15_paused_orders")
    op.drop_table("framework15_paused_orders")

    op.drop_index("idx_f15_sessions_date", table_name="framework15_sessions")
    op.drop_table("framework15_sessions")

    # Remove F15 config keys — only remove keys that belong to F15.
    op.execute(
        sa.text(
            """
            DELETE FROM atlas_config
            WHERE key IN (
              'f15_spike_threshold_points',
              'f15_session_start_et',
              'f15_session_end_et'
            )
            """
        )
    )
