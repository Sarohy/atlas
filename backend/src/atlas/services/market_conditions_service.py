"""Market Conditions service.

Fetches current Brent crude oil prices and VIX index value.
This is a ticker-independent snapshot used by the frontend to compute
the regime modifier locally, avoiding a per-ticker round-trip.

Sources:
  Brent crude — Yahoo Finance BZ=F (primary) / Alpha Vantage BRENT daily (fallback)
  VIX         — Alpha Vantage GLOBAL_QUOTE (primary) / Yahoo Finance (fallback)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx

from atlas.schemas.market_conditions import MarketConditionsResponse
from atlas.services.regime_modifier_service import (
    _AV_BRENT_URL,
    _AV_GLOBAL_QUOTE_URL,
    _BRENT_NUM_CLOSES,
    _YAHOO_BRENT_URL,
    _YAHOO_VIX_URL,
    _parse_yahoo_brent_payload,
    _parse_yahoo_vix_payload,
)

logger = logging.getLogger(__name__)

# Number of Brent closes to fetch (current + previous for consecutive check).
_BRENT_FETCH_COUNT: Final[int] = _BRENT_NUM_CLOSES


class MarketConditionsService:
    """Fetches Brent crude and VIX values for regime rule evaluation."""

    def __init__(self, alphavantage_api_key: str) -> None:
        self._av_key = alphavantage_api_key

    async def get_conditions(self) -> MarketConditionsResponse:
        """Fetch Brent and VIX concurrently and return a snapshot."""
        async with httpx.AsyncClient() as client:
            brent_closes, vix_value = await asyncio.gather(
                self._fetch_brent(client),
                self._fetch_vix(client),
                return_exceptions=False,
            )

        brent_price: float | None = brent_closes[0] if brent_closes else None
        brent_prev_price: float | None = brent_closes[1] if len(brent_closes) >= 2 else None

        return MarketConditionsResponse(
            brent_price=brent_price,
            brent_prev_price=brent_prev_price,
            vix_value=vix_value,
        )

    async def _fetch_brent(self, client: httpx.AsyncClient) -> list[float]:
        """Fetch the two most recent Brent crude closes.

        Tries Yahoo Finance (BZ=F) first; falls back to Alpha Vantage.
        """
        # ── Yahoo Finance (primary) ───────────────────────────────────────
        try:
            yf_response = await client.get(
                _YAHOO_BRENT_URL,
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=10.0,
            )
            yf_response.raise_for_status()
            closes = _parse_yahoo_brent_payload(yf_response.json())
            if closes:
                return closes
            logger.warning("Yahoo Finance Brent payload had no price; using Alpha Vantage fallback")
        except Exception:
            logger.warning("Yahoo Finance Brent fetch failed; using Alpha Vantage fallback")

        # ── Alpha Vantage (fallback) ──────────────────────────────────────
        try:
            response = await client.get(
                _AV_BRENT_URL,
                params={"function": "BRENT", "interval": "daily", "apikey": self._av_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: dict = response.json()  # type: ignore[type-arg]
            data: list[dict] = payload.get("data", [])  # type: ignore[type-arg]
            closes_av: list[float] = []
            for entry in data:
                raw = entry.get("value", ".")
                if raw != ".":
                    closes_av.append(float(raw))
                if len(closes_av) >= _BRENT_FETCH_COUNT:
                    break
            return closes_av
        except Exception:
            logger.exception("Alpha Vantage Brent fallback failed")
            return []

    async def _fetch_vix(self, client: httpx.AsyncClient) -> float | None:
        """Fetch VIX from Yahoo Finance; fall back to Alpha Vantage."""
        # ── Yahoo Finance (primary) ───────────────────────────────────────
        try:
            yf_response = await client.get(
                _YAHOO_VIX_URL,
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=10.0,
            )
            yf_response.raise_for_status()
            vix = _parse_yahoo_vix_payload(yf_response.json())
            if vix is not None:
                return vix
            logger.warning("Yahoo Finance VIX payload had no price; using Alpha Vantage fallback")
        except Exception:
            logger.warning("Yahoo Finance VIX fetch failed; using Alpha Vantage fallback")

        # ── Alpha Vantage (fallback) ──────────────────────────────────────
        try:
            response = await client.get(
                _AV_GLOBAL_QUOTE_URL,
                params={"function": "GLOBAL_QUOTE", "symbol": "^VIX", "apikey": self._av_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: dict = response.json()  # type: ignore[type-arg]
            quote: dict = payload.get("Global Quote", {})  # type: ignore[type-arg]
            price_str: str = quote.get("05. price", "")
            if price_str:
                return float(price_str)
            logger.warning("Alpha Vantage VIX returned empty quote")
        except Exception:
            logger.exception("Alpha Vantage VIX fallback failed")
        return None
