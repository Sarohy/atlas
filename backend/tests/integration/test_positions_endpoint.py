"""Integration tests for the /api/v1/positions endpoints."""

from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from atlas.db.session import get_db_session
from atlas.main import create_app
from atlas.models.position import Position


def _make_position(
    *,
    position_id: int = 1,
    ticker: str = "AAPL",
    company_name: str = "Apple Inc.",
    shares: Decimal = Decimal("100"),
) -> Position:
    """Helper — construct a Position instance without a real DB."""
    p = Position(ticker=ticker, company_name=company_name, shares=shares)
    p.id = position_id
    from datetime import datetime

    p.created_at = datetime.now(tz=UTC)
    p.updated_at = datetime.now(tz=UTC)
    return p


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
async def client(mock_session: AsyncMock) -> AsyncClient:
    """ASGI client with the DB session overridden by a mock."""
    app = create_app()

    async def _override_session():  # type: ignore[return]
        yield mock_session

    app.dependency_overrides[get_db_session] = _override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── GET /positions ────────────────────────────────────────────────────────────


async def test_list_positions_returns_200_with_list(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """GET /positions returns 200 and a JSON array."""
    positions = [_make_position(position_id=1, ticker="AAPL"), _make_position(position_id=2, ticker="MSFT")]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = positions
    mock_session.execute = AsyncMock(return_value=result_mock)

    response = await client.get("/api/v1/positions")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["ticker"] == "AAPL"


async def test_list_positions_returns_empty_list_when_none(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """GET /positions returns [] when no positions are saved."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    response = await client.get("/api/v1/positions")
    assert response.status_code == 200
    assert response.json() == []


# ── POST /positions ───────────────────────────────────────────────────────────


async def test_create_position_returns_201(client: AsyncClient, mock_session: AsyncMock) -> None:
    """POST /positions returns 201 with the created position."""
    from datetime import datetime

    # get_by_ticker returns None (no duplicate)
    no_existing = MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=no_existing)
    mock_session.flush = AsyncMock()

    # refresh side-effect: populate DB-generated fields on the object
    async def _populate_db_fields(obj: object) -> None:
        obj.id = 1  # type: ignore[attr-defined]
        obj.created_at = datetime.now(tz=UTC)  # type: ignore[attr-defined]
        obj.updated_at = datetime.now(tz=UTC)  # type: ignore[attr-defined]

    mock_session.refresh = AsyncMock(side_effect=_populate_db_fields)

    response = await client.post(
        "/api/v1/positions",
        json={"ticker": "NVDA", "company_name": "NVIDIA Corp", "shares": "25"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "NVDA"


async def test_create_position_returns_409_on_duplicate(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """POST /positions returns 409 when the ticker is already in the portfolio."""
    existing = _make_position(ticker="AAPL")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=result_mock)

    response = await client.post(
        "/api/v1/positions",
        json={"ticker": "AAPL", "company_name": "Apple Inc.", "shares": "100"},
    )
    assert response.status_code == 409


# ── PATCH /positions/{id} ─────────────────────────────────────────────────────


async def test_update_position_returns_200(client: AsyncClient, mock_session: AsyncMock) -> None:
    """PATCH /positions/{id} returns 200 with updated shares."""
    existing = _make_position(position_id=1, ticker="AAPL", shares=Decimal("100"))
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    response = await client.patch("/api/v1/positions/1", json={"shares": "200"})

    assert response.status_code == 200
    assert Decimal(response.json()["shares"]) == Decimal("200")


async def test_update_position_returns_404_for_missing_id(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """PATCH /positions/{id} returns 404 when the id does not exist."""
    mock_session.get = AsyncMock(return_value=None)

    response = await client.patch("/api/v1/positions/999", json={"shares": "50"})
    assert response.status_code == 404


# ── DELETE /positions/{id} ────────────────────────────────────────────────────


async def test_delete_position_returns_204(client: AsyncClient, mock_session: AsyncMock) -> None:
    """DELETE /positions/{id} returns 204 on success."""
    existing = _make_position(position_id=1)
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    response = await client.delete("/api/v1/positions/1")
    assert response.status_code == 204


async def test_delete_position_returns_404_for_missing_id(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """DELETE /positions/{id} returns 404 when the id does not exist."""
    mock_session.get = AsyncMock(return_value=None)

    response = await client.delete("/api/v1/positions/999")
    assert response.status_code == 404
