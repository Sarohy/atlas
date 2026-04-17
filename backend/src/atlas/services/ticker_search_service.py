"""Service for searching tickers via the Polygon.io Reference API."""

from __future__ import annotations

from typing import Any

import httpx

from atlas.schemas.ticker import TickerSearchResult

# Polygon reference tickers endpoint — stable v3 path.
_POLYGON_SEARCH_URL = "https://api.polygon.io/v3/reference/tickers"

# Maximum results to request per search query — keeps the response lean.
_MAX_RESULTS = 10


def _ticker_upper_bound(prefix: str) -> str:
    """Return the exclusive upper bound for a ticker prefix range query.

    E.g. "M" → "N", "MU" → "MV", "MUR" → "MUS".
    If the last character is "Z" it is dropped and the previous char is
    incremented, so "MZ" → "N".  Pure "Z"s fall back to a wide sentinel.
    """
    upper = prefix.upper()
    while upper:
        last = upper[-1]
        if last < "Z":
            return upper[:-1] + chr(ord(last) + 1)
        upper = upper[:-1]
    # All characters were 'Z' — return a sentinel beyond any ticker.
    return "ZZZ"


class TickerSearchService:
    """Thin wrapper around the Polygon.io REST API for ticker look-ups."""

    def __init__(self, api_key: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._client = client

    async def search(self, query: str) -> list[TickerSearchResult]:
        """Search for active tickers whose symbol starts with *query*.

        Uses Polygon's ``ticker.gte`` / ``ticker.lte`` range parameters so
        that a query of "M" returns M, MA, MAA … MZ* instead of any stock
        whose *company name* happens to contain the letter M.

        Returns up to ``_MAX_RESULTS`` results sorted by ticker symbol.
        Raises ``httpx.HTTPStatusError`` on non-2xx responses.
        """
        upper = _ticker_upper_bound(query)
        response = await self._client.get(
            _POLYGON_SEARCH_URL,
            params={
                "ticker.gte": query.upper(),
                "ticker.lte": upper,
                "active": "true",
                "sort": "ticker",
                "limit": _MAX_RESULTS,
                "apiKey": self._api_key,
            },
        )
        response.raise_for_status()

        payload: dict[str, Any] = response.json()
        raw_results: list[dict[str, Any]] = [
            r for r in payload.get("results", [])
            if isinstance(r, dict)
        ]

        return [
            TickerSearchResult(
                ticker=str(r.get("ticker", "")),
                name=str(r.get("name", "")),
                market=str(r.get("market", "")),
                type=str(r.get("type", "")),
            )
            for r in raw_results
        ]
