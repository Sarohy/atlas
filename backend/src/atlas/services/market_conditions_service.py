"""Market Conditions service.

Fetches current Brent crude oil prices and VIX index value.
This is a ticker-independent snapshot used by the frontend to compute
the regime modifier locally, avoiding a per-ticker round-trip.

Sources:
  Brent crude — Alpha Vantage BRENT daily (primary) / Yahoo Finance BZ=F (fallback)
  VIX         — Alpha Vantage GLOBAL_QUOTE ^VIX (primary) / Yahoo Finance (fallback)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx

from atlas.schemas.market_conditions import MarketConditionsResponse
from atlas.services.regime_modifier_service import (
    _YAHOO_BRENT_URL,
    _YAHOO_VIX_URL,
    _parse_yahoo_brent_payload,
    _parse_yahoo_vix_payload,
)

logger = logging.getLogger(__name__)


class MarketConditionsService:
    """Fetches Brent crude and VIX values for regime rule evaluation."""

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
        """Fetch the two most recent Brent crude closes from Yahoo Finance (BZ=F).

        Returns [] if Yahoo Finance is unreachable or returns no price.
        """
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
            logger.warning("Yahoo Finance Brent returned no price")
        except Exception:
            logger.warning("Yahoo Finance Brent fetch failed")
        return []

    async def _fetch_vix(self, client: httpx.AsyncClient) -> float | None:
        """Fetch the latest VIX from Yahoo Finance (^VIX).

        Returns None if Yahoo Finance is unreachable or returns no price.
        """
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
            logger.warning("Yahoo Finance VIX returned no price")
        except Exception:
            logger.warning("Yahoo Finance VIX fetch failed")
        return None
