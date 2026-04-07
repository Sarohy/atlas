"""Pydantic schemas for health check responses."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Schema returned by GET /api/v1/health."""

    status: str
    service: str
