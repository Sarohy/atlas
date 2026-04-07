"""Authentication business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.security import verify_password
from atlas.models.user import User


class AuthService:
    """Authenticate users against the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authenticate(self, email: str, password: str) -> User | None:
        """Return the matching active user when credentials are valid."""
        user = await self._get_user_by_email(email)
        if user is None or user.is_active is False:
            return None
        if verify_password(password, user.password_hash) is False:
            return None
        return user

    async def _get_user_by_email(self, email: str) -> User | None:
        """Fetch a user by email address."""
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
