"""add_watchlist_table

Revision ID: cfbaab08fedb
Revises: f1b3c2a0d1e4
Create Date: 2026-04-08 21:09:46.834175

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfbaab08fedb'
down_revision: Union[str, None] = 'f1b3c2a0d1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("previous_close", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("day_change", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("day_change_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("beta", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("ticker"),
    )
    op.create_index(op.f("ix_watchlist_ticker"), "watchlist", ["ticker"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_watchlist_ticker"), table_name="watchlist")
    op.drop_table("watchlist")
