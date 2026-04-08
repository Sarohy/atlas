"""Integration tests for portfolio endpoints (summary + cash management)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from atlas.db.session import get_db_session
from atlas.main import create_app
from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_config(
    cash: str = "3585000.00",
    floor_pct: str = "0.10",
) -> PortfolioConfig:
    cfg = PortfolioConfig(
        id=PORTFOLIO_CONFIG_ROW_ID,
        cash_balance=Decimal(cash),
        cash_floor_pct=Decimal(floor_pct),
    )
    cfg.created_at = datetime.now(tz=UTC)
    cfg.updated_at = datetime.now(tz=UTC)
    return cfg


def _make_ticker(
    ticker: str = "AAPL",
    shares: str = "100",
    position_value: str | None = "10000000",
) -> Ticker:
    t = Ticker(ticker=ticker, company_name=f"{ticker} Inc.", shares=Decimal(shares))
    t.id = 1
    t.position_value = Decimal(position_value) if position_value else None
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
async def client(mock_session: AsyncMock) -> AsyncClient:
    """ASGI client with the DB session replaced by a mock."""
    app = create_app()

    async def _override():  # type: ignore[return]
        yield mock_session

    app.dependency_overrides[get_db_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── GET /portfolio/summary ────────────────────────────────────────────────────


async def test_get_summary_returns_200(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """GET /portfolio/summary returns 200 with correct shape."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.get = AsyncMock(return_value=_make_config())

    resp = await client.get("/api/v1/portfolio/summary")
    assert resp.status_code == 200


async def test_get_summary_has_required_fields(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.get = AsyncMock(return_value=_make_config())

    data = (await client.get("/api/v1/portfolio/summary")).json()
    for field in (
        "total_nav",
        "invested_value",
        "invested_pct",
        "cash_balance",
        "cash_pct",
        "cash_floor",
        "cash_floor_pct",
        "deployable",
    ):
        assert field in data, f"Missing field: {field}"


async def test_get_summary_computes_totals(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    ticker = _make_ticker(position_value="20315000")
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [ticker]
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.get = AsyncMock(return_value=_make_config(cash="3585000"))

    data = (await client.get("/api/v1/portfolio/summary")).json()
    assert float(data["total_nav"]) == pytest.approx(23_900_000.0)
    assert float(data["invested_value"]) == pytest.approx(20_315_000.0)


async def test_get_summary_no_tickers_invested_is_zero(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.get = AsyncMock(return_value=_make_config())

    data = (await client.get("/api/v1/portfolio/summary")).json()
    assert float(data["invested_value"]) == pytest.approx(0.0)


# ── GET /portfolio/cash ───────────────────────────────────────────────────────


async def test_get_cash_returns_200(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    mock_session.get = AsyncMock(return_value=_make_config())
    resp = await client.get("/api/v1/portfolio/cash")
    assert resp.status_code == 200


async def test_get_cash_has_required_fields(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    mock_session.get = AsyncMock(return_value=_make_config())
    data = (await client.get("/api/v1/portfolio/cash")).json()
    assert "cash_balance" in data
    assert "cash_floor_pct" in data


# ── PUT /portfolio/cash ───────────────────────────────────────────────────────


async def test_update_cash_returns_200_with_new_value(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    cfg = _make_config(cash="0")
    mock_session.get = AsyncMock(return_value=cfg)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    resp = await client.put(
        "/api/v1/portfolio/cash", json={"cash_balance": "5000000.00"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["cash_balance"]) == pytest.approx(5_000_000.0)


async def test_update_cash_negative_balance_rejected(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    resp = await client.put(
        "/api/v1/portfolio/cash", json={"cash_balance": "-100.00"}
    )
    assert resp.status_code == 422


async def test_update_cash_floor_pct_above_1_rejected(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    resp = await client.put(
        "/api/v1/portfolio/cash",
        json={"cash_balance": "0", "cash_floor_pct": "1.5"},
    )
    assert resp.status_code == 422


# ── POST /portfolio/cash/adjust ───────────────────────────────────────────────


async def test_adjust_cash_positive_delta_adds_to_balance(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """Starting balance $20; adding $400 should yield $420."""
    cfg = _make_config(cash="20.00")
    mock_session.get = AsyncMock(return_value=cfg)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    resp = await client.post("/api/v1/portfolio/cash/adjust", json={"delta": "400.00"})
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["cash_balance"]) == pytest.approx(420.0)


async def test_adjust_cash_negative_delta_subtracts_from_balance(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """Starting balance $420; subtracting $30 should yield $390."""
    cfg = _make_config(cash="420.00")
    mock_session.get = AsyncMock(return_value=cfg)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    resp = await client.post(
        "/api/v1/portfolio/cash/adjust", json={"delta": "-30.00"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["cash_balance"]) == pytest.approx(390.0)


async def test_adjust_cash_clamps_at_zero_prevents_negative(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """Starting balance $10; subtracting $100 should clamp to $0, not go negative."""
    cfg = _make_config(cash="10.00")
    mock_session.get = AsyncMock(return_value=cfg)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    resp = await client.post(
        "/api/v1/portfolio/cash/adjust", json={"delta": "-100.00"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["cash_balance"]) == pytest.approx(0.0)


async def test_adjust_cash_missing_delta_is_rejected(
    client: AsyncClient, mock_session: AsyncMock
) -> None:
    """A request body without `delta` should return 422 Unprocessable Entity."""
    resp = await client.post("/api/v1/portfolio/cash/adjust", json={})
    assert resp.status_code == 422

