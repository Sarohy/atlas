"""add_clear_transition_date_to_portfolio_config

Tracks the date when the market first entered a CLEAR regime, used by
Framework 5 to apply the 2-week transition floor (10 %) before dropping to
the settled floor (8 %).

Revision ID: a3c9e1f2b0d8
Revises: cfbaab08fedb
Create Date: 2026-06-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c9e1f2b0d8"
down_revision: Union[str, None] = "cfbaab08fedb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portfolio_config",
        sa.Column("clear_transition_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_config", "clear_transition_date")
