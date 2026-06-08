"""Shared provider-response cache for third-party API calls.

This module centralizes short-lived caching and request de-duplication for
upstream providers so repeated framework requests do not repeatedly hit vendor
rate limits.

Current implementation covers Alpha Vantage JSON endpoints.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_AV_BASE_URL = "https://www.alphavantage.co/query"
_AV_DEFAULT_TIMEOUT = 15.0

# Per-function freshness windows (seconds).
_AV_TTL_SECONDS: dict[str, float] = {
    "OVERVIEW": 300.0,
    "EARNINGS": 300.0,
    "INCOME_STATEMENT": 300.0,
    "BALANCE_SHEET": 300.0,
    "CASH_FLOW": 300.0,
}

# Serve stale data for this long after expiry when upstream is unavailable or
# rate-limited. This avoids hard failures during short burst limits.
_AV_STALE_TTL_SECONDS = 1800.0


@dataclass(slots=True)
class _CacheEntry:
    payload: dict[str, Any]
    fresh_until: float
    stale_until: float


_av_cache: dict[tuple[str, str], _CacheEntry] = {}
_av_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _now() -> float:
    return monotonic()


def _cache_key(function: str, symbol: str) -> tuple[str, str]:
    return (function.upper(), symbol.upper())


def _is_rate_limited(payload: dict[str, Any]) -> bool:
    return "Note" in payload or "Information" in payload


def _get_lock(key: tuple[str, str]) -> asyncio.Lock:
    lock = _av_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _av_locks[key] = lock
    return lock


def _get_fresh(key: tuple[str, str]) -> dict[str, Any] | None:
    entry = _av_cache.get(key)
    if entry is None:
        return None
    if entry.fresh_until >= _now():
        return entry.payload
    return None


def _get_stale(key: tuple[str, str]) -> dict[str, Any] | None:
    entry = _av_cache.get(key)
    if entry is None:
        return None
    if entry.stale_until >= _now():
        return entry.payload
    return None


def _set_cache(
    key: tuple[str, str],
    payload: dict[str, Any],
    ttl_seconds: float,
    stale_ttl_seconds: float,
) -> None:
    now = _now()
    _av_cache[key] = _CacheEntry(
        payload=payload,
        fresh_until=now + ttl_seconds,
        stale_until=now + stale_ttl_seconds,
    )


async def fetch_alpha_vantage_cached(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    function: str,
    symbol: str,
    timeout: float = _AV_DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch Alpha Vantage JSON with shared cache and request de-duplication.

    Behavior:
    - returns fresh cached payload when present;
    - collapses concurrent in-flight requests per (function, symbol);
    - stores successful payloads with function-specific TTL;
    - on upstream rate-limit/error, returns stale cache if available.
    """
    if not api_key:
        return {}

    normalized_function = function.upper()
    normalized_symbol = symbol.upper()
    key = _cache_key(normalized_function, normalized_symbol)

    cached = _get_fresh(key)
    if cached is not None:
        return cached

    lock = _get_lock(key)
    async with lock:
        cached = _get_fresh(key)
        if cached is not None:
            return cached

        try:
            resp = await client.get(
                _AV_BASE_URL,
                params={
                    "function": normalized_function,
                    "symbol": normalized_symbol,
                    "apikey": api_key,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            payload: Any = resp.json()
            if not isinstance(payload, dict):
                payload = {}

            if _is_rate_limited(payload):
                stale = _get_stale(key)
                if stale is not None:
                    logger.debug(
                        "AV %s rate-limited for %s; serving stale cache",
                        normalized_function,
                        normalized_symbol,
                    )
                    return stale
                logger.debug(
                    "AV %s rate-limited for %s; no cache available",
                    normalized_function,
                    normalized_symbol,
                )
                return {}

            ttl = _AV_TTL_SECONDS.get(normalized_function, 300.0)
            _set_cache(key, payload, ttl_seconds=ttl, stale_ttl_seconds=_AV_STALE_TTL_SECONDS)
            return payload
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError, TypeError):
            stale = _get_stale(key)
            if stale is not None:
                logger.debug(
                    "AV %s fetch failed for %s; serving stale cache",
                    normalized_function,
                    normalized_symbol,
                )
                return stale
            return {}


def clear_provider_response_cache() -> None:
    """Clear in-memory provider cache (used by tests)."""
    _av_cache.clear()
    _av_locks.clear()
