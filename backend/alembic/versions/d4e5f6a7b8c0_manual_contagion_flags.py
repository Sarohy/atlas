"""Framework 27 — Manual contagion flags: operator confirmation table.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-04-25 00:03:00.000000

Creates the manual_contagion_flags table for operator-confirmed supply chain
disruption events. Used by F27 service to evaluate trigger types that require
human confirmation:
  - ASIA_FREIGHT_DISRUPTION_PCT
  - METALS_DISRUPTION
  - INDIUM_SUPPLY_DISRUPTION

Only an operator can write to this table via:
  POST /api/v1/framework27/contagion/manual-flag
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c0"
down_revision: str = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # manual_contagion_flags — operator-confirmed disruption events.
    # One row per operator action; service reads the most recent active row
    # for each trigger_type on today's session_date.
    # ------------------------------------------------------------------
    op.create_table(
        "manual_contagion_flags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "trigger_type",
            sa.String(50),
            nullable=False,
            comment="One of: ASIA_FREIGHT_DISRUPTION_PCT, METALS_DISRUPTION, "
            "INDIUM_SUPPLY_DISRUPTION",
        ),
        sa.Column("flagged_by", sa.String(100), nullable=False),
        sa.Column(
            "flagged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("session_date", sa.Date, nullable=False),
        sa.Column(
            "active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_manual_flag_session_type",
        "manual_contagion_flags",
        ["session_date", "trigger_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_manual_flag_session_type", table_name="manual_contagion_flags")
    op.drop_table("manual_contagion_flags")
