from __future__ import annotations

from typing import Any

import pytest

from atlas.services import provider_response_cache as cache


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls = 0

    async def get(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
        payload = self._payloads[min(self.calls, len(self._payloads) - 1)]
        self.calls += 1
        return _FakeResponse(payload)


@pytest.mark.asyncio
async def test_fetch_alpha_vantage_cached_reuses_fresh_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    cache.clear_provider_response_cache()
    now = [1_000.0]
    monkeypatch.setattr(cache, "_now", lambda: now[0])

    client = _FakeClient([{"Symbol": "SNDK", "ok": True}])

    first = await cache.fetch_alpha_vantage_cached(
        client,
        api_key="key",
        function="OVERVIEW",
        symbol="SNDK",
    )
    second = await cache.fetch_alpha_vantage_cached(
        client,
        api_key="key",
        function="OVERVIEW",
        symbol="SNDK",
    )

    assert first == {"Symbol": "SNDK", "ok": True}
    assert second == first
    assert client.calls == 1


@pytest.mark.asyncio
async def test_fetch_alpha_vantage_cached_serves_stale_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache.clear_provider_response_cache()
    now = [2_000.0]
    monkeypatch.setattr(cache, "_now", lambda: now[0])

    client = _FakeClient(
        [
            {"Symbol": "SNDK", "ok": True},
            {"Note": "Thank you for using Alpha Vantage"},
        ]
    )

    fresh = await cache.fetch_alpha_vantage_cached(
        client,
        api_key="key",
        function="OVERVIEW",
        symbol="SNDK",
    )

    # Move past fresh TTL (300s) but still within stale TTL (1800s).
    now[0] += 301.0

    stale = await cache.fetch_alpha_vantage_cached(
        client,
        api_key="key",
        function="OVERVIEW",
        symbol="SNDK",
    )

    assert fresh == {"Symbol": "SNDK", "ok": True}
    assert stale == fresh
    assert client.calls == 2
