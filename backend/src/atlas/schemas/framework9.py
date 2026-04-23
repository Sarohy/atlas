"""Pydantic schemas for Framework 9 — Options Flow Signal Hierarchy.

Framework 9 produces the F4 Options Flow score (0-100) that feeds into
Framework 1 at 15% weight.  It aggregates three data sources:

  Source 1: Unusual Whales (whale blocks, flow direction, put/call ratio)
  Source 2: Polygon.io     (dark pool prints, spread_position formula)
  Source 3: Alpha Vantage  (options volume fallback, put/call backup)

Five signal tiers in priority order:
  TIER_1_WHALE         — Single print > $10M confirmed by Unusual Whales
  TIER_2_INSTITUTIONAL — Dark pool > $500K + spread_position > 0.6 + vol > 2% ADV
  TIER_3_UNUSUAL       -- Options volume > 2x 30-day ADV + P/C ratio reversal
  TIER_4_WEAK          -- Volume elevated, below 2x ADV threshold
  TIER_5_NONE          — No qualifying signal, or all data unavailable

Data gap severity levels:
  NONE     — All sources online, no missing fields
  PARTIAL  — Some fields missing but scoring still possible
  MAJOR    — At least one critical source offline, scoring degraded
  CRITICAL — All sources offline, f4_score forced to neutral baseline 55
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DataSourceStatus(StrEnum):
    """Availability state for each external data source."""

    ONLINE = "ONLINE"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    RATE_LIMITED = "RATE_LIMITED"
    OFFLINE = "OFFLINE"


class SignalTier(StrEnum):
    """Five-tier options flow signal hierarchy (checked in priority order)."""

    TIER_1_WHALE = "TIER_1_WHALE"
    TIER_2_INSTITUTIONAL = "TIER_2_INSTITUTIONAL"
    TIER_3_UNUSUAL = "TIER_3_UNUSUAL"
    TIER_4_WEAK = "TIER_4_WEAK"
    TIER_5_NONE = "TIER_5_NONE"


class FlowDirection(StrEnum):
    """Directional bias of the dominant options flow detected by Unusual Whales."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class DataGapDetail(BaseModel):
    """Describes a single missing or unavailable data field.

    Every gap must carry an explicit default_used so the investor can see
    exactly what substitute value was applied (ATLAS non-negotiable: no
    silent failures).
    """

    field: str = Field(description="Logical field name (e.g. 'whale_block', 'dark_pool.bid').")
    source: str = Field(description="Data source responsible for this field.")
    reason: str = Field(description="Why the field is unavailable.")
    impact: str = Field(description="How the gap affects the F4 score.")
    default_used: str | None = Field(
        default=None,
        description="Value substituted when the field is absent.",
    )


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


class Framework9Result(BaseModel):
    """Complete Framework 9 evaluation result for a single ticker.

    Returned by GET /api/v1/framework9/{ticker}.

    f4_score and f4_grade are consumed by FrameworkScoreService._extract_factor
    to compute the F1 conviction score.
    """

    ticker: str

    # ── Core F4 output ──────────────────────────────────────────────────────
    f4_score: float = Field(ge=0.0, le=100.0, description="F4 Options Flow score (0-100).")
    f4_grade: str = Field(
        description=(
            "Grade label derived from f4_score: "
            "'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'WEAK' | 'AVOID'"
        )
    )
    f4_contribution: float = Field(ge=0.0, le=15.0, description="f4_score x 0.15.")

    # ── Signal hierarchy ─────────────────────────────────────────────────────
    signal_tier: SignalTier
    flow_direction: FlowDirection

    # ── Raw data points ──────────────────────────────────────────────────────
    largest_print_usd: float | None = Field(
        default=None, description="Largest single options premium print in USD."
    )
    dark_pool_spread_position: float | None = Field(
        default=None,
        description=(
            "Weighted average (price - bid) / (ask - bid) across dark pool prints. "
            "> 0.6 buy-side, < 0.4 sell-side, 0.4-0.6 neutral."
        ),
    )
    dark_pool_direction: str | None = Field(
        default=None,
        description="'BULLISH' | 'BEARISH' | 'NEUTRAL' | None when unavailable.",
    )
    put_call_ratio: float | None = Field(default=None, description="put_volume / call_volume.")
    options_volume_vs_adv: float | None = Field(
        default=None, description="Total options volume / 30-day average daily volume."
    )

    # ── Modifiers ────────────────────────────────────────────────────────────
    put_call_modifier: int = Field(description="Put/call ratio adjustment applied to base score.")
    dark_pool_modifier: int = Field(description="Dark pool spread_position adjustment.")
    pre_earnings_modifier: int = Field(description="Pre-earnings reduction (negative or 0).")
    index_modifier: int = Field(default=0, description="Index-flow adjustment (reserved).")

    # ── Flags ────────────────────────────────────────────────────────────────
    signal_valid: bool = Field(description="True when minimum signal threshold is met.")
    minimum_threshold_met: bool = Field(
        description=(
            "True when at least one of: ≥10 prints, "
            "single print > 2% ADV, session total > $500K."
        )
    )
    covered_call_exception: bool = Field(
        default=False,
        description=(
            "True when bearish UW signal is overridden by dark pool buy-side "
            "(spread_position > 0.6). Do NOT penalise F4 in this case."
        ),
    )
    covered_call_unverifiable: bool = Field(
        default=False,
        description="True when Polygon is offline so the covered call check cannot run.",
    )
    pre_earnings_reduction: bool = Field(
        default=False, description="True when the 30% pre-earnings reduction was applied."
    )
    conflicting_signals: bool = Field(
        default=False,
        description="True when UW direction and dark pool direction disagree.",
    )
    low_liquidity: bool = Field(
        default=False,
        description="True when 30-day ADV < 100K — score capped at 70.",
    )
    potential_index_flow: bool = Field(
        default=False, description="True when index-rebalancing artefact suspected."
    )

    # ── Source statuses ──────────────────────────────────────────────────────
    uw_status: DataSourceStatus
    polygon_status: DataSourceStatus
    av_status: DataSourceStatus

    # ── Data gap propagation ─────────────────────────────────────────────────
    data_gaps: list[DataGapDetail] = Field(default_factory=list)
    data_gap_severity: str = Field(
        description="'NONE' | 'PARTIAL' | 'MAJOR' | 'CRITICAL'"
    )

    # Propagated to Framework 1 F4 row so the investor sees the gap in context.
    f1_propagation_badge: str | None = Field(
        default=None,
        description=(
            "Short badge text for the Framework 1 F4 row: "
            "'F4 PARTIAL DATA' | 'F4 MAJOR DATA GAP' | 'F4 DATA UNAVAILABLE' | None"
        ),
    )
    f1_propagation_message: str | None = Field(
        default=None, description="Sentence-length explanation for Framework 1."
    )
    f1_propagation_tooltip: str | None = Field(
        default=None, description="Detailed tooltip content for the badge in Framework 1."
    )

    # ── Diagnostics ──────────────────────────────────────────────────────────
    modifiers_skipped: list[str] = Field(
        default_factory=list,
        description="Modifier keys skipped due to unavailable data (e.g. 'put_call', 'dark_pool').",
    )
    warning_level: str = Field(
        description="'NONE' | 'AMBER' | 'RED' — highest severity warning present."
    )
    warning_messages: list[str] = Field(
        default_factory=list,
        description="Human-readable list of all warnings generated during evaluation.",
    )
    breakdown: dict[str, object] = Field(
        default_factory=dict,
        description="Full scoring breakdown for debugging (base_score, tier, modifiers, flags).",
    )
