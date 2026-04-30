"""add_nav_history_and_leaps_tables

Revision ID: c1d2e3f4a5b6
Revises: a3c9e1f2b0d8
Create Date: 2025-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a3c9e1f2b0d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create nav_history table — append-only NAV snapshots for F30 drawdown.
    op.create_table(
        "nav_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("nav_value", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("peak_90d", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("drawdown_pct", sa.Numeric(precision=7, scale=4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_nav_history_date"),
    )
    op.create_index("ix_nav_history_date", "nav_history", ["date"])

    # 2. Create leaps_positions table — Section 17 V1 LEAPS position tracking.
    op.create_table(
        "leaps_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("option_symbol", sa.String(40), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("strike_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("option_type", sa.String(4), nullable=False),
        sa.Column("contracts", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("iv_at_entry", sa.Numeric(precision=7, scale=4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("notes", sa.String(500), nullable=True),
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
        sa.UniqueConstraint("option_symbol", name="uq_leaps_positions_option_symbol"),
    )
    op.create_index("ix_leaps_positions_ticker", "leaps_positions", ["ticker"])

    # 3. Create leaps_iv_history table — time-series IV readings per position.
    op.create_table(
        "leaps_iv_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("option_symbol", sa.String(40), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("iv_value", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["leaps_positions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leaps_iv_history_position_id", "leaps_iv_history", ["position_id"])
    op.create_index("ix_leaps_iv_history_ticker", "leaps_iv_history", ["ticker"])
    op.create_index("ix_leaps_iv_history_date", "leaps_iv_history", ["date"])


def downgrade() -> None:
    op.drop_index("ix_leaps_iv_history_date", "leaps_iv_history")
    op.drop_index("ix_leaps_iv_history_ticker", "leaps_iv_history")
    op.drop_index("ix_leaps_iv_history_position_id", "leaps_iv_history")
    op.drop_table("leaps_iv_history")

    op.drop_index("ix_leaps_positions_ticker", "leaps_positions")
    op.drop_table("leaps_positions")

    op.drop_index("ix_nav_history_date", "nav_history")
    op.drop_table("nav_history")
