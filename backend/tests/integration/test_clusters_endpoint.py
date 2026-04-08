"""Integration tests for the /api/v1/clusters endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from atlas.db.session import get_db_session
from atlas.main import create_app
from atlas.models.cluster import Cluster
from atlas.models.ticker import Ticker


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_cluster(
    cluster_id: int = 1,
    name: str = "AI Core",
    color: str = "#4a90d9",
    tickers: list[Ticker] | None = None,
) -> Cluster:
    c = Cluster(name=name, color=color)
    c.id = cluster_id
    c.tickers = tickers or []
    c.created_at = datetime.now(tz=UTC)
    c.updated_at = datetime.now(tz=UTC)
    return c


def _make_ticker(ticker: str = "AAPL", cluster_id: int | None = None) -> Ticker:
    t = Ticker(ticker=ticker, company_name=f"{ticker} Inc.", shares=Decimal("100"))
    t.id = 1
    t.cluster_id = cluster_id
    t.created_at = datetime.now(tz=UTC)
    t.updated_at = datetime.now(tz=UTC)
    return t


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
async def client(mock_session: AsyncMock) -> AsyncClient:  # type: ignore[override]
    app = create_app()

    async def _override():  # type: ignore[return]
        yield mock_session

    app.dependency_overrides[get_db_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── GET /clusters ─────────────────────────────────────────────────────────────


async def test_list_clusters_returns_200(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """GET /clusters returns 200 and a list."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [_make_cluster()]
    mock_session.execute = AsyncMock(return_value=result_mock)

    resp = await client.get("/api/v1/clusters")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "AI Core"
    assert data[0]["color"] == "#4a90d9"


async def test_list_clusters_returns_empty_list(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """GET /clusters returns [] when no clusters exist."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    resp = await client.get("/api/v1/clusters")
    assert resp.status_code == 200
    assert resp.json() == []


# ── POST /clusters ────────────────────────────────────────────────────────────


async def test_create_cluster_returns_201(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """POST /clusters returns 201 with the new cluster."""
    new_cluster = _make_cluster(cluster_id=2, name="Energy", color="#4ade80")
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = new_cluster
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()

    resp = await client.post("/api/v1/clusters", json={"name": "Energy", "color": "#4ade80"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Energy"


async def test_create_cluster_invalid_color_returns_422(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """POST /clusters with an invalid hex colour returns 422."""
    resp = await client.post("/api/v1/clusters", json={"name": "Bad", "color": "blue"})
    assert resp.status_code == 422


# ── PATCH /clusters/{id} ──────────────────────────────────────────────────────


async def test_update_cluster_returns_200(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """PATCH /clusters/{id} returns 200 with the updated cluster."""
    existing = _make_cluster(name="Old Name")
    updated = _make_cluster(name="New Name")
    mock_session.get = AsyncMock(return_value=existing)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = updated
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.flush = AsyncMock()

    resp = await client.patch("/api/v1/clusters/1", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_update_cluster_returns_404_when_missing(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """PATCH /clusters/{id} returns 404 when the cluster does not exist."""
    mock_session.get = AsyncMock(return_value=None)
    resp = await client.patch("/api/v1/clusters/999", json={"name": "x"})
    assert resp.status_code == 404


# ── DELETE /clusters/{id} ─────────────────────────────────────────────────────


async def test_delete_cluster_returns_204(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """DELETE /clusters/{id} returns 204 on success."""
    existing = _make_cluster()
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    resp = await client.delete("/api/v1/clusters/1")
    assert resp.status_code == 204


async def test_delete_cluster_returns_404_when_missing(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """DELETE /clusters/{id} returns 404 when the cluster does not exist."""
    mock_session.get = AsyncMock(return_value=None)
    resp = await client.delete("/api/v1/clusters/999")
    assert resp.status_code == 404
