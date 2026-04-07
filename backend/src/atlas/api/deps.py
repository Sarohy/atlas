"""Shared API dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.services.auth import AuthService

DB_SESSION_DEPENDENCY = Depends(get_db_session)

def get_auth_service(session: AsyncSession = DB_SESSION_DEPENDENCY) -> AuthService:
    """Provide the auth service for request handlers."""
    return AuthService(session)
