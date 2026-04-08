"""Pydantic schemas for portfolio tickers and Polygon ticker search."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TickerSearchResult(BaseModel):
    """One result from the Polygon.io ticker-search endpoint."""

    ticker: str
    name: str
    market: str
    type: str


class TickerCreate(BaseModel):
    """Payload to create a new portfolio ticker."""

    ticker: str = Field(min_length=1, max_length=20)
    company_name: str = Field(min_length=1, max_length=200)
    # Shares must be strictly positive; 4 decimal places stored in DB.
    shares: Decimal = Field(gt=Decimal("0"))
    # Optional cluster assignment at creation time.
    cluster_id: int | None = Field(None, description="ID of the cluster to assign to.")

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


class TickerUpdate(BaseModel):
    """Payload to update the share count for an existing ticker."""

    shares: Decimal = Field(gt=Decimal("0"))


class TickerResponse(BaseModel):
    """API response shape for a portfolio ticker."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    company_name: str
    shares: Decimal

    # Optional cluster assignment.
    cluster_id: int | None = None

    # Market-data fields — None until the first /sync call.
    current_price: Decimal | None = None
    previous_close: Decimal | None = None
    day_change: Decimal | None = None
    day_change_pct: Decimal | None = None
    position_value: Decimal | None = None
    # Rolling 1-year beta vs SPY — None until first sync.
    beta: Decimal | None = None
    synced_at: datetime | None = None

    created_at: datetime
    updated_at: datetime
