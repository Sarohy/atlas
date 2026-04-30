"""Framework 28 — War Duration Ladder: ladder tiers table.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-04-25 00:02:00.000000

Creates the framework28_ladder_tiers table and seeds 4 ladder tier rows.
These tiers are the SINGLE SOURCE OF TRUTH for war duration portfolio
guidance. The service NEVER hardcodes duration or Brent price thresholds.

Tier matching logic (in service):
  Find the active tier where:
    duration_min_days <= conflict_duration_days
    AND (duration_max_days IS NULL OR conflict_duration_days <= duration_max_days)
    AND brent_range_low <= current_brent
    AND (brent_range_high IS NULL OR current_brent <= brent_range_high)
  If multiple tiers match, use the highest tier_order (most severe).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b9"
down_revision: str = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # framework28_ladder_tiers — war duration portfolio action tiers.
    # Tier 4 has NULL duration_max_days (open-ended: 91+ days).
    # Tier 4 has NULL brent_range_high (no upper cap).
    # ------------------------------------------------------------------
    op.create_table(
        "framework28_ladder_tiers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tier_order",
            sa.Integer,
            nullable=False,
            unique=True,
            comment="1 = lowest severity, 4 = highest severity",
        ),
        sa.Column(
            "duration_min_days",
            sa.Integer,
            nullable=False,
            comment="Minimum conflict duration (inclusive) in days",
        ),
        sa.Column(
            "duration_max_days",
            sa.Integer,
            nullable=True,
            comment="Maximum conflict duration (inclusive) in days; NULL = open-ended",
        ),
        sa.Column(
            "brent_range_low",
            sa.Numeric(6, 2),
            nullable=False,
            comment="Minimum Brent price (inclusive) in USD/barrel",
        ),
        sa.Column(
            "brent_range_high",
            sa.Numeric(6, 2),
            nullable=True,
            comment="Maximum Brent price (inclusive) in USD/barrel; NULL = open-ended",
        ),
        sa.Column(
            "fed_implication",
            sa.Text,
            nullable=False,
            comment="Fed policy implication text for this tier",
        ),
        sa.Column(
            "portfolio_action",
            sa.Text,
            nullable=False,
            comment="Portfolio action guidance text for this tier",
        ),
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

    # ------------------------------------------------------------------
    # Seed 4 ladder tiers — all values from spec, stored in DB only.
    # NEVER reproduce these threshold values in service code.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO framework28_ladder_tiers
              (tier_order, duration_min_days, duration_max_days,
               brent_range_low, brent_range_high,
               fed_implication, portfolio_action, active)
            VALUES
              (1, 0, 14, 95.00, 115.00,
               'Hold — wait for data',
               'Framework 7 active. Catalyst-only buys. No new positions.',
               true),
              (2, 15, 30, 100.00, 120.00,
               'No cuts 2026 locked in',
               'Reduce high-multiple names 15%. Raise cash to 25%. Increase GLD and NEM.',
               true),
              (3, 30, 90, 105.00, 130.00,
               'Rate hike risk emerges 2027',
               'Reduce growth names to minimum weights. Target 30%+ cash. Energy longs only new adds.',
               true),
              (4, 91, NULL, 110.00, NULL,
               'Macquarie hike scenario 1H27',
               'Full defensive posture. Only MU TSM GLD NEM CEG ATI as core. Everything else minimum weight or sold.',
               true)
            """
        )
    )


def downgrade() -> None:
    op.drop_table("framework28_ladder_tiers")
