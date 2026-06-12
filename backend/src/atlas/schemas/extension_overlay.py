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
    ath: float | None = Field(
        None,
        description="All-time high (max split-adjusted daily high over available history).",
    )
    ath_date: str | None = Field(None, description="ISO date the all-time high was set.")
    pct_from_ath: float | None = Field(
        None, description="Distance of the latest close from the ATH, percent (negative = below)."
    )
    iv_rank: float | None = Field(
        None,
        description="IV rank on a 0-100 scale (Unusual Whales). Null when the UW key is "
        "unset or UW returns no data (DATA_GAP).",
    )

    # --- Deterministic technical sell / exhaustion signals ---
    td_setup: int | None = Field(
        None, description="DeMark TD setup count (1-9); null when no active setup."
    )
    td_setup_direction: str | None = Field(
        None, description="TD setup direction: SELL | BUY | null."
    )
    td_countdown: int | None = Field(
        None, description="DeMark TD sell countdown progress (1-13); null when not counting."
    )
    td_signal: str | None = Field(
        None,
        description="SELL_SETUP_9 | SELL_COUNTDOWN_13 | BUY_SETUP_9 | null (headline TD signal).",
    )
    rsi_bearish_divergence: bool = Field(
        default=False, description="Price higher-high while RSI makes a lower-high."
    )
    macd_bearish_cross: bool = Field(
        default=False, description="Fresh MACD line cross below its signal line."
    )

    # --- Rule-based Elliott Wave + Gann (contextual; NOT in the risk score) ---
    elliott_wave: str | None = Field(
        None, description="Current Elliott impulse wave (count of completed legs, 1-5)."
    )
    elliott_direction: str | None = Field(None, description="Impulse direction: UP | DOWN | null.")
    elliott_signal: str | None = Field(
        None,
        description="IMPULSE_TOP_SELL | IMPULSE_BOTTOM_BUY | null (rule-valid completed impulse).",
    )
    elliott_confidence: int | None = Field(
        None, description="Fibonacci-guideline adherence of the impulse (0-100)."
    )
    gann_signal: str | None = Field(
        None, description="BELOW_1X1_BEARISH | AT_GANN_RESISTANCE | TIME_TURN_DUE | null."
    )
    gann_below_1x1: bool = Field(
        default=False, description="Price below the 1x1 support angle from the last swing low."
    )
    gann_time_cycle_due: bool = Field(
        default=False, description="Near a 90/144/180/360-bar Gann time count from the last pivot."
    )
    gann_nearest_support: float | None = Field(
        None, description="Nearest Square-of-9 support level below price."
    )
    gann_nearest_resistance: float | None = Field(
        None, description="Nearest Square-of-9 resistance level above price."
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
