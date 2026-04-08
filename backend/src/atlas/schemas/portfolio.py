"""Pydantic schemas for portfolio summary and cash management."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CashAdjustRequest(BaseModel):
    """Payload to add or subtract from the portfolio cash balance.

    Positive delta deposits cash; negative delta withdraws.
    The resulting balance is clamped to zero — it cannot go negative.
    """

    delta: Decimal = Field(
        description="Amount to add (positive) or subtract (negative) from cash balance.",
    )


class CashUpdateRequest(BaseModel):
    """Payload to update the portfolio cash balance and floor percentage."""

    cash_balance: Decimal = Field(
        ge=Decimal("0"),
        description="Total cash held outside positions (USD).",
    )
    # Default to 10 % of NAV; must be in the range [0, 1].
    cash_floor_pct: Decimal = Field(
        default=Decimal("0.10"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Cash floor as a fraction of total NAV (0.10 = 10 %).",
    )


class CashResponse(BaseModel):
    """Current cash settings read back from the database."""

    model_config = ConfigDict(from_attributes=True)

    cash_balance: Decimal
    cash_floor_pct: Decimal


class PortfolioSummaryResponse(BaseModel):
    """Computed portfolio summary — all monetary values in USD."""

    # ── NAV breakdown ────────────────────────────────────────────────────────
    # Total net asset value = invested_value + cash_balance.
    total_nav: Decimal
    # Sum of all position market values (shares × current_price).
    invested_value: Decimal
    # Fraction of NAV that is invested (0–100).
    invested_pct: Decimal

    # ── Cash breakdown ───────────────────────────────────────────────────────
    cash_balance: Decimal
    # Fraction of NAV held in cash (0–100).
    cash_pct: Decimal
    # Hard floor: total_nav × cash_floor_pct (stored as fraction).
    cash_floor: Decimal
    # Floor expressed as percentage of NAV (0–100).
    cash_floor_pct: Decimal
    # Cash available above the floor; never negative.
    deployable: Decimal

    # ── Performance ──────────────────────────────────────────────────────────
    # Sum of dollar day-change across all positions; None until first sync.
    day_change: Decimal | None

    # ── Risk ─────────────────────────────────────────────────────────────────
    # Weighted-average beta including cash (cash beta = 0).
    beta_total: Decimal | None
    # Weighted-average beta of the invested portion only.
    beta_invested: Decimal | None
