"""Shared pytest fixtures for the ATLAS test suite."""

from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True, scope="session")
def _patch_db_pool() -> Generator[None, None, None]:
    """Replace the SQLAlchemy engine with a NullPool engine for the test session.

    asyncpg connections are bound to the event loop they are created on.
    With pytest-asyncio's per-function event loops, the module-level engine
    would reuse connections across loops, causing RuntimeError on the second+
    test that makes a real DB call.  NullPool disables pooling so every
    request creates a fresh connection on the current loop.
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import NullPool

    import atlas.db.session as db_session
    from atlas.config import get_settings

    settings = get_settings()
    test_engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        future=True,
    )
    test_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autoflush=False,
    )

    original_engine = db_session.engine
    original_factory = db_session.AsyncSessionLocal

    db_session.engine = test_engine  # type: ignore[assignment]
    db_session.AsyncSessionLocal = test_session_factory  # type: ignore[assignment]

    yield

    db_session.engine = original_engine
    db_session.AsyncSessionLocal = original_factory


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    from atlas.main import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_tranche_stores() -> Generator[None, None, None]:
    """Reset Framework 4 in-memory state between tests to prevent pollution."""
    from atlas.services.tranche_sizing_service import reset_t1_fired_store

    reset_t1_fired_store()
    yield
    reset_t1_fired_store()
