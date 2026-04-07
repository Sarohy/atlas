"""Integration tests for the POST /api/v1/auth/sign-in endpoint."""

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from atlas.api.deps import get_auth_service
from atlas.main import create_app


class FakeAuthService:
    """Minimal auth service stub for route-level tests."""

    def __init__(self, authenticated_user: SimpleNamespace | None) -> None:
        self.authenticated_user = authenticated_user

    async def authenticate(self, email: str, password: str) -> SimpleNamespace | None:
        """Return the configured user only for the expected seed credentials."""
        if email == "admin@atlas.com" and password == "admin@123":
            return self.authenticated_user
        return None


async def test_sign_in_returns_authenticated_user_payload() -> None:
    """POST /api/v1/auth/sign-in returns the signed-in admin user."""
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        authenticated_user=SimpleNamespace(email="admin@atlas.com")
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/sign-in",
            json={"email": "admin@atlas.com", "password": "admin@123"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "email": "admin@atlas.com",
        "message": "Sign in successful.",
    }


async def test_sign_in_rejects_invalid_credentials() -> None:
    """POST /api/v1/auth/sign-in returns HTTP 401 for invalid credentials."""
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        authenticated_user=SimpleNamespace(email="admin@atlas.com")
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/sign-in",
            json={"email": "admin@atlas.com", "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}
