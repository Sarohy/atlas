"""rename_positions_table_to_tickers

Revision ID: b5b08cfb7911
Revises: e8937b49790b
Create Date: 2026-04-08 00:53:49.327097

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5b08cfb7911'
down_revision: Union[str, None] = 'e8937b49790b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename table in-place — preserves all existing rows and sequences.
    op.rename_table("positions", "tickers")
    op.execute("ALTER INDEX IF EXISTS ix_positions_ticker RENAME TO ix_tickers_ticker")
    op.execute("ALTER SEQUENCE IF EXISTS positions_id_seq RENAME TO tickers_id_seq")


def downgrade() -> None:
    op.execute("ALTER SEQUENCE IF EXISTS tickers_id_seq RENAME TO positions_id_seq")
    op.execute("ALTER INDEX IF EXISTS ix_tickers_ticker RENAME TO ix_positions_ticker")
    op.rename_table("tickers", "positions")
