"""Unit tests for the authentication service."""

from atlas.core.security import hash_password
from atlas.services.auth import AuthService


class FakeScalarResult:
    """Simple stand-in for a scalar SQLAlchemy result."""

    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        """Return the configured value."""
        return self._value


class FakeSession:
    """Async session double for auth service tests."""

    def __init__(self, user: object | None) -> None:
        self.user = user

    async def execute(self, _statement: object) -> FakeScalarResult:
        """Return the configured user lookup result."""
        return FakeScalarResult(self.user)


class FakeUser:
    """Simple user object for auth tests."""

    def __init__(self, *, email: str, password_hash: str, is_active: bool) -> None:
        self.email = email
        self.password_hash = password_hash
        self.is_active = is_active


async def test_authenticate_returns_user_for_valid_credentials() -> None:
    """authenticate returns the user when the password matches."""
    user = FakeUser(
        email="admin@atlas.com",
        password_hash=hash_password("admin@123"),
        is_active=True,
    )
    service = AuthService(FakeSession(user))  # type: ignore[arg-type]

    authenticated_user = await service.authenticate("admin@atlas.com", "admin@123")

    assert authenticated_user is user


async def test_authenticate_rejects_inactive_user() -> None:
    """authenticate returns None for inactive users."""
    user = FakeUser(
        email="admin@atlas.com",
        password_hash=hash_password("admin@123"),
        is_active=False,
    )
    service = AuthService(FakeSession(user))  # type: ignore[arg-type]

    authenticated_user = await service.authenticate("admin@atlas.com", "admin@123")

    assert authenticated_user is None


async def test_authenticate_rejects_unknown_user() -> None:
    """authenticate returns None when no user matches the email."""
    service = AuthService(FakeSession(None))  # type: ignore[arg-type]

    authenticated_user = await service.authenticate("admin@atlas.com", "admin@123")

    assert authenticated_user is None


async def test_authenticate_rejects_wrong_password() -> None:
    """authenticate returns None when the password does not match."""
    user = FakeUser(
        email="admin@atlas.com",
        password_hash=hash_password("admin@123"),
        is_active=True,
    )
    service = AuthService(FakeSession(user))  # type: ignore[arg-type]

    authenticated_user = await service.authenticate("admin@atlas.com", "wrong-password")

    assert authenticated_user is None
