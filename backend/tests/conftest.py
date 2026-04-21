"""Shared pytest fixtures for the ATLAS test suite."""

from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient


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
