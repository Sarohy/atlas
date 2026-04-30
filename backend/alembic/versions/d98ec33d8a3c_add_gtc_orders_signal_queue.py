"""Add gtc_orders and signal_queue tables for Framework 11.

Revision ID: d98ec33d8a3c
Revises: c1d2e3f4a5b6
Create Date: 2026-04-23

Framework 11 (Cash Floor Enforcer) requires:
  gtc_orders   — tracks open GTC buy orders for the GTC aggregate window
  signal_queue — holds buy signals queued when the cash floor is violated
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d98ec33d8a3c"
down_revision: str = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── gtc_orders ──────────────────────────────────────────────────────────
    op.create_table(
        "gtc_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("limit_price", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_gtc_orders_status_side",
        "gtc_orders",
        ["status", "side"],
    )

    # ── signal_queue ─────────────────────────────────────────────────────────
    op.create_table(
        "signal_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("queue_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="QUEUED"),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_signal_queue_status",
        "signal_queue",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("idx_signal_queue_status", table_name="signal_queue")
    op.drop_table("signal_queue")
    op.drop_index("idx_gtc_orders_status_side", table_name="gtc_orders")
    op.drop_table("gtc_orders")
