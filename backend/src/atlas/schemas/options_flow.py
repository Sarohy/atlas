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
        description="LARGE | MID | SMALL — determines anchor table for net-flow scoring."
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
    largest_options_buy_usd: float | None = Field(
        default=None, description="Largest single NEW_BULL or PUT_SELL options premium (USD)."
    )
