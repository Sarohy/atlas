"""Framework 18 — 4-Week Trend Gate: seed atlas_config keys.

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c0
Create Date: 2026-04-24

Seeds two atlas_config keys required by Framework 18.
weeks_to_fetch is NOT stored — it is derived in code as threshold + 1.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d1"
down_revision: str = "d4e5f6a7b8c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO atlas_config (key, value, description)
        VALUES
        (
            'f18_consecutive_weeks_threshold',
            '3',
            'Framework 18: number of consecutive S&P 500 (SPY) weekly closing price '
            'declines required to trigger the 4-Week Trend Gate. '
            'weeks_to_fetch is derived in code as this value + 1 — NOT stored separately.'
        ),
        (
            'f18_add_reduction_pct',
            '50',
            'Framework 18: percentage by which aggressive adds are reduced when the '
            '4-Week Trend Gate is active. Applied to conviction-action size_max and '
            'tranche sizing by Framework 6 and Framework 4 respectively.'
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM atlas_config
        WHERE key IN (
            'f18_consecutive_weeks_threshold',
            'f18_add_reduction_pct'
        );
        """
    )
