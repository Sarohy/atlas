"""Service for searching tickers via the Polygon.io Reference API."""

import httpx

from atlas.schemas.position import TickerSearchResult

# Polygon reference tickers endpoint — stable v3 path.
_POLYGON_SEARCH_URL = "https://api.polygon.io/v3/reference/tickers"

# Maximum results to request per search query — keeps the response lean.
_MAX_RESULTS = 10


class TickerService:
    """Thin wrapper around the Polygon.io REST API for ticker look-ups."""

    def __init__(self, api_key: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._client = client

    async def search(self, query: str) -> list[TickerSearchResult]:
        """Search for active tickers matching *query*.

        Returns up to ``_MAX_RESULTS`` results.
        Raises ``httpx.HTTPStatusError`` on non-2xx responses.
        """
        response = await self._client.get(
            _POLYGON_SEARCH_URL,
            params={
                "search": query,
                "active": "true",
                "limit": _MAX_RESULTS,
                "apiKey": self._api_key,
            },
        )
        response.raise_for_status()

        payload: dict = response.json()  # type: ignore[type-arg]
        raw_results: list[dict] = payload.get("results", [])  # type: ignore[type-arg]

        return [
            TickerSearchResult(
                ticker=r.get("ticker", ""),
                name=r.get("name", ""),
                market=r.get("market", ""),
                type=r.get("type", ""),
            )
            for r in raw_results
        ]
