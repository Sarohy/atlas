"""Section 16 (Entry Gatekeeper) + Framework 12 (Decision Matrix) — full replacement.

Revision ID: g5h6i7j8k9l0
Revises: a1b2c3d4e5f6
Create Date: 2026-05-12 00:00:00.000000

DROPS the old "exit-rules" Section 16 and old "catalyst no-fly zone" F12 entirely:
  - exit_rule_cycles, gap_down_events, grok_scores
  - catalyst_events, framework12_overrides
  - all atlas_config rows with key prefix s16_ or f12_

CREATES the new "Entry Gatekeeper" + "Decision Matrix" pipeline:
  - ticker_track_assignment       (one row per ticker, Track A or Track B)
  - rule4_portfolio_fit           (one row per ticker per day, operator-set)
  - override_usage_tracking       (one row per ticker per earnings cycle)
  - framework12_decision_matrix   (8 priority rows seeded)

SEEDS atlas_config with 17 new s16_* threshold keys + 8 decision-matrix rows.

NOTE on values: All thresholds, day counts, sizing percentages live in DB.
Application code reads them at evaluation time — never hardcoded.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g5h6i7j8k9l0"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Seed payloads — kept at module scope so they can be inspected/audited.
# ---------------------------------------------------------------------------

_S16_CONFIG_SEEDS: list[tuple[str, str, str]] = [
    ("s16_priority1_earnings_days", "14",
     "Rule 1 / Priority 1: max calendar days to next earnings (Track A row 1)."),
    ("s16_priority2_earnings_min_days", "15",
     "Rule 1 / Priority 2: minimum calendar days to next earnings."),
    ("s16_priority2_earnings_max_days", "45",
     "Rule 1 / Priority 2: maximum calendar days to next earnings."),
    ("s16_priority1_dark_pool_usd", "15000000",
     "Rule 1 / Priority 1: dark-pool single-print USD threshold (OR with flow)."),
    ("s16_priority1_flow_usd", "2000000",
     "Rule 1 / Priority 1: bullish options flow USD threshold (OR with dark pool)."),
    ("s16_priority2_dark_pool_usd", "20000000",
     "Rule 1 / Priority 2: dark-pool single-print USD threshold."),
    ("s16_priority2_flow_usd", "3000000",
     "Rule 1 / Priority 2: bullish options flow USD threshold."),
    ("s16_priority3_dark_pool_usd", "40000000",
     "Rule 1 / Priority 3: dark-pool USD threshold (AND with flow)."),
    ("s16_priority3_flow_usd", "2000000",
     "Rule 1 / Priority 3: bullish options flow USD threshold (AND with dark pool)."),
    ("s16_catalyst_max_days", "45",
     "Rule 2: max calendar days to upcoming earnings/catalyst event."),
    ("s16_parabolic_catalyst_days", "30",
     "Rule 2 / Track B: parabolic-exception window (days to earnings)."),
    ("s16_rule3_near_high_pct", "5",
     "Rule 3: percent below 365d high considered 'near high' (entry blocked)."),
    ("s16_rule3_pullback_pct", "8",
     "Rule 3: required percent pullback from recent high to allow entry."),
    ("s16_override_dark_pool_usd", "25000000",
     "Override: dark-pool USD threshold within lookback window (Track A only)."),
    ("s16_override_flow_usd", "3500000",
     "Override: bullish options flow USD threshold within lookback window."),
    ("s16_override_max_allocation_pct", "5",
     "Override: max single-position allocation as percent of NAV."),
    ("s16_override_lookback_days", "5",
     "Override: trading-day lookback window for stronger-signal evidence."),
]

# (priority_code, priority_label, track, e_max, e_min, override_req,
#  underweight_req, strong_flow_req, size_min, size_max, timing_rule,
#  watchlist_only, priority_order)
_DECISION_MATRIX_SEEDS: list[tuple] = [
    ("1-OVERRIDE", "Priority 1 with Override", "TRACK_A", 14, None, True,
     False, False, "1.75", "2.50", "Execute before the print", False, 1),
    ("2-OVERRIDE", "Priority 2 with Override", "TRACK_A", 45, 15, True,
     False, False, "1.50", "2.00", "Immediately or on minor dip", False, 2),
    ("1", "Priority 1", "TRACK_A", 14, None, False,
     False, False, "1.00", "1.50", "Execute before the print", False, 3),
    ("1b", "Priority 1 (Track B)", "TRACK_B", 30, None, False,
     False, False, "0.40", "0.60", "Execute before the print", False, 4),
    ("2", "Priority 2", "TRACK_A", 45, 15, False,
     True, False, "1.25", "1.75", "Only on dip to defined zone", False, 5),
    ("2b", "Priority 2 (Track B)", "TRACK_B", 45, 15, False,
     False, False, "0.50", "0.75", "Only on dip to defined zone", False, 6),
    ("3", "Priority 3", "TRACK_A", None, None, False,
     False, True, "0.75", "1.00", "On 8-12% pullback", False, 7),
    ("4", "Watchlist Only", None, None, None, False,
     False, False, "0.00", "0.00", "Set alerts, wait for deeper dip", True, 8),
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Drop OLD tables + OLD config keys (S16 exit-rules + F12 no-fly).
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            "DELETE FROM atlas_config "
            "WHERE key LIKE 's16_%' OR key LIKE 'f12_%'"
        )
    )
    for table in (
        "framework12_overrides",
        "catalyst_events",
        "grok_scores",
        "gap_down_events",
        "exit_rule_cycles",
    ):
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table} CASCADE"))

    # ------------------------------------------------------------------
    # 2. ticker_track_assignment — operator assigns each ticker to a Track.
    # ------------------------------------------------------------------
    op.create_table(
        "ticker_track_assignment",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("track", sa.String(10), nullable=False),
        sa.Column("assigned_by", sa.String(100), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", name="uq_ticker_track_assignment_ticker"),
        sa.CheckConstraint(
            "track IN ('TRACK_A', 'TRACK_B')",
            name="ck_ticker_track_assignment_track",
        ),
    )

    # ------------------------------------------------------------------
    # 3. rule4_portfolio_fit — operator's daily YES/NO for portfolio fit.
    # ------------------------------------------------------------------
    op.create_table(
        "rule4_portfolio_fit",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("fit_date", sa.Date(), nullable=False),
        sa.Column("fits_portfolio", sa.Boolean(), nullable=False),
        sa.Column("cluster_gap", sa.Text(), nullable=True),
        sa.Column("redundancy_check", sa.Text(), nullable=True),
        sa.Column("set_by", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "fit_date",
            name="uq_rule4_portfolio_fit_ticker_date",
        ),
    )
    op.create_index(
        "ix_rule4_portfolio_fit_ticker_date",
        "rule4_portfolio_fit", ["ticker", "fit_date"],
    )

    # ------------------------------------------------------------------
    # 4. override_usage_tracking — one override allowed per earnings cycle.
    # ------------------------------------------------------------------
    op.create_table(
        "override_usage_tracking",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("earnings_cycle_start", sa.Date(), nullable=False),
        sa.Column("earnings_cycle_end", sa.Date(), nullable=False),
        sa.Column(
            "override_used",
            sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("override_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_used_by", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "earnings_cycle_start",
            name="uq_override_usage_ticker_cycle",
        ),
    )
    op.create_index(
        "ix_override_usage_ticker", "override_usage_tracking", ["ticker"],
    )

    # ------------------------------------------------------------------
    # 5. framework12_decision_matrix — priority rows for sizing pipeline.
    # ------------------------------------------------------------------
    op.create_table(
        "framework12_decision_matrix",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("priority_code", sa.String(20), nullable=False),
        sa.Column("priority_label", sa.String(100), nullable=False),
        sa.Column("track", sa.String(10), nullable=True),
        sa.Column("earnings_max_days", sa.Integer(), nullable=True),
        sa.Column("earnings_min_days", sa.Integer(), nullable=True),
        sa.Column(
            "override_required",
            sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "underweight_required",
            sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "strong_flow_required",
            sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("size_min_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("size_max_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("timing_rule", sa.Text(), nullable=False),
        sa.Column(
            "is_watchlist_only",
            sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("priority_code", name="uq_decision_matrix_priority_code"),
        sa.CheckConstraint(
            "track IS NULL OR track IN ('TRACK_A', 'TRACK_B')",
            name="ck_decision_matrix_track",
        ),
    )
    op.create_index(
        "ix_decision_matrix_order", "framework12_decision_matrix",
        ["priority_order"],
    )

    # ------------------------------------------------------------------
    # 6. Seed atlas_config with 17 new s16_* threshold rows.
    # ------------------------------------------------------------------
    config_table = sa.table(
        "atlas_config",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        config_table,
        [
            {"key": k, "value": v, "description": d}
            for (k, v, d) in _S16_CONFIG_SEEDS
        ],
    )

    # ------------------------------------------------------------------
    # 7. Seed framework12_decision_matrix with 8 priority rows.
    # ------------------------------------------------------------------
    matrix_table = sa.table(
        "framework12_decision_matrix",
        sa.column("priority_code", sa.String),
        sa.column("priority_label", sa.String),
        sa.column("track", sa.String),
        sa.column("earnings_max_days", sa.Integer),
        sa.column("earnings_min_days", sa.Integer),
        sa.column("override_required", sa.Boolean),
        sa.column("underweight_required", sa.Boolean),
        sa.column("strong_flow_required", sa.Boolean),
        sa.column("size_min_pct", sa.Numeric),
        sa.column("size_max_pct", sa.Numeric),
        sa.column("timing_rule", sa.Text),
        sa.column("is_watchlist_only", sa.Boolean),
        sa.column("priority_order", sa.Integer),
    )
    op.bulk_insert(
        matrix_table,
        [
            {
                "priority_code": code,
                "priority_label": label,
                "track": track,
                "earnings_max_days": e_max,
                "earnings_min_days": e_min,
                "override_required": override_req,
                "underweight_required": underweight_req,
                "strong_flow_required": strong_flow_req,
                "size_min_pct": size_min,
                "size_max_pct": size_max,
                "timing_rule": timing,
                "is_watchlist_only": watchlist_only,
                "priority_order": order,
            }
            for (code, label, track, e_max, e_min, override_req,
                 underweight_req, strong_flow_req, size_min, size_max,
                 timing, watchlist_only, order) in _DECISION_MATRIX_SEEDS
        ],
    )


def downgrade() -> None:
    # Drop new tables in reverse creation order.
    op.drop_index(
        "ix_decision_matrix_order", table_name="framework12_decision_matrix",
    )
    op.drop_table("framework12_decision_matrix")
    op.drop_index(
        "ix_override_usage_ticker", table_name="override_usage_tracking",
    )
    op.drop_table("override_usage_tracking")
    op.drop_index(
        "ix_rule4_portfolio_fit_ticker_date", table_name="rule4_portfolio_fit",
    )
    op.drop_table("rule4_portfolio_fit")
    op.drop_table("ticker_track_assignment")

    # Remove the new s16_* config seeds we added.
    op.execute(
        sa.text(
            "DELETE FROM atlas_config WHERE key LIKE 's16_%'"
        )
    )

    # NOTE: We do NOT recreate the dropped legacy tables here.  This downgrade
    # is intentionally one-way for the table drops — the old code that
    # depended on them has been removed from the codebase.
