"""Pydantic schemas for Framework 9 — Options Flow Signal Hierarchy.

Framework 9 produces the F4 Options Flow score (0-100) that feeds into
Framework 1 at 15% weight.  It aggregates three data sources:

  Source 1: Unusual Whales (whale blocks, flow direction, put/call ratio)
  Source 2: Polygon.io     (dark pool prints, spread_position formula)
  Source 3: Alpha Vantage  (options volume fallback, put/call backup)

Five signal tiers in priority order:
  TIER_1_WHALE         — Single print > $10M confirmed by Unusual Whales    (score 88-92)
  TIER_2_INSTITUTIONAL — Dark pool > $500K + spread > 0.6 + vol > 2% ADV   (score 80-85)
  TIER_3_UNUSUAL       — Options volume 150%+ above normal call volume       (score 78-82)
  TIER_4_WEAK          — Moderate unusual call activity                      (score 72-76)
  TIER_5_NONE          — Normal baseline activity                            (score 65-68)
  TIER_1_BEARISH       — Genuine bearish put flow (not covered calls)        (score 55-65)

Data gap severity levels:
  NONE     — All sources online, no missing fields
  PARTIAL  — Some fields missing but scoring still possible
  MAJOR    — At least one critical source offline, scoring degraded
  CRITICAL — All sources offline, f4_score forced to neutral baseline

Pre-earnings adjustment:
  Normal (0-7 days to earnings): 25% reduction
  Exceptional Conviction (3-of-5 criteria): 0% reduction or +10% premium
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


class ExceptionalConvictionDetail(BaseModel):
    """Exceptional Conviction evaluation — 3-of-5 criteria override pre-earnings reduction.

    When active (count >= 3), the normal 25% pre-earnings reduction is replaced
    by a 0% reduction or +10% premium applied to the F4 score.

    Criteria 2-4 require manual / external confirmation and may be None when
    not evaluated this session.  None counts as False toward the total.
    """

    dark_pool_multiple_blocks_gt_1m: bool = Field(
        description=(
            "Criterion 1: dark pool shows multiple (>=2) blocks >$1M premium "
            "in the last 5 trading days."
        )
    )
    transcript_conviction_language: bool | None = Field(
        default=None,
        description=(
            "Criterion 2: transcript uses language like 'sold-out', "
            "'100% committed', 'pricing power'. None = not evaluated."
        ),
    )
    guidance_raised_above_high: bool | None = Field(
        default=None,
        description=(
            "Criterion 3: guidance materially raised prior quarter; analysts "
            "modeling above the high end. None = not evaluated."
        ),
    )
    transcript_cross_references_ge5: bool | None = Field(
        default=None,
        description=(
            "Criterion 4: >=5 transcript cross-references from other universe "
            "names confirming the same thesis. None = not evaluated."
        ),
    )
    bullish_skew_despite_elevated_iv: bool = Field(
        description=(
            "Criterion 5: options flow shows unusual bullish skew (call buying) "
            "despite elevated IV (call/put ratio > 2.0 and BULLISH flow direction)."
        )
    )
    count: int = Field(
        ge=0,
        le=5,
        description="Number of criteria that evaluate to True (None counts as False).",
    )
    active: bool = Field(
        description="True when count >= 3 — overrides the normal pre-earnings reduction."
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
            "Grade label derived from f4_score: 'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'WEAK' | 'AVOID'"
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
            "True when at least one of: ≥10 prints, single print > 2% ADV, session total > $500K."
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
        default=False,
        description=(
            "True when the pre-earnings window (0-7 days) is active and a modifier "
            "was applied. When Exceptional Conviction is active the modifier is +10%; "
            "otherwise it is a 25% reduction."
        ),
    )
    days_to_earnings: int | None = Field(
        default=None,
        description="Calendar days until next earnings date. None when unavailable.",
    )
    exceptional_conviction: ExceptionalConvictionDetail | None = Field(
        default=None,
        description=(
            "Exceptional Conviction detail. Populated only when the pre-earnings "
            "window is active. None when outside the window or when F4 is unavailable."
        ),
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
    data_gap_severity: str = Field(description="'NONE' | 'PARTIAL' | 'MAJOR' | 'CRITICAL'")

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
