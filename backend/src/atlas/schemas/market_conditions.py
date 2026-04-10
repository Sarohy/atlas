"""Pydantic schema for the Market Conditions endpoint."""

from pydantic import BaseModel, Field


class MarketConditionsResponse(BaseModel):
    """Live market-regime inputs: Brent crude and VIX.

    Both values are None when the upstream data source is unavailable.
    ``brent_prev_price`` is the previous daily close, required by the frontend
    to evaluate the two-consecutive-closes test for Rule 3.
    """

    brent_price: float | None = Field(
        description="Most recent Brent crude daily close (USD per barrel).",
    )
    brent_prev_price: float | None = Field(
        description="Previous Brent crude daily close (USD per barrel). "
        "Used to check two consecutive closes below $95 for Rule 3.",
    )
    vix_value: float | None = Field(
        description="Latest CBOE VIX index level.",
    )
