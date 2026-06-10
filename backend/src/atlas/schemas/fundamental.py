"""Pydantic schemas for the F5 Fundamental Quality endpoint.

F5 has five sub-indicators with internal weights (per Factor_Mapping_Guide):
  1. Insider Activity         — SEC Form 4 net activity last 90 days  (30%)
  2. Altman Z-Score           — Financial distress composite metric    (25%)
  3. Free Cash Flow           — FCF level and quarter-over-quarter trend (20%)
  4. Debt / Equity            — Balance-sheet leverage ratio            (15%)
  5. Institutional Ownership  — Current institutional ownership %       (10%)

F5 = (insider × 0.30) + (altman_z × 0.25) + (fcf × 0.20)
   + (debt_equity × 0.15) + (institutional × 0.10)

Caps and hard blocks (applied before entering main formula):
  Insider Selling Cap   C-suite sale >$1M in 90 days → F5 capped at 72
  CEO/CFO Mega Sale     CEO or CFO sale >$10M        → F5 capped at 65
  Altman Z Grey Zone    Z-score 1.8–2.0              → F5 capped at 75
  Altman Z Distress     Z-score <1.8                 → Hard block (f5_blocked=True)

Data sources:
  Insider Activity  — sec-api.io  (POST /insider-trading)
  Altman Z-Score    — Alpha Vantage BALANCE_SHEET + INCOME_STATEMENT + OVERVIEW
  Free Cash Flow    — Alpha Vantage CASH_FLOW
  Debt / Equity     — Alpha Vantage BALANCE_SHEET
  Institutional     — Alpha Vantage OVERVIEW (PercentInstitutionsOwnership)
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Grade constants
# ---------------------------------------------------------------------------


class F5Grade:
    """Named constants for F5 composite grade labels."""

    STRONG: Final[str] = "STRONG"
    GOOD: Final[str] = "GOOD"
    NEUTRAL: Final[str] = "NEUTRAL"
    WEAK: Final[str] = "WEAK"
    DISTRESSED: Final[str] = "DISTRESSED"


# ---------------------------------------------------------------------------
# Sub-indicator schemas
# ---------------------------------------------------------------------------


class InsiderActivityIndicator(BaseModel):
    """Net insider buying/selling from SEC Form 4 filings over the last 90 days.

    Scoring rule (0-100):
      Net buying (buys > 0, no sales)   → 100
      No activity                        →  70
      1 small sale (<$500K)              →  55
      Multiple sales (≥2 dispose events) →  30
      CEO/CFO sale >$10M                 →  20

    Cap overrides (applied to F5 total, not this score):
      C-suite officer sale >$1M  → F5 capped at 72
      CEO or CFO sale   >$10M   → F5 capped at 65
    """

    model_config = ConfigDict(from_attributes=True)

    net_buy_value: float | None = Field(
        None, description="Total USD value of insider open-market purchases (last 90 days)."
    )
    net_sell_value: float | None = Field(
        None, description="Total USD value of insider open-market sales (last 90 days)."
    )
    transaction_count: int = Field(default=0, description="Total Form 4 transactions found.")
    c_suite_sell_value: float | None = Field(
        None, description="Total officer (C-suite) disposal value in USD (last 90 days)."
    )
    ceo_cfo_sell_value: float | None = Field(
        None, description="CEO or CFO disposal value in USD. Triggers mega-sale cap at >$10M."
    )
    activity_label: str = Field(
        default="NO_ACTIVITY",
        description=(
            "NET_BUYING | NO_ACTIVITY | SMALL_SALE | MULTIPLE_SALES | CEO_MEGA_SALE | ROUTINE_DIVERSIFICATION"
        ),
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.30, description="Weight in F5 formula.")


class AltmanZScoreIndicator(BaseModel):
    """Altman Z-Score financial distress metric.

    Formula (public-company version):
      Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5
      X1 = Working Capital / Total Assets
      X2 = Retained Earnings / Total Assets
      X3 = TTM EBIT / Total Assets
      X4 = Market Cap / Total Liabilities
      X5 = TTM Revenue / Total Assets

    Scoring rule (0-100) and cap / block triggers:
      Z > 3.0     → 100  (safe zone)
      Z 2.5–3.0   →  85
      Z 2.0–2.5   →  70
      Z 1.8–2.0   →  55  → also caps F5 at 75 (grey zone)
      Z < 1.8     →   0  → hard block (f5_blocked = True, buy disabled)
      Unknown     →  70  (neutral — data unavailable)
    """

    model_config = ConfigDict(from_attributes=True)

    z_score: float | None = Field(
        None, description="Computed Altman Z-Score. Null when data insufficient."
    )
    x1_working_capital_ratio: float | None = Field(
        None, description="X1 = (Current Assets − Current Liabilities) / Total Assets."
    )
    x2_retained_earnings_ratio: float | None = Field(
        None, description="X2 = Retained Earnings / Total Assets."
    )
    x3_ebit_ratio: float | None = Field(
        None, description="X3 = TTM Operating Income / Total Assets."
    )
    x4_market_cap_to_liabilities: float | None = Field(
        None, description="X4 = Market Cap / Total Liabilities."
    )
    x5_revenue_to_assets: float | None = Field(
        None, description="X5 = TTM Revenue / Total Assets."
    )
    zone: str = Field(
        default="UNKNOWN",
        description="SAFE (Z>3) | GREY (1.8–2.0) | DISTRESSED (<1.8) | UNKNOWN",
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.25, description="Weight in F5 formula.")


class FreeCashFlowIndicator(BaseModel):
    """Free Cash Flow level and quarter-over-quarter trend.

    FCF = Operating Cash Flow − Capital Expenditures (quarterly).

    Scoring rule (0-100):
      FCF positive AND growing   → 100
      FCF positive AND flat      →  80
      FCF positive AND declining →  60
      FCF negative AND improving →  40
      FCF negative AND worsening →  20
      Unknown                    →  60  (neutral)
    """

    model_config = ConfigDict(from_attributes=True)

    fcf_current: float | None = Field(
        None, description="Trailing-twelve-month Free Cash Flow (USD) — sum of the last 4 quarters."
    )
    fcf_prior: float | None = Field(
        None,
        description="Preceding TTM Free Cash Flow (USD) — quarters 5-8, used for trend.",
    )
    fcf_trend: str = Field(
        default="UNKNOWN",
        description=(
            "POSITIVE_GROWING | POSITIVE_FLAT | POSITIVE_DECLINING"
            " | NEGATIVE_LARGE_IMPROVEMENT | NEGATIVE_IMPROVING | NEGATIVE_WORSENING | UNKNOWN"
        ),
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.15, description="Weight in F5 formula (reduced from 0.20 to accommodate gross_margin).")


class DebtEquityIndicator(BaseModel):
    """Debt-to-Equity ratio from the most recent balance sheet.

    D/E = Total Debt (short + long term) / Total Shareholder Equity.
    Falls back to Total Liabilities / Equity when debt line items unavailable.

    Scoring rule (0-100):
      D/E < 0.3  → 100
      D/E 0.3–0.6 →  85
      D/E 0.6–1.0 →  70
      D/E 1.0–2.0 →  50
      D/E > 2.0   →  25
      Unknown      →  65  (neutral)
    """

    model_config = ConfigDict(from_attributes=True)

    total_debt: float | None = Field(
        None, description="Total debt (short-term + long-term) in USD."
    )
    total_equity: float | None = Field(
        None, description="Total shareholder equity in USD."
    )
    ratio: float | None = Field(
        None, description="Debt / Equity ratio. Null when equity is zero or data missing."
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.15, description="Weight in F5 formula.")


class InstitutionalOwnershipIndicator(BaseModel):
    """Institutional ownership level from Alpha Vantage OVERVIEW.

    Note: Alpha Vantage provides current ownership % only; quarter-over-quarter
    change requires 13F data not available in this integration.  Current %
    is used as a proxy for institutional conviction:
      ≥ 70 %   → NET_BUYING   → 100
      50–70 %  → FLAT         →  80
      30–50 %  → FLAT         →  65
      10–30 %  → SMALL_SELLING →  45
      < 10 %   → LARGE_SELLING →  20
      Unknown  → FLAT          →  65
    """

    model_config = ConfigDict(from_attributes=True)

    ownership_pct: float | None = Field(
        None, description="Current institutional ownership as a fraction (0.0–1.0)."
    )
    change_label: str = Field(
        default="FLAT",
        description="NET_BUYING | FLAT | SMALL_SELLING | LARGE_SELLING",
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.10, description="Weight in F5 formula (reduced from 0.15 to accommodate gross_margin).")


class GrossMarginIndicator(BaseModel):
    """Gross margin sub-indicator (Fix 3 addition, weight 0.10).

    Gross margin = (Revenue − COGS) / Revenue, expressed as a fraction.
    Sourced from TTM income statement (Alpha Vantage INCOME_STATEMENT).

    Scoring rule (0-100):
      ≥ 70%   → 100
      50–70%  →  80
      30–50%  →  60
      10–30%  →  40
      < 10%  →  20  (includes negative margins)
      Unknown →  60  (neutral)
    """

    model_config = ConfigDict(from_attributes=True)

    gross_margin: float | None = Field(
        None, description="TTM gross margin as a fraction (0.0–1.0). Null when unavailable."
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.10, description="Weight in F5 formula.")


class FundamentalResponse(BaseModel):
    """Complete F5 Fundamental Quality analysis for a single ticker.

    F5 = (insider_activity.score  × 0.30)
       + (altman_z.score          × 0.25)
       + (free_cash_flow.score    × 0.15)
       + (debt_equity.score       × 0.10)
       + (gross_margin.score      × 0.10)
       + (institutional.score     × 0.10)

    Caps are applied to the composite total (not individual indicators):
      insider_cap  — set when C-suite sells above threshold
      altman_cap   — 75 when Z-score is in the grey zone (1.8–2.0)
      active_cap   — effective cap = min(insider_cap, altman_cap) if any set

    Hard block: f5_blocked = True when Z < 1.8 (no new capital regardless of score).
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    insider_activity: InsiderActivityIndicator
    altman_z: AltmanZScoreIndicator
    free_cash_flow: FreeCashFlowIndicator
    debt_equity: DebtEquityIndicator
    gross_margin: GrossMarginIndicator
    institutional_ownership: InstitutionalOwnershipIndicator

    # --- Cap and block fields ---
    insider_cap: int | None = Field(
        None,
        description=(
            "F5 cap from insider selling — 72 (officer >$1M) or 65 (CEO/CFO >$10M). "
            "Null = no insider selling cap triggered."
        ),
    )
    altman_cap: int | None = Field(
        None,
        description="F5 cap from Altman Z grey zone — 75. Null = not in grey zone.",
    )
    f5_blocked: bool = Field(
        default=False,
        description=(
            "True when Altman Z-Score < 1.8 (distress zone). "
            "New capital deployment is hard-blocked regardless of final score."
        ),
    )
    active_cap: int | None = Field(
        None,
        description="The effective cap applied — lowest of insider_cap and altman_cap.",
    )

    f5_score: int = Field(
        ge=0, le=100, description="Composite F5 Fundamental Quality score (0-100, after caps)."
    )
    f5_grade: str = Field(
        description="F5 grade: STRONG | GOOD | NEUTRAL | WEAK | DISTRESSED"
    )
    data_available: bool = Field(
        default=True,
        description="False when Alpha Vantage returned no data (rate-limited); scores are fallback-only.",
    )
