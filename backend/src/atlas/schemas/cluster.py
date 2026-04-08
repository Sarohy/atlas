"""Pydantic schemas for position clusters."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.schemas.ticker import TickerResponse


class ClusterCreate(BaseModel):
    """Payload to create a new cluster."""

    name: str = Field(min_length=1, max_length=100)
    # Hex colour string — exactly 7 chars, e.g. "#4a90d9".
    color: str = Field(
        min_length=7,
        max_length=7,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex colour, e.g. '#4a90d9'.",
    )


class ClusterUpdate(BaseModel):
    """Payload to update a cluster (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(
        None,
        min_length=7,
        max_length=7,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )


class ClusterResponse(BaseModel):
    """API response for a cluster, including its assigned tickers."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    tickers: list[TickerResponse] = []
    created_at: datetime
    updated_at: datetime
