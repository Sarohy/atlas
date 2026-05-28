"""Pydantic schemas for the F2 Earnings Quality endpoint — v7.3.4 flat structure.

EarningsResponse (= F2Result) is a single flat model with all sub-factor fields.
Sub-factors:
  sf1  Revenue Growth YoY       30%  — decimal input, banded 0-100
  sf2  Gross Margin Trend       20%  — bps YoY change, banded 0-100
  sf3  EPS Beat Consistency     20%  — 4Q window; excluded when pre-profitability
  sf4  Guidance Reliability     15%  — 4Q track record; DATA_GAP default = 10
  sf5  Forward Visibility       15%  — transcript NLP label, scored 0/30/60/80/100

framework_score_service.py accesses: .data_available, .f2_score, .f2_grade
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# F2 grade literals (kept for backward-compat — also used by earnings_service)
# ---------------------------------------------------------------------------


class F2Grade:
    """Named constants for the five F2 earnings-quality grades."""

    STRONG_BUY: Final[str] = "STRONG BUY"
    BUY: Final[str] = "BUY"
    NEUTRAL: Final[str] = "NEUTRAL"
    WEAK: Final[str] = "WEAK"
    AVOID: Final[str] = "AVOID"


# ---------------------------------------------------------------------------
# Flat top-level response schema — v7.3.4
# ---------------------------------------------------------------------------


class EarningsResponse(BaseModel):
    """Complete F2 Earnings Quality result for a single ticker (v7.3.4 flat layout)."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # Sub-factor 1 — Revenue Growth YoY (weight 30%)
    sf1_revenue_growth_pct: float | None = Field(
        None, description="YoY revenue growth as percentage (e.g. 29.0 for +29%)."
    )
    sf1_score: float = Field(ge=0, le=100, description="sf1 raw 0-100 score.")

    # Sub-factor 2 — Gross Margin Trend (weight 20%)
    sf2_gross_margin_trend_bps: float | None = Field(
        None, description="YoY gross margin change in basis points (positive = expanding)."
    )
    sf2_score: float = Field(ge=0, le=100, description="sf2 raw 0-100 score.")

    # Sub-factor 3 — EPS Beat Consistency 4Q (weight 20%; excluded when pre-profit)
    sf3_eps_beats: int | None = Field(
        None, description="Number of EPS beats in last 4Q (None when excluded)."
    )
    sf3_quarters_available: int = Field(ge=0, description="Quarters of EPS data available (max 4).")
    sf3_score: float | None = Field(
        None,
        ge=0,
        le=100,
        description="sf3 raw 0-100 score; None when excluded (pre-profitability).",
    )
    sf3_excluded: bool = Field(
        default=False, description="True when sf3 is excluded due to pre-profitability."
    )

    # Sub-factor 4 — Guidance Reliability 4Q (weight 15%)
    sf4_guidance_delivered: int | None = Field(
        None, description="Number of quarters guidance was delivered/met (0-4). None = DATA_GAP."
    )
    sf4_score: float = Field(
        ge=0,
        le=100,
        description="sf4 raw 0-100 score (~66.67 when DATA_GAP → 10 pts weighted at 15%).",
    )
    sf4_data_gap: bool = Field(
        default=False,
        description="True when Bloomberg guidance data is unavailable; sf4 defaults to 10.",
    )

    # Sub-factor 5 — Forward Visibility (weight 15%)
    sf5_forward_visibility_label: str = Field(
        description="Forward visibility label: SPECIFIC_RAISED | SPECIFIC_MAINTAINED | DIRECTIONAL | VAGUE_NONE | WITHDRAWN_REDUCED."
    )
    sf5_score: float = Field(ge=0, le=100, description="sf5 score (0/30/60/80/100).")

    # F2 composite
    f2_raw: float = Field(ge=0, le=100, description="Weighted composite F2 score (0-100 float).")
    f2_contribution: float = Field(
        description="f2_raw × 0.25 — F2's contribution to overall conviction score."
    )
    f2_score: int = Field(ge=0, le=100, description="f2_raw rounded to integer for display.")
    f2_grade: str = Field(description="Grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID.")

    # Flags
    pre_profit_status: bool = Field(default=False, description="True when net_income_ttm < 0.")
    pre_profit_reweighted: bool = Field(
        default=False, description="True when pre-profit re-weighting was applied (sf3 excluded)."
    )
    data_gap_applied: bool = Field(
        default=False, description="True when DATA_GAP default was applied to sf4."
    )
    guidance_concern: bool = Field(
        default=False, description="True when both sf4_score == 0 and sf5_score == 0."
    )
    exit_flag: bool = Field(
        default=False,
        description="True when revenue_growth < 0 and price is >20% above analyst target.",
    )
    limited_history: bool = Field(
        default=False, description="True when fewer than 4Q of EPS data were available."
    )
    ipo_limited_history: bool = Field(
        default=False, description="True when eps_quarters_available < 4 (IPO / young company)."
    )
    data_available: bool = Field(
        default=True, description="False when all data sources returned no data."
    )
    is_pre_profitability: bool = Field(
        default=False,
        description="Alias for pre_profit_status (for backward compat with framework_score_service).",
    )

    # Full breakdown dict for transparency
    breakdown: dict[str, Any] = Field(
        default_factory=dict, description="Detailed per-sub-factor breakdown."
    )
