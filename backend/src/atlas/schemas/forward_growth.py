"""Pydantic schemas for the Forward Growth Score (FGS) endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FgsSubFactor(BaseModel):
    """A single FGS sub-factor score with its provenance."""

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(ge=0, le=100, description="Sub-factor score (0-100).")
    source: str = Field(
        description="Data source: alpha_vantage | curated | override | DATA_GAP.",
    )


class RevenueAccelerationSubFactor(FgsSubFactor):
    """G1 — revenue acceleration detail."""

    yoy_pct: float | None = Field(None, description="Most recent year-over-year revenue growth, %.")
    accelerating: bool | None = Field(
        None, description="True when YoY growth is speeding up vs the prior quarter's YoY."
    )


class TamBottleneckSubFactor(FgsSubFactor):
    """G5 — TAM / bottleneck status detail."""

    wave: str = Field(description="Bottleneck wave label (Section 8 roadmap) or UNCLASSIFIED.")
    status: str = Field(description="Wave status: ACTIVE | FORMING | EARLY | PRICED_IN | ...")


class ForwardGrowthResponse(BaseModel):
    """Forward Growth Score (FGS) — a parallel axis to the ATLAS score.

    FGS measures forward growth potential, never blended into the raw ATLAS
    number. The ``bucket`` / ``action`` come from the F5 x FGS x F4 matrix and
    are populated only when the caller supplies f5_score (and ideally f4_score).
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Upper-cased ticker symbol.")

    fgs_score: int = Field(ge=0, le=100, description="Composite Forward Growth Score (0-100).")
    fgs_grade: str = Field(description="ELITE | HIGH | MODERATE | LOW.")
    confidence_pct: int = Field(
        ge=0, le=100, description="Share of the 5 sub-factors backed by real data (not DATA_GAP)."
    )

    # --- Sub-factors (each 20%) ---
    revenue_acceleration: RevenueAccelerationSubFactor
    backlog_bookings: FgsSubFactor
    customer_quality: FgsSubFactor
    product_ramp: FgsSubFactor
    tam_bottleneck: TamBottleneckSubFactor

    # --- Action matrix (populated when f5_score supplied) ---
    f5_score: int | None = Field(None, description="F5 survivability score used for the matrix.")
    f4_score: int | None = Field(None, description="F4 options-flow score used for the matrix.")
    atlas_score: int | None = Field(None, description="ATLAS conviction score, for context.")
    bucket: str | None = Field(
        None,
        description="CORE_COMPOUNDER | QUALITY_HOLD | GROWTH_TACTICAL | STORY_RISK | AVOID.",
    )
    action: str | None = Field(None, description="Plain-English action from the matrix.")

    data_gaps: list[str] = Field(
        default_factory=list,
        description="Sub-factors not yet instrumented (e.g. BACKLOG_BOOKINGS, PRODUCT_RAMP).",
    )
