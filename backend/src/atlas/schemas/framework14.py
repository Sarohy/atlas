"""Pydantic schemas for Framework 14 — Position Sizing Rules.

ATLAS v7.3.4 spec (CLAUDE.md Framework #13).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SizingTier(StrEnum):
    """Position sizing tier per ATLAS v7.3.4 Framework #13."""

    CORE_ANCHOR = "CORE_ANCHOR"
    HIGH_CONVICTION_T2 = "HIGH_CONVICTION_T2"
    STANDARD_T2 = "STANDARD_T2"
    T3_SATELLITE = "T3_SATELLITE"
    CHINA_RISK = "CHINA_RISK"
    HIGH_BETA = "HIGH_BETA"


class ConcentrationStatus(StrEnum):
    """Concentration cap status for a single position."""

    NORMAL = "NORMAL"
    SOFT_CAP = "SOFT_CAP"
    HARD_REVIEW = "HARD_REVIEW"
    GRANDFATHERED = "GRANDFATHERED"


class ClusterStatus(StrEnum):
    """Concentration status for a correlation cluster."""

    NORMAL = "NORMAL"
    YELLOW_ZONE = "YELLOW_ZONE"
    RED_ZONE = "RED_ZONE"


class Framework14Result(BaseModel):
    """Full Framework 14 result for a single ticker."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # -- Position weight -------------------------------------------------

    position_weight_pct: float = Field(
        description="Current position weight as a percentage of NAV (e.g. 13.6)."
    )
    nav_dollars: float = Field(description="Total portfolio NAV in USD.")
    position_dollars: float = Field(description="Current position market value in USD.")

    # -- Sizing tier ------------------------------------------------------

    sizing_tier: SizingTier = Field(description="Which sizing tier this ticker belongs to.")
    target_weight_min: float = Field(
        description="Lower bound of target weight for this tier (fraction, e.g. 0.03)."
    )
    target_weight_max: float = Field(
        description="Upper bound of target weight for this tier (fraction, e.g. 0.05)."
    )

    # -- Concentration cap ------------------------------------------------

    concentration_status: ConcentrationStatus = Field(
        description="Overall concentration cap status."
    )
    cap_active: bool = Field(description="True when adds are blocked by the concentration cap.")
    soft_cap_breached: bool = Field(description="True when position weight >= 8% NAV soft cap.")
    hard_review_triggered: bool = Field(
        description="True when position weight >= 10% NAV hard review threshold."
    )
    grandfathered: bool = Field(
        description="True when position is grandfathered above the soft cap."
    )
    grandfathered_expires_at: float | None = Field(
        description="Weight threshold (fraction) at which grandfathered status expires."
    )
    grandfathered_expiry_near: bool = Field(
        description="True when current weight is within 2 pp of the expiry threshold."
    )
    score_display_cap: int | None = Field(
        description=(
            "Display-only score cap (85) when soft cap is breached. "
            "Does NOT trigger 3-AI consensus gate — display only."
        )
    )

    # -- Cluster ----------------------------------------------------------

    cluster: str = Field(description="Correlation cluster name for this ticker.")
    cluster_weight_pct: float = Field(description="Total cluster weight as a percentage of NAV.")
    cluster_status: ClusterStatus = Field(description="Cluster concentration zone status.")
    cluster_yellow_threshold: float = Field(
        description="Yellow zone threshold for this cluster (fraction)."
    )
    cluster_red_threshold: float = Field(
        description="Red zone threshold for this cluster (fraction)."
    )

    # -- Decision outputs -------------------------------------------------

    adds_permitted: bool = Field(description="True when new adds are permitted for this position.")
    trim_recommended: bool = Field(description="True when a trim review is recommended.")
    message: str = Field(description="Human-readable guidance for the current state.")


class ClusterSummaryResult(BaseModel):
    """Summary result for a single correlation cluster."""

    model_config = ConfigDict(from_attributes=True)

    cluster: str = Field(description="Cluster name.")
    cluster_weight_pct: float = Field(description="Total cluster weight as a percentage of NAV.")
    cluster_status: ClusterStatus = Field(description="Cluster concentration zone.")
    cluster_yellow_threshold: float = Field(description="Yellow zone threshold (fraction).")
    cluster_red_threshold: float = Field(description="Red zone threshold (fraction).")
    tickers: list[str] = Field(description="Tickers belonging to this cluster.")
    trim_recommended: bool = Field(description="True when cluster is in the red zone.")
