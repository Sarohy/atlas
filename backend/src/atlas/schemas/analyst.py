"""Pydantic schemas for the F3 Analyst Conviction endpoint.

F3 has four sub-indicators with internal weights (per Factor_Mapping_Guide):
  1. Consensus Rating     — buy % of analyst coverage            (35%)
  2. Analyst Count        — number of unique covering analysts   (10%)
  3. PT vs Current Price  — % upside from current to consensus PT (30%)
  4. PT Revision Direction — PT raises / lowers in last 30 days  (25%)

Each indicator is scored 0–100. The F3 score is:
  F3 = (consensus × 0.35) + (count × 0.10) + (pt_upside × 0.30) + (pt_revision × 0.25)
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# F3 grade literals
# ---------------------------------------------------------------------------


class F3Grade:
    """Named constants for the five F3 analyst-conviction grades."""

    STRONG_BUY: Final[str] = "STRONG BUY"
    BUY: Final[str] = "BUY"
    NEUTRAL: Final[str] = "NEUTRAL"
    WEAK: Final[str] = "WEAK"
    AVOID: Final[str] = "AVOID"


# ---------------------------------------------------------------------------
# Sub-indicator schemas
# ---------------------------------------------------------------------------


class ConsensusRatingIndicator(BaseModel):
    """Analyst buy/hold/sell breakdown and the resulting consensus label.

    Scoring rule (0-100):
      buy_pct > 80% → 100 (Strong Buy) | 60-80% → 80 (Buy)
      40-60% → 55 (Hold) | < 40% → 20 (Sell)
    Weight in F3: 35%
    """

    model_config = ConfigDict(from_attributes=True)

    strong_buy_count: int = Field(ge=0, description="Analysts with a Strong Buy rating.")
    buy_count: int = Field(ge=0, description="Analysts with a Buy rating.")
    hold_count: int = Field(ge=0, description="Analysts with a Hold / Neutral rating.")
    sell_count: int = Field(ge=0, description="Analysts with a Sell rating.")
    strong_sell_count: int = Field(ge=0, description="Analysts with a Strong Sell rating.")
    total_analysts: int = Field(ge=0, description="Total analyst count.")
    buy_pct: float | None = Field(
        None,
        description="(Strong Buy + Buy) as a percentage of total (0-100). Null when no analysts.",
    )
    label: str = Field(
        description="Consensus label: STRONG BUY | BUY | HOLD | SELL | NO DATA"
    )
    score: int | None = Field(default=None, ge=0, le=100, description="Raw indicator score (0-100). Null when no coverage data available.")
    weight: float = Field(default=0.35, description="Weight in F3 formula.")


class AnalystCoverageIndicator(BaseModel):
    """Depth of analyst coverage.

    Scoring rule (0-100):
      > 20 analysts → 100 | 10-20 → 85 | 5-10 → 65 | < 5 → 40 (hard cap)
    Note: names with fewer than 5 analysts score max 40 per guide.
    Weight in F3: 10%
    """

    model_config = ConfigDict(from_attributes=True)

    num_analysts: int = Field(ge=0, description="Total number of analysts covering the stock.")
    score: int | None = Field(default=None, ge=0, le=100, description="Raw indicator score (0-100). Null when no coverage data available.")
    weight: float = Field(default=0.10, description="Weight in F3 formula.")


class PtUpsideIndicator(BaseModel):
    """Price target upside vs the current market price.

    Scoring rule (0-100):
      PT > 30% above current → 100 | 15-30% → 85 | 5-15% → 70
      0-5% → 55 | PT below current → 20
    Weight in F3: 30%
    """

    model_config = ConfigDict(from_attributes=True)

    current_price: float | None = Field(
        None, description="Latest closing price (USD). Null when unavailable."
    )
    consensus_pt: float | None = Field(
        None, description="Consensus 12-month price target (USD). Null when unavailable."
    )
    upside_pct: float | None = Field(
        None,
        description=(
            "Percentage upside from current price to consensus PT. "
            "Negative indicates downside. Null when price data is missing."
        ),
    )
    pt_ratio: float | None = Field(
        None,
        description=(
            "current_price / consensus_PT. >1.40 triggers the F3 cap at 55. "
            "Null when price or PT data is missing."
        ),
    )
    score: int | None = Field(default=None, ge=0, le=100, description="Raw indicator score (0-100). Null when price or PT data is unavailable.")
    weight: float = Field(default=0.30, description="Weight in F3 formula.")


class PtRevisionIndicator(BaseModel):
    """Direction of analyst PT revisions over the last 30 days.

    Uses Benzinga calendar/ratings action_pt field:
      'Raises' / 'Announces' → upgrade | 'Lowers' → downgrade | 'Maintains' → no change

    Scoring rule (0-100):
      ≥ 2 raises in 30d → 100 | 1 raise → 80 | No change → 60 | Any lower → 20
    Weight in F3: 25%
    """

    model_config = ConfigDict(from_attributes=True)

    raises_30d: int = Field(ge=0, description="PT raises (Raises/Announces) in last 30 days.")
    lowers_30d: int = Field(ge=0, description="PT cuts (Lowers) in last 30 days.")
    revision_label: str = Field(
        description="Summary label: MULTIPLE RAISES | 1 RAISE | NO CHANGE | LOWERED"
    )
    score: int | None = Field(default=None, ge=0, le=100, description="Raw indicator score (0-100). Null when Benzinga ratings fetch failed.")
    weight: float = Field(default=0.25, description="Weight in F3 formula.")


# ---------------------------------------------------------------------------
# Top-level response schema
# ---------------------------------------------------------------------------


class AnalystResponse(BaseModel):
    """Complete F3 Analyst Conviction analysis for a single ticker.

    F3 = (consensus_rating.score × 0.35)
       + (analyst_coverage.score × 0.10)
       + (pt_upside.score × 0.30)
       + (pt_revision.score × 0.25)
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    consensus_rating: ConsensusRatingIndicator
    analyst_coverage: AnalystCoverageIndicator
    pt_upside: PtUpsideIndicator
    pt_revision: PtRevisionIndicator
    f3_score: int | None = Field(
        default=None, ge=0, le=100, description="Composite F3 Analyst Conviction score (0-100). Null when all sub-factors have no data."
    )
    f3_grade: str = Field(description="F3 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID")
