"""Pydantic schemas for watchlist items."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WatchlistItemCreate(BaseModel):
    """Payload to add a ticker to the watchlist."""

    ticker: str = Field(min_length=1, max_length=20)
    company_name: str = Field(min_length=1, max_length=200)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        """Force ticker symbols to upper-case on ingestion."""
        return v.strip().upper()

    @field_validator("company_name", mode="before")
    @classmethod
    def strip_company_name(cls, v: str) -> str:
        """Trim surrounding whitespace from company names."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("company_name must not be blank")
        return stripped


class WatchlistItemResponse(BaseModel):
    """API response shape for a watchlist item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    company_name: str

    # Market-data fields — None until the first /sync call.
    current_price: Decimal | None = None
    previous_close: Decimal | None = None
    day_change: Decimal | None = None
    day_change_pct: Decimal | None = None
    beta: Decimal | None = None
    synced_at: datetime | None = None

    created_at: datetime
    updated_at: datetime
