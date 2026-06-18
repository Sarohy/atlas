"""Pydantic schemas for the F4 Options Flow endpoint (v2 spec).

F4 v2 produces a single 0-100 composite score from:
  - Dark-pool signed net flow over the last 5 trading sessions
  - Options signed net flow over the same window
combined 50/50 (or single-source fallback), with the per-flow score mapped
through a market-cap-tiered (LARGE / MID / SMALL) anchor table.

See ``atlas.services.options_flow_service`` for the scoring pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OptionsFlowResponse(BaseModel):
    """Complete F4 Options Flow analysis for a single ticker (F4 v2 spec).

    Scoring is now driven by signed net flows over a 5-session rolling window,
    mapped to a 0-100 score via a market-cap-tiered anchor table. The legacy
    sub-indicator structure (whale_block, call_put_ratio, volume_oi,
    dark_pool, sweep_type) has been removed; the two new sub-scores are
    `dark_pool_score` and `options_flow_score`, combined 50/50 into
    `f4_score`.

    `f4_score` and `f4_grade` are preserved for backward compatibility with
    Framework 9 and Framework 1's score aggregator.
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # ---- Composite (kept for F9 + F1 compatibility) -----------------------
    f4_score: int = Field(ge=0, le=100, description="Composite F4 Options Flow score (0-100).")
    f4_grade: str = Field(description="F4 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID")

    # ---- Sub-scores (new) ------------------------------------------------
    dark_pool_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="0-100 score from signed dark-pool net flow. None when DP data missing.",
    )
    options_flow_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="0-100 score from signed options net flow. None when options data missing.",
    )

    # ---- Net flows (signed, 5-session rolling window) --------------------
    dark_pool_net_flow_usd: float | None = Field(
        default=None,
        description="Sum(BUY premium) - Sum(SELL premium) for dark-pool prints over 5 sessions.",
    )
    options_net_flow_usd: float | None = Field(
        default=None,
        description=(
            "Sum(NEW_BULL + PUT_SELL premium) - Sum(NEW_BEAR premium) for options prints "
            "over 5 sessions."
        ),
    )

    # ---- Market-cap context ----------------------------------------------
    market_cap_usd: float | None = Field(
        default=None, description="Market cap from Polygon (USD). None when unavailable."
    )
    market_cap_tier: str = Field(
        description="MEGA | LARGE | MID | SMALL — determines anchor table for net-flow scoring."
    )

    # ---- Direction (derived from signs of net flows) ---------------------
    flow_direction: str = Field(
        description="BULLISH | BEARISH | NEUTRAL — derived from combined net flows."
    )

    # ---- Data quality / provenance ---------------------------------------
    data_source: str = Field(
        description="BOTH | DARK_POOL_ONLY | OPTIONS_ONLY | DATA_GAP — which sources contributed."
    )
    data_gap_reason: str | None = Field(
        default=None,
        description="Human-readable reason when data_source != BOTH; None otherwise.",
    )
    lookback_sessions: int = Field(
        default=5, description="Trailing trading-session window length (always 5 in v2)."
    )

    # ---- Detail counts / extremes (consumed by F9) -----------------------
    dark_pool_prints_count: int = Field(
        default=0, description="Count of classified BUY+SELL dark-pool prints in window."
    )
    dark_pool_sessions_covered: int | None = Field(
        default=None,
        description=(
            "Distinct trading sessions the dark-pool net flow actually spans. "
            "Less than lookback_sessions means the pagination cap was hit on a very "
            "high-volume name (partial coverage) — the net flow understates the full "
            "window, though the LARGE-tier score typically already saturates."
        ),
    )
    dark_pool_truncated: bool = Field(
        default=False,
        description=(
            "True when the dark-pool fetch hit the page cap without covering the full "
            "lookback window (high-volume truncation). Never silently dropped."
        ),
    )
    dark_pool_large_buy_count: int = Field(
        default=0,
        description=(
            "Count of dark-pool BUY prints >$1M in window — feeds F9 Exceptional "
            "Conviction criterion 1."
        ),
    )
    largest_dark_pool_buy_usd: float | None = Field(
        default=None, description="Largest single dark-pool BUY print premium (USD)."
    )
    largest_kept_buy_usd: float | None = Field(
        default=None,
        description="Largest single kept (non-plumbing) dark-pool BUY print premium (USD).",
    )
    largest_stripped_print_usd: float | None = Field(
        default=None,
        description="Largest stripped plumbing/settlement dark-pool print premium (USD).",
    )
    largest_options_buy_usd: float | None = Field(
        default=None, description="Largest single NEW_BULL or PUT_SELL options premium (USD)."
    )

    # ---- F4a reconciliation (raw vs stripped vs kept) ---------------------
    raw_dark_pool_notional_usd: float = Field(
        default=0.0,
        description="Raw dark-pool notional across window before plumbing strip (USD).",
    )
    stripped_plumbing_notional_usd: float = Field(
        default=0.0,
        description="Dark-pool notional stripped as plumbing/settlement (USD).",
    )
    kept_dark_pool_notional_usd: float = Field(
        default=0.0,
        description="Kept non-plumbing dark-pool notional after strip (USD).",
    )
    strict_buy_notional_usd: float = Field(
        default=0.0,
        description="Strict bid/ask-classified dark-pool BUY notional (USD).",
    )
    strict_sell_notional_usd: float = Field(
        default=0.0,
        description="Strict bid/ask-classified dark-pool SELL notional (USD).",
    )
    midpoint_lean_buy_notional_usd: float = Field(
        default=0.0,
        description="All kept midpoint-lean dark-pool BUY notional (USD).",
    )
    midpoint_lean_sell_notional_usd: float = Field(
        default=0.0,
        description="All kept midpoint-lean dark-pool SELL notional (USD).",
    )
    net_classified_flow_usd: float = Field(
        default=0.0,
        description="Net kept classified dark-pool flow: buy notional minus sell notional (USD).",
    )
    buy_share: float | None = Field(
        default=None,
        description="Midpoint-lean kept buy-share: buy / (buy + sell).",
    )
    stripped_notional_by_reason: dict[str, float] = Field(
        default_factory=dict,
        description="Stripped plumbing notional grouped by canonical strip reason.",
    )
    session_coverage: int | None = Field(
        default=None,
        description="Distinct dark-pool sessions covered in the current F4a window.",
    )
    confidence: str = Field(
        default="No dark-pool data",
        description="F4a confidence label mirrored from dark_pool_confidence for UI reconciliation.",
    )

    # ---- Signal quality / strategy context (new) -------------------------
    dark_pool_settlement_ratio: float | None = Field(
        default=None,
        description=(
            "Fraction of dark-pool prints classified as SETTLEMENT over the 5-session window. "
            "Low ratios (< 0.20) indicate directional, non-settlement block activity."
        ),
    )
    options_strategy_type: str | None = Field(
        default=None,
        description="Deprecated/disabled — the covered-call posture tag was removed (always None).",
    )

    # ---- Layer 2: stock-tape state ("chips") + Layer 3: clearance ---------
    dark_pool_state: str = Field(
        default="UNKNOWN",
        description=(
            "Stock-tape state from per-session dark-pool flow: FRESH_ACCUMULATION | "
            "PERSISTENT_ACCUMULATION | NEUTRAL_MIXED | FADING | ACTIVE_DISTRIBUTION | UNKNOWN. "
            "A state, not a score — kept separate from f4_score."
        ),
    )
    dark_pool_state_reason: str | None = Field(
        default=None, description="Plain-English reason for the dark_pool_state chip."
    )
    clearance: str = Field(
        default="WATCH",
        description=(
            "Entry decision combining the F4 options score (resume) with the stock-tape chip "
            "(this week): CLEARED | WATCH | REVOKED. ACTIVE_DISTRIBUTION forces REVOKED."
        ),
    )
    clearance_reason: str | None = Field(
        default=None, description="Plain-English reason for the clearance decision."
    )

    # ---- Hedge-structure flag — context only, never rewrites f4_score --------
    hedge_structure: str = Field(
        default="NONE",
        description=(
            "Options hedge/structure context, tagged separately from f4_score: "
            "DIRECTIONAL_BEARISH | PROTECTIVE_HEDGE | HEDGED_BULLISH | PUT_SELLING | "
            "BULLISH | MIXED | NONE. Bearish put demand shows through F4 unless the "
            "structure is clearly protective (bullish side confirming)."
        ),
    )
    hedge_structure_reason: str | None = Field(
        default=None, description="Plain-English reason for the hedge_structure flag."
    )
    bullish_share: float | None = Field(
        default=None,
        description=(
            "bullish_premium / (bullish_premium + bearish_premium) over the window, "
            "where bullish = call_ask + put_bid and bearish = put_ask + call_bid "
            "(moneyness/expiry-weighted). Drives f4_score. None when no directional flow."
        ),
    )
    f4_state: str = Field(
        default="Neutral",
        description=(
            "F4 state label from the score band (Implementation Audit): Strong bullish | "
            "Bullish | Mild bullish | Constructive | Neutral-constructive | Neutral | "
            "Mild bearish | Bearish | Aggressive bearish. Never 'Neutral' below 45."
        ),
    )
    f4_add_impact: str = Field(
        default="No edge — no fresh add from F4b",
        description=(
            "Gate-aware F4b add impact — never a bare BUY. A full add is only emitted by "
            "the Flow Monitor after F4a/VWAP/cluster/size/regime gates clear."
        ),
    )
    dark_pool_confidence: str = Field(
        default="No dark-pool data",
        description=(
            "F4a dark-pool coverage confidence: High (full) | Medium (partial) | "
            "Low (1 session / truncation) | No dark-pool data."
        ),
    )
    # ---- Multi-window F4b (current-session-weighted) — Multi-Window Pull Spec ----
    live_tape_state: str = Field(
        default="Data gap",
        description=(
            "Today's tape vs the 5-session baseline: Improving | Deteriorating | "
            "Bullish persistent | Bearish persistent | Bullish reversal | Bearish reversal | "
            "Mixed / structured | Data gap. Lets timing react even when the average disagrees."
        ),
    )
    persistence_state: str = Field(
        default="Neutral / constructive",
        description="F4 state label of the 5-session persistence window (vs the live blend).",
    )
    current_session_net_usd: float | None = Field(
        default=None, description="Today's net directional options premium (bullish - bearish)."
    )
    otm_call_ask_usd: float | None = Field(
        default=None, description="OTM call ask-side (bought) premium over the window."
    )
    otm_put_ask_usd: float | None = Field(
        default=None, description="OTM put ask-side (bought) premium over the window."
    )

    # ---- Flow Monitor — the final action gate (only add authority) -----------
    flow_monitor_action: str = Field(
        default="WATCH",
        description=(
            "Final Flow Monitor action combining F4b + F4a + live tape (+ order-time "
            "gates): ADD_ELIGIBLE | ADD_PENDING_GATES | STARTER | WATCH | CONFLICT | "
            "MIXED_ABSORPTION | TRIM_WATCH | AVOID. The only layer allowed to clear an add."
        ),
    )
    flow_monitor_reason: str | None = Field(
        default=None, description="Plain-English reason for the Flow Monitor action."
    )
