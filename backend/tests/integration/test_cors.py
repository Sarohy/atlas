"""Integration tests for backend CORS behavior."""

import os

from httpx import ASGITransport, AsyncClient

from atlas.main import create_app

_TEST_FRONTEND_ORIGIN = "https://frontend.example.com"


async def test_cors_preflight_allows_configured_frontend_origin() -> None:
    """Configured frontend origins should receive CORS allow headers on preflight."""
    previous_allowed_origins = os.environ.get("ALLOWED_ORIGINS")
    os.environ["ALLOWED_ORIGINS"] = f"http://localhost:3000,{_TEST_FRONTEND_ORIGIN}"

    try:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.options(
                "/api/v1/auth/sign-in",
                headers={
                    "Origin": _TEST_FRONTEND_ORIGIN,
                    "Access-Control-Request-Method": "POST",
                },
            )
    finally:
        if previous_allowed_origins is None:
            os.environ.pop("ALLOWED_ORIGINS", None)
        else:
            os.environ["ALLOWED_ORIGINS"] = previous_allowed_origins

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _TEST_FRONTEND_ORIGIN
