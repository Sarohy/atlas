"""Unit tests for the backend seed module."""

from atlas.seed import INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_PASSWORD_HASH, seed_initial_admin
from atlas.core.security import verify_password


class FakeScalarResult:
    """Simple stand-in for SQLAlchemy scalar query results."""

    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        """Return the configured scalar value."""
        return self._value


class FakeSession:
    """Very small async session double for seed tests."""

    def __init__(self, existing_user: object | None = None) -> None:
        self.added_user: object | None = None
        self.commit_called = False
        self.existing_user = existing_user
        self.refresh_called_with: object | None = None

    async def execute(self, _statement: object) -> FakeScalarResult:
        """Return the configured result for the admin lookup."""
        return FakeScalarResult(self.existing_user)

    def add(self, user: object) -> None:
        """Capture the added user."""
        self.added_user = user

    async def commit(self) -> None:
        """Track commit calls."""
        self.commit_called = True

    async def refresh(self, user: object) -> None:
        """Track refresh calls."""
        self.refresh_called_with = user


async def test_seed_initial_admin_creates_admin_when_missing() -> None:
    """seed_initial_admin creates the initial admin user exactly once."""
    session = FakeSession()

    was_created = await seed_initial_admin(session)  # type: ignore[arg-type]

    assert was_created is True
    assert session.added_user is not None
    assert getattr(session.added_user, "email") == INITIAL_ADMIN_EMAIL
    assert verify_password("admin@123", INITIAL_ADMIN_PASSWORD_HASH) is True
    assert session.commit_called is True
    assert session.refresh_called_with is session.added_user


async def test_seed_initial_admin_is_noop_when_admin_exists() -> None:
    """seed_initial_admin does not create a duplicate admin user."""
    existing_user = object()
    session = FakeSession(existing_user=existing_user)

    was_created = await seed_initial_admin(session)  # type: ignore[arg-type]

    assert was_created is False
    assert session.added_user is None
    assert session.commit_called is False
