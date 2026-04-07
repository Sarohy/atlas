"""Shared API dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.services.auth import AuthService


def get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    """Provide the auth service for request handlers."""
    return AuthService(session)
