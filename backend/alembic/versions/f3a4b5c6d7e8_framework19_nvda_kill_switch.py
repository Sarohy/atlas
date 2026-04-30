"""Framework 19 — NVDA Kill Switch database tables and config seeds.

Revision ID: f3a4b5c6d7e8
Revises: e5f6a7b8c9d1
Create Date: 2026-04-24 00:00:00.000000

Creates three new tables:
  portfolio_beta               — operator-maintained beta vs NVDA per holding
  framework19_sessions         — one row per trading day, kill-switch state
  framework19_paused_orders    — orders paused when F19 fires

Seeds atlas_config with F19 spec constants.
All threshold values seeded here — never hardcoded in application code.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str = "e5f6a7b8c9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Seed F19 config keys into existing atlas_config table.
    # ON CONFLICT DO NOTHING — idempotent across re-runs.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO atlas_config (key, value, description) VALUES
              ('f19_drop_threshold_pct',
               '4.0',
               'Framework 19: NVDA intraday drop % to trigger kill switch'),
              ('f19_time_window_minutes',
               '60',
               'Framework 19: rolling window in minutes for NVDA drop calculation'),
              ('f19_beta_threshold',
               '1.5',
               'Framework 19: NVDA beta above this threshold = market order block'),
              ('f19_alert_fire_within_minutes',
               '5',
               'Framework 19: maximum minutes allowed to send alert after trigger')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )

    # ------------------------------------------------------------------
    # portfolio_beta — operator-maintained beta values per holding.
    # Operator updates quarterly.  F19 reads fresh on every evaluation.
    # Never automated — operator sets these after each quarterly review.
    # ------------------------------------------------------------------
    op.create_table(
        "portfolio_beta",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("beta_vs_nvda", sa.Numeric(6, 4), nullable=False),
        sa.Column("beta_source", sa.String(50), nullable=False),
        sa.Column("last_updated", sa.Date, nullable=False),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    # ------------------------------------------------------------------
    # framework19_sessions — one row per trading day.
    # Stores kill-switch state, triggered price, affected names.
    # UNIQUE on session_date — single authoritative record per session.
    # Once f19_triggered = True it never reverts within that session.
    # ------------------------------------------------------------------
    op.create_table(
        "framework19_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_date", sa.Date, nullable=False, unique=True
        ),
        sa.Column(
            "f19_triggered",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "triggered_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "nvda_price_at_trigger", sa.Numeric(10, 4), nullable=True
        ),
        sa.Column("nvda_drop_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column("drop_window_minutes", sa.Integer, nullable=True),
        sa.Column(
            "peak_price_in_window", sa.Numeric(10, 4), nullable=True
        ),
        sa.Column("regime_at_trigger", sa.String(30), nullable=True),
        sa.Column(
            "orders_paused_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        # Text array stored as JSON string for portability.
        sa.Column("high_beta_names_blocked", sa.Text, nullable=True),
        sa.Column("alert_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_sent_within_minutes", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    # ------------------------------------------------------------------
    # framework19_paused_orders — one row per order paused per session.
    # UNIQUE on (session_date, order_id) — idempotent re-pause guards.
    # review_status: PENDING → KEPT | MODIFIED | CANCELLED.
    # ------------------------------------------------------------------
    op.create_table(
        "framework19_paused_orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_date", sa.Date, nullable=False, index=True),
        sa.Column("order_id", sa.Integer, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(50), nullable=False),
        sa.Column("beta_vs_nvda", sa.Numeric(6, 4), nullable=True),
        sa.Column("is_high_beta", sa.Boolean, nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "review_status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_decision", sa.String(30), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "session_date",
            "order_id",
            name="uq_f19_paused_session_order",
        ),
    )


def downgrade() -> None:
    op.drop_table("framework19_paused_orders")
    op.drop_table("framework19_sessions")
    op.drop_table("portfolio_beta")

    op.execute(
        sa.text(
            """
            DELETE FROM atlas_config
            WHERE key IN (
                'f19_drop_threshold_pct',
                'f19_time_window_minutes',
                'f19_beta_threshold',
                'f19_alert_fire_within_minutes'
            )
            """
        )
    )
