"""Pydantic schemas for the F3 Analyst Conviction endpoint."""

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
    """Analyst buy/hold/sell breakdown and the resulting consensus label."""

    model_config = ConfigDict(from_attributes=True)

    buy_count: int = Field(ge=0, description="Number of analysts with a Buy or Strong Buy rating.")
    hold_count: int = Field(ge=0, description="Number of analysts with a Hold / Neutral rating.")
    sell_count: int = Field(
        ge=0, description="Number of analysts with an Underperform or Sell rating."
    )
    total_analysts: int = Field(ge=0, description="Total analyst count.")
    buy_pct: float | None = Field(
        None,
        description="Buy ratings as a percentage of total (0-100). Null when no analysts.",
    )
    label: str = Field(
        description=(
            "Consensus label derived from buy_pct: "
            "STRONG BUY | BUY | HOLD | UNDERPERFORM | SELL | NO DATA"
        )
    )
    score: int = Field(ge=0, le=20, description="F3 score contribution (0-20).")
    max_score: int = Field(default=20)


class PtUpsideIndicator(BaseModel):
    """Price target upside vs the current market price."""

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
    score: int = Field(ge=0, le=20, description="F3 score contribution (0-20).")
    max_score: int = Field(default=20)


class PtDirectionIndicator(BaseModel):
    """Direction of the consensus price target revision."""

    model_config = ConfigDict(from_attributes=True)

    current_consensus_pt: float | None = Field(
        None, description="Current consensus 12-month price target (USD)."
    )
    prior_consensus_pt: float | None = Field(
        None,
        description="Consensus price target from approximately 3 months ago (USD).",
    )
    direction_pct: float | None = Field(
        None,
        description=(
            "Percentage change in consensus PT from prior to current. "
            "Positive = PT being raised; negative = PT being cut."
        ),
    )
    score: int = Field(ge=0, le=20, description="F3 score contribution (0-20).")
    max_score: int = Field(default=20)


class AnalystCoverageIndicator(BaseModel):
    """Depth of analyst coverage — more analysts means a more reliable consensus."""

    model_config = ConfigDict(from_attributes=True)

    num_analysts: int = Field(ge=0, description="Total number of analysts covering the stock.")
    score: int = Field(ge=0, le=20, description="F3 score contribution (0-20).")
    max_score: int = Field(default=20)


class RecentUpgradesIndicator(BaseModel):
    """Net upgrade/downgrade balance over the most recent 90-day window."""

    model_config = ConfigDict(from_attributes=True)

    upgrades: int = Field(ge=0, description="Number of analyst upgrades in last 90 days.")
    downgrades: int = Field(ge=0, description="Number of analyst downgrades in last 90 days.")
    net_upgrades: int = Field(description="upgrades - downgrades. Positive = net bullish action.")
    score: int = Field(ge=0, le=20, description="F3 score contribution (0-20).")
    max_score: int = Field(default=20)


# ---------------------------------------------------------------------------
# Top-level response schema
# ---------------------------------------------------------------------------


class AnalystResponse(BaseModel):
    """Complete F3 Analyst Conviction analysis for a single ticker."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    consensus_rating: ConsensusRatingIndicator
    pt_upside: PtUpsideIndicator
    pt_direction: PtDirectionIndicator
    analyst_coverage: AnalystCoverageIndicator
    recent_upgrades: RecentUpgradesIndicator
    f3_score: int = Field(
        ge=0, le=100, description="Composite F3 Analyst Conviction score (0-100)."
    )
    f3_grade: str = Field(description="F3 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID")
