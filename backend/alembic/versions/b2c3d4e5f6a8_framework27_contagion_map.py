"""Framework 27 — Supply Chain Contagion Map: contagion rules table.

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-04-25 00:01:00.000000

Creates the framework27_contagion_map table and seeds 11 rows of contagion
rules. These rules are the SINGLE SOURCE OF TRUTH for supply chain contagion
triggers. The service NEVER hardcodes ticker names or thresholds.

Trigger types supported:
  HORMUZ_CLOSURE_DAYS         — measured against conflict_duration_days
  ASIA_FREIGHT_DISRUPTION_PCT — requires operator manual flag
  OIL_PRICE_SUSTAINED_DAYS    — Brent above threshold for sustained duration
  DISRUPTION_DURATION_DAYS    — measured against conflict_duration_days
  METALS_DISRUPTION           — requires operator manual flag
  INDIUM_SUPPLY_DISRUPTION    — requires operator manual flag
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: str = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # framework27_contagion_map — supply chain contagion rules per ticker.
    # Multiple rows per ticker allowed (different trigger types).
    # Service reads ALL active=TRUE rows and evaluates each trigger type.
    # NEVER hardcode these in service code.
    # ------------------------------------------------------------------
    op.create_table(
        "framework27_contagion_map",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("primary_risk", sa.Text, nullable=False),
        sa.Column("secondary_exposure", sa.Text, nullable=False),
        sa.Column(
            "contagion_trigger_type",
            sa.String(50),
            nullable=False,
            comment="One of: HORMUZ_CLOSURE_DAYS, ASIA_FREIGHT_DISRUPTION_PCT, "
            "OIL_PRICE_SUSTAINED_DAYS, DISRUPTION_DURATION_DAYS, "
            "METALS_DISRUPTION, INDIUM_SUPPLY_DISRUPTION",
        ),
        sa.Column("trigger_condition", sa.Text, nullable=False),
        sa.Column(
            "trigger_threshold",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Numeric threshold for the trigger (NULL for operator-flag types)",
        ),
        sa.Column(
            "trigger_unit",
            sa.String(30),
            nullable=True,
            comment="Unit for threshold: days, pct, usd_per_barrel (NULL for operator-flag types)",
        ),
        sa.Column(
            "trigger_duration_days",
            sa.Integer,
            nullable=True,
            comment="How many days the condition must persist (NULL if instantaneous)",
        ),
        sa.Column("action_on_trigger", sa.Text, nullable=False),
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
        "idx_f27_contagion_ticker",
        "framework27_contagion_map",
        ["ticker"],
    )

    op.create_index(
        "idx_f27_contagion_trigger_type",
        "framework27_contagion_map",
        ["contagion_trigger_type"],
    )

    # ------------------------------------------------------------------
    # Seed 11 contagion rules — all values from spec, stored in DB only.
    # NEVER reproduce these values in service code.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO framework27_contagion_map
              (ticker, primary_risk, secondary_exposure, contagion_trigger_type,
               trigger_condition, trigger_threshold, trigger_unit,
               trigger_duration_days, action_on_trigger, active)
            VALUES
              ('TSM',
               'Taiwan military risk',
               'Helium via Strait of Hormuz (~45% global)',
               'HORMUZ_CLOSURE_DAYS',
               'Hormuz closure exceeds threshold days',
               14, 'days', 14,
               'Flag TSM fab supply risk',
               true),
              ('MU',
               'DRAM/HBM cycle',
               'HBM packaging Korea NAND Japan logistics',
               'ASIA_FREIGHT_DISRUPTION_PCT',
               'Asia freight disruption exceeds threshold percentage',
               30, 'pct', NULL,
               'Flag MU supply risk',
               true),
              ('COPX',
               'Copper price',
               'Global slowdown Iran war stagflation',
               'OIL_PRICE_SUSTAINED_DAYS',
               'Oil price above threshold sustained for days',
               110, 'usd_per_barrel', 30,
               'Trim COPX signal',
               true),
              ('LITE',
               'AI capex cycle',
               'Fab inputs specialty chemicals Hormuz',
               'DISRUPTION_DURATION_DAYS',
               'Disruption duration exceeds threshold days',
               60, 'days', 60,
               'Check fab input costs',
               true),
              ('COHR',
               'AI capex cycle',
               'Fab inputs specialty chemicals Hormuz',
               'DISRUPTION_DURATION_DAYS',
               'Disruption duration exceeds threshold days',
               60, 'days', 60,
               'Check fab input costs',
               true),
              ('ETN',
               'Data center build pace',
               'Copper steel specialty metals power',
               'METALS_DISRUPTION',
               'Metals supply disruption flagged by operator',
               NULL, NULL, NULL,
               'Check build cost assumptions',
               true),
              ('NVT',
               'Data center build pace',
               'Copper steel specialty metals power',
               'METALS_DISRUPTION',
               'Metals supply disruption flagged by operator',
               NULL, NULL, NULL,
               'Check build cost assumptions',
               true),
              ('VRT',
               'Data center build pace',
               'Copper steel specialty metals power',
               'METALS_DISRUPTION',
               'Metals supply disruption flagged by operator',
               NULL, NULL, NULL,
               'Check build cost assumptions',
               true),
              ('LITE',
               'AI capex cycle',
               'InP substrate China indium supply control',
               'INDIUM_SUPPLY_DISRUPTION',
               'Indium supply disruption flagged by operator',
               NULL, NULL, NULL,
               'Flag LITE COHR TSEM',
               true),
              ('COHR',
               'AI capex cycle',
               'InP substrate China indium supply control',
               'INDIUM_SUPPLY_DISRUPTION',
               'Indium supply disruption flagged by operator',
               NULL, NULL, NULL,
               'Flag LITE COHR TSEM',
               true),
              ('TSEM',
               'AI capex cycle',
               'InP substrate China indium supply control',
               'INDIUM_SUPPLY_DISRUPTION',
               'Indium supply disruption flagged by operator',
               NULL, NULL, NULL,
               'Flag LITE COHR TSEM',
               true)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_f27_contagion_trigger_type", table_name="framework27_contagion_map")
    op.drop_index("idx_f27_contagion_ticker", table_name="framework27_contagion_map")
    op.drop_table("framework27_contagion_map")
