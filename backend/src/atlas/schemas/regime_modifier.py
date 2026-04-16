"""Pydantic schemas for the Regime Modifier endpoint."""

from pydantic import BaseModel, Field


class RegimeModifierResponse(BaseModel):
    """Response from the regime modifier endpoint.

    Combines the base Framework Score with a market-regime adjustment driven
    by Brent crude price, VIX level, and an active-war flag.
    """

    ticker: str
    active_war: bool

    # ── Market conditions (None when Polygon.io data unavailable) ─────────
    brent_price: float | None = Field(
        description="Brent crude price in USD per barrel (most recent daily close).",
    )
    vix_value: float | None = Field(
        description="CBOE VIX index level (most recent daily close).",
    )

    # ── Framework score ───────────────────────────────────────────────────
    base_score: int = Field(
        description="Original framework score before regime adjustment (0-100).",
    )
    adjusted_score: int = Field(
        description="Score after applying the triggered regime rule (0-100).",
    )

    # ── Regime determination ──────────────────────────────────────────────
    rule_triggered: int | None = Field(
        description="Which regime rule fired (1 = Crisis, 2 = Caution, 3 = Clear), "
        "or None when market conditions are normal.",
    )
    rule: str = Field(
        description="Human-readable name of the triggered rule: "
        "CRISIS | CAUTION | CLEAR | NORMAL.",
    )
    modifier: int = Field(
        description="Score delta applied by the triggered rule: "
        "-10 (Crisis), -5 (Caution), +5 (Clear), 0 (Normal).",
    )

    # ── Cash guidance — fractions (0.35 = 35 %) ──────────────────────────
    min_cash_pct: float = Field(
        description="Minimum required cash fraction of the ticker's position value.",
    )
    max_cash_pct: float = Field(
        description="Maximum recommended cash fraction of the ticker's position value.",
    )

    # ── Cash guidance — USD amounts ───────────────────────────────────────
    # None when the ticker is not present in the portfolio DB.
    min_cash_usd: float | None = Field(
        description="Minimum cash in USD (min_cash_pct x position_value). "
        "None when ticker is not in the portfolio.",
    )
    max_cash_usd: float | None = Field(
        description="Maximum cash in USD (max_cash_pct x position_value). "
        "None when ticker is not in the portfolio.",
    )

    # ── Human-readable guidance ───────────────────────────────────────────
    output_text: str = Field(
        description="Regime cash-management instruction (multi-line for crisis rules).",
    )
