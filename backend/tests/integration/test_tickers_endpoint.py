"""Integration tests for the /api/v1/tickers/search endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from atlas.main import create_app


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── GET /tickers/search ───────────────────────────────────────────────────────


async def test_ticker_search_returns_200_with_results(client: AsyncClient) -> None:
    """GET /tickers/search?q=apple returns 200 and a list of tickers."""
    from atlas.schemas.position import TickerSearchResult

    mock_results = [
        TickerSearchResult(ticker="AAPL", name="Apple Inc.", market="stocks", type="CS"),
    ]

    with (
        patch("atlas.api.v1.tickers.get_settings") as mock_settings,
        patch("atlas.api.v1.tickers.TickerService") as mock_service,
    ):
        mock_settings.return_value.polygon_api_key = "test-key"
        instance = mock_service.return_value
        instance.search = AsyncMock(return_value=mock_results)

        response = await client.get("/api/v1/tickers/search?q=apple")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_ticker_search_requires_q_param(client: AsyncClient) -> None:
    """GET /tickers/search without q returns 422 Unprocessable Entity."""
    response = await client.get("/api/v1/tickers/search")
    assert response.status_code == 422


async def test_ticker_search_returns_503_when_api_key_missing(client: AsyncClient) -> None:
    """GET /tickers/search returns 503 when POLYGON_API_KEY is not configured."""
    with patch("atlas.api.v1.tickers.get_settings") as mock_settings:
        mock_settings.return_value.polygon_api_key = ""

        response = await client.get("/api/v1/tickers/search?q=apple")

    assert response.status_code == 503
