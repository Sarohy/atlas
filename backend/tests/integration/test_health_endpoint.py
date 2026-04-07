"""Integration tests for the GET /api/v1/health endpoint."""

from httpx import AsyncClient


async def test_health_endpoint_returns_ok_status(client: AsyncClient) -> None:
    """GET /api/v1/health returns HTTP 200 with status ok."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


async def test_health_endpoint_returns_expected_json(client: AsyncClient) -> None:
    """GET /api/v1/health returns the canonical service health payload."""
    response = await client.get("/api/v1/health")
    assert response.json() == {"status": "ok", "service": "atlas-backend"}
