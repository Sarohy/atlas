"""Pydantic schemas for the ATLAS Overbought / Extension Overlay endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExtensionOverlayResponse(BaseModel):
    """Per-name overbought / extension overlay result.

    Combines technical extension metrics into a 0-N Extension Risk Score, a
    Green/Yellow/Red/Extreme-Red flag, and (when an ATLAS conviction score is
    supplied) an action recommendation that pairs quality with entry timing.
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Upper-cased ticker symbol.")

    # --- Raw metrics (null when insufficient data) ---
    rsi_14: float | None = Field(None, description="14-day Wilder RSI.")
    rsi_7: float | None = Field(None, description="7-day Wilder RSI (faster heat check).")
    move_14d_pct: float | None = Field(None, description="14-session price move, percent.")
    move_21d_pct: float | None = Field(None, description="21-session price move, percent.")
    pct_above_20dma: float | None = Field(None, description="Distance above 20-day MA, percent.")
    pct_above_50dma: float | None = Field(None, description="Distance above 50-day MA, percent.")
    pct_above_200dma: float | None = Field(
        None, description="Distance above the 200-day MA, percent."
    )
    week_52_position_pct: float | None = Field(
        None, description="Position within the trailing 52-week range, 0-100."
    )
    gap_today_pct: float | None = Field(
        None, description="Today's opening gap vs prior close, percent."
    )
    vwap: float | None = Field(
        None,
        description="Latest session volume-weighted average price (Polygon daily `vw`). "
        "This is the DAILY VWAP, not the intraday running VWAP.",
    )
    pct_vs_vwap: float | None = Field(
        None, description="Distance of the latest close above/below the daily VWAP, percent."
    )
    iv_rank: float | None = Field(
        None,
        description="IV rank on a 0-100 scale (Unusual Whales). Null when the UW key is "
        "unset or UW returns no data (DATA_GAP).",
    )

    # --- Overlay outputs ---
    extension_risk_score: int = Field(
        ge=0, description="Summed Extension Risk Score from the points table (0-N)."
    )
    extension_flag: str = Field(description="GREEN | YELLOW | RED | EXTREME_RED.")
    atlas_score: int | None = Field(
        None, description="ATLAS conviction score used for the action matrix, if supplied."
    )
    action: str | None = Field(
        None,
        description="ADD | BUY_ON_PULLBACK | HOLD_TRIM | TRIM_HEDGE | AVOID. "
        "Null when no atlas_score was supplied.",
    )
    action_detail: str | None = Field(
        None, description="Human-readable rationale for the recommended action."
    )

    # --- Diagnostics ---
    data_gaps: list[str] = Field(
        default_factory=list,
        description="Inputs that could not be computed (e.g. IV_RANK, insufficient bars).",
    )
