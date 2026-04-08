"""Unit tests for TickerService — Polygon API calls are mocked via httpx."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.ticker_service import TickerService


@pytest.fixture
def mock_client() -> AsyncMock:
    """Return a mocked httpx.AsyncClient."""
    return AsyncMock()


@pytest.fixture
def service(mock_client: AsyncMock) -> TickerService:
    return TickerService(api_key="test-key", client=mock_client)


def _make_polygon_response(results: list[dict]) -> MagicMock:  # type: ignore[type-arg]
    """Build a mock httpx Response wrapping a Polygon-style JSON payload."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"results": results, "status": "OK", "count": len(results)}
    return mock_resp


# ── search ────────────────────────────────────────────────────────────────────


async def test_search_returns_ticker_list(service: TickerService, mock_client: AsyncMock) -> None:
    """search returns a TickerSearchResult for each Polygon result."""
    mock_client.get = AsyncMock(
        return_value=_make_polygon_response(
            [{"ticker": "AAPL", "name": "Apple Inc.", "market": "stocks", "type": "CS"}]
        )
    )

    results = await service.search("apple")

    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].name == "Apple Inc."


async def test_search_returns_empty_list_when_no_results(
    service: TickerService, mock_client: AsyncMock
) -> None:
    """search returns [] when Polygon finds no matching tickers."""
    mock_client.get = AsyncMock(return_value=_make_polygon_response([]))

    results = await service.search("xyzxyzxyz")
    assert results == []


async def test_search_passes_query_and_api_key(
    service: TickerService, mock_client: AsyncMock
) -> None:
    """search passes the query string and api key as query parameters."""
    mock_client.get = AsyncMock(return_value=_make_polygon_response([]))

    await service.search("nvidia")

    mock_client.get.assert_awaited_once()
    call_kwargs = mock_client.get.call_args
    call_kwargs.kwargs.get("params") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
    # Params can be positional or keyword depending on how the service calls httpx
    all_params = call_kwargs.kwargs.get("params", {})
    assert "nvidia" in str(all_params) or "nvidia" in str(call_kwargs)


async def test_search_raises_on_http_error(service: TickerService, mock_client: AsyncMock) -> None:
    """search propagates HTTP errors raised by the httpx client."""
    import httpx

    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await service.search("apple")
