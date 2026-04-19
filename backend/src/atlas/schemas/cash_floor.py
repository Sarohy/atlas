"""Pydantic schemas for the Framework 5 Cash Floor endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CashFloorResponse(BaseModel):
    """Framework 5 cash floor guidance for a single ticker.

    Derives a cash-reserve requirement from the active Framework 2 (Regime
    Modifier) rule.  The floor is the minimum cash the investor must keep
    relative to the ticker's current portfolio position value.
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # ── Regime context ────────────────────────────────────────────────────
    rule_triggered: int | None = Field(
        default=None,
        description="Framework 2 rule that fired: 1=CRISIS, 2=CAUTION, 3=CLEAR, None=NORMAL.",
    )
    brent_price: float | None = Field(
        default=None,
        description="Brent crude price in USD per barrel at time of evaluation.",
    )
    vix_value: float | None = Field(
        default=None,
        description="CBOE VIX index level at time of evaluation.",
    )

    # ── Cash floor output ─────────────────────────────────────────────────
    condition: str = Field(
        description="Regime condition: CRISIS | CAUTION | CLEAR | FULLY_DEPLOYED.",
    )
    rationale: str = Field(
        description="Human-readable rationale for the floor requirement.",
    )

    # Percentages expressed as fractions (0.35 = 35 %).
    floor_pct_min: float = Field(
        description="Minimum cash floor as a fraction of position value.",
    )
    floor_pct_max: float = Field(
        description="Maximum cash floor as a fraction of position value.",
    )

    # USD amounts — None when the ticker is not in the portfolio database.
    position_value_usd: float | None = Field(
        default=None,
        description="Current portfolio position value in USD (shares × price).",
    )
    floor_usd_min: float | None = Field(
        default=None,
        description="Minimum cash to hold in USD (floor_pct_min × position_value_usd). "
        "None when ticker is not in the portfolio.",
    )
    floor_usd_max: float | None = Field(
        default=None,
        description="Maximum cash to hold in USD (floor_pct_max × position_value_usd). "
        "None when ticker is not in the portfolio.",
    )
