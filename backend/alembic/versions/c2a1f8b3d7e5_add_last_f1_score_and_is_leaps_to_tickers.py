"""Add last_f1_score and is_leaps to tickers.

Revision ID: c2a1f8b3d7e5
Revises: g5h6i7j8k9l0
Create Date: 2026-05-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c2a1f8b3d7e5"
down_revision = "g5h6i7j8k9l0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column("last_f1_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tickers",
        sa.Column(
            "is_leaps",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tickers", "is_leaps")
    op.drop_column("tickers", "last_f1_score")
