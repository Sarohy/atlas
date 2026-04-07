"""Unit tests for the HealthResponse schema."""

from atlas.schemas.health import HealthResponse


def test_health_response_has_status_field() -> None:
    """HealthResponse must expose a 'status' string field."""
    fields = HealthResponse.model_fields
    assert "status" in fields
    assert fields["status"].annotation is str


def test_health_response_has_service_field() -> None:
    """HealthResponse must expose a 'service' string field."""
    fields = HealthResponse.model_fields
    assert "service" in fields
    assert fields["service"].annotation is str


def test_health_response_serializes_correctly() -> None:
    """An ok health response serialises to the expected dict."""
    response = HealthResponse(status="ok", service="atlas-backend")
    assert response.model_dump() == {"status": "ok", "service": "atlas-backend"}
