"""Framework 17 — Geopolitical Monitor: geopolitical_flag table.

Revision ID: a1b2c3d4e5f7
Revises: f2a3b4c5d6e7
Create Date: 2026-04-25 00:00:00.000000

Creates the geopolitical_flag table, which is the SINGLE SOURCE OF TRUTH
for the operator-set geopolitical state. The system NEVER auto-sets this
flag — only a human operator can write to it.

Valid flag states (stored as strings): NONE, DE_ESCALATING, ACTIVE.
The NOT_SET state is a runtime-only concept — it means no row exists.

Also seeds atlas_config with F17 display thresholds.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # geopolitical_flag — operator-set geopolitical state per session.
    # One row per operator action; multiple rows per session_date allowed
    # (latest set_at wins for carry-forward queries).
    # CRITICAL: This table is READ by F17 service; WRITTEN only by the
    #           POST /api/v1/framework17/flag endpoint.
    # ------------------------------------------------------------------
    op.create_table(
        "geopolitical_flag",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "flag_state",
            sa.String(20),
            nullable=False,
            comment="One of: NONE, DE_ESCALATING, ACTIVE",
        ),
        sa.Column("set_by", sa.String(100), nullable=False),
        sa.Column(
            "set_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("conflict_start_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("session_date", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_geo_flag_session",
        "geopolitical_flag",
        [sa.text("session_date DESC")],
    )

    # ------------------------------------------------------------------
    # Seed F17 config keys into existing atlas_config table.
    # ON CONFLICT DO NOTHING — idempotent across re-runs.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO atlas_config (key, value, description) VALUES
              ('f17_brent_watch_threshold_usd',
               '95',
               'Framework 17: Brent price above which oil watch alert is shown (USD/barrel)'),
              ('f17_brent_elevated_threshold_usd',
               '110',
               'Framework 17: Brent price above which oil is elevated/critical (USD/barrel)'),
              ('f17_cache_ttl_seconds',
               '60',
               'Framework 17: Result cache TTL in seconds (60s — geo flag can change anytime)')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_geo_flag_session", table_name="geopolitical_flag")
    op.drop_table("geopolitical_flag")

    op.execute(
        sa.text(
            """
            DELETE FROM atlas_config
            WHERE key IN (
              'f17_brent_watch_threshold_usd',
              'f17_brent_elevated_threshold_usd',
              'f17_cache_ttl_seconds'
            )
            """
        )
    )
