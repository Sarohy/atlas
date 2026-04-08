"""add_clusters_table_and_cluster_id_to_tickers

Revision ID: f1b3c2a0d1e4
Revises: b43218f0415e
Create Date: 2026-04-08 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b3c2a0d1e4"
down_revision: Union[str, None] = "b43218f0415e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the clusters table.
    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(10), nullable=False),
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
        sa.UniqueConstraint("name"),
    )

    # 2. Add cluster_id FK column to tickers (nullable, SET NULL on delete).
    op.add_column("tickers", sa.Column("cluster_id", sa.Integer(), nullable=True))
    op.create_index("ix_tickers_cluster_id", "tickers", ["cluster_id"])
    op.create_foreign_key(
        "fk_tickers_cluster_id",
        "tickers",
        "clusters",
        ["cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Reverse order: drop FK first, then column, then table.
    op.drop_constraint("fk_tickers_cluster_id", "tickers", type_="foreignkey")
    op.drop_index("ix_tickers_cluster_id", table_name="tickers")
    op.drop_column("tickers", "cluster_id")
    op.drop_table("clusters")
