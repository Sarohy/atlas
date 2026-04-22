"""Pydantic schemas for Framework 13 — Beta-Adjusted Portfolio Management.

ATLAS v7.3.4 spec (CLAUDE.md Framework #13).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BetaSource(StrEnum):
    """Source of the beta value used for this position."""

    CONFIRMED = "CONFIRMED"
    CALCULATED = "CALCULATED"  # Computed from Polygon.io returns; cached 7 days
    DEFAULT = "DEFAULT"


class Framework13Result(BaseModel):
    """Full Framework 13 evaluation result for a single ticker."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    beta: float = Field(description="Confirmed or default beta value.")
    beta_source: BetaSource = Field(description="Whether beta is confirmed or default.")

    # -- Position metrics --------------------------------------------------

    position_weight_pct: float = Field(
        description="Current position weight as a percentage of NAV (e.g. 0.9)."
    )
    position_dollars: float = Field(description="Position market value in USD.")
    effective_exposure_pct: float = Field(
        description="Position weight * beta, expressed as a percentage (e.g. 2.97)."
    )
    effective_exposure_note: str = Field(
        description="Human-readable multiplication: 'X% position * beta Y = Z% effective'."
    )

    # -- Beta cap ----------------------------------------------------------

    beta_cap_active: bool = Field(
        description="True when position_weight >= beta-adjusted cap limit."
    )
    beta_cap_limit_pct: float | None = Field(
        description="Cap threshold in percentage points (e.g. 1.0 for 1.0% NAV)."
    )
    beta_cap_reason: str | None = Field(
        description="Human-readable reason when beta_cap_active is True."
    )

    # -- Sizing tier -------------------------------------------------------

    sizing_tier: str = Field(
        description=(
            "Beta-based tier: AAOI_TYPE_HIGH_BETA | VERY_HIGH_BETA | "
            "HIGH_BETA | MODERATE_BETA | LOW_BETA."
        )
    )
    max_weight_pct: float = Field(
        description="Maximum allowed weight for this tier (percentage, e.g. 1.0)."
    )

    # -- Decision outputs --------------------------------------------------

    adds_permitted: bool = Field(description="True when new adds are permitted.")
    warning_level: str = Field(description="NONE | AMBER | RED | CRITICAL.")
    warning_message: str | None = Field(description="Human-readable warning when applicable.")

    # -- Flags -------------------------------------------------------------

    beta_source_flag: bool = Field(
        description="True when beta_source is DEFAULT (unconfirmed beta)."
    )


class PortfolioPositionBeta(BaseModel):
    """Per-position beta contribution for the portfolio beta result."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol.")
    weight: float = Field(description="Position weight as fraction of NAV.")
    beta: float = Field(description="Beta value used.")
    contribution: float = Field(description="weight * beta contribution to portfolio beta.")
    source: BetaSource = Field(description="Beta source (CONFIRMED or DEFAULT).")


class PortfolioBetaResult(BaseModel):
    """Portfolio-level beta result including effective beta calculation."""

    model_config = ConfigDict(from_attributes=True)

    weighted_avg_beta: float = Field(
        description="Sum of (position_weight * beta) across all held positions."
    )
    effective_beta: float = Field(description="weighted_avg_beta * (1 - cash_percentage).")
    cash_percentage: float = Field(description="Cash as a fraction of NAV (e.g. 0.20 for 20%).")
    target_beta: float = Field(description="Target portfolio effective beta (1.75 per ATLAS spec).")
    beta_status: str = Field(description="NORMAL | ELEVATED | CRITICAL.")
    warning_level: str = Field(description="NONE | RED | CRITICAL.")
    warning_message: str | None = Field(
        description="Human-readable warning message when beta is elevated."
    )
    position_betas: list[PortfolioPositionBeta] = Field(description="Per-position beta details.")
