"""Framework 12 — Catalyst No-Fly Zone database tables.

Revision ID: e4f5a6b7c8d9
Revises: d98ec33d8a3c
Create Date: 2025-07-14 00:00:00.000000

Creates four new tables:
  - catalyst_events      — non-earnings catalysts entered by operator
  - framework12_overrides — per-action human overrides
  - decision_trace       — append-only audit log (never UPDATE/DELETE)
  - atlas_config         — runtime config key-value store

Seeds atlas_config with F12 spec constants.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str = "d98ec33d8a3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # atlas_config — runtime constants (never hardcode in app code)
    # ------------------------------------------------------------------
    op.create_table(
        "atlas_config",
        sa.Column("key", sa.String(100), primary_key=True, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed required config values — use INSERT ... ON CONFLICT DO NOTHING
    # so subsequent upgrades are idempotent.
    op.execute(
        sa.text(
            """
            INSERT INTO atlas_config (key, value, description) VALUES
              ('f12_catalyst_window_days',
               '7',
               'Framework 12: calendar-day window before a catalyst during which no-fly zone is active'),
              ('f12_exit_deferral_trading_days',
               '10',
               'Framework 12: trading days after catalyst date before Section 16 exit rule resumes')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )

    # ------------------------------------------------------------------
    # catalyst_events — non-earnings catalyst events
    # ------------------------------------------------------------------
    op.create_table(
        "catalyst_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("catalyst_type", sa.String(50), nullable=False),
        sa.Column("catalyst_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")
        ),
        sa.Column("entered_by", sa.String(100), nullable=True),
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
        "idx_catalyst_events_ticker_date",
        "catalyst_events",
        ["ticker", "catalyst_date"],
    )

    # ------------------------------------------------------------------
    # framework12_overrides — per-action human overrides
    # ------------------------------------------------------------------
    op.create_table(
        "framework12_overrides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("override_reason", sa.Text, nullable=False),
        sa.Column(
            "override_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("override_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entered_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Partial index — only index rows where override is still active.
    op.execute(
        sa.text(
            """
            CREATE INDEX idx_f12_overrides_ticker
            ON framework12_overrides (ticker, action_type)
            WHERE override_active = TRUE
            """
        )
    )

    # ------------------------------------------------------------------
    # decision_trace — append-only immutable audit log
    # ------------------------------------------------------------------
    op.create_table(
        "decision_trace",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "decision_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger", sa.String(100), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=True),
        sa.Column("catalyst_type", sa.String(50), nullable=True),
        sa.Column("catalyst_date", sa.String(20), nullable=True),
        sa.Column("days_to_catalyst", sa.Integer, nullable=True),
        sa.Column(
            "actions_blocked", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "framework_states", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "regime_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "data_freshness", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "human_override",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("override_action", sa.String(50), nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column(
            "visible_in_briefing",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_decision_trace_decision_id",
        "decision_trace",
        ["decision_id"],
        unique=True,
    )
    op.create_index(
        "idx_decision_trace_ticker_ts",
        "decision_trace",
        ["ticker", sa.text("timestamp_utc DESC")],
    )


def downgrade() -> None:
    op.drop_table("decision_trace")
    op.drop_table("framework12_overrides")
    op.drop_table("catalyst_events")
    op.drop_table("atlas_config")
