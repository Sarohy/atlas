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
async def test_fetch_alpha_vantage_cached_reuses_fresh_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


# ---------------------------------------------------------------------------
# Generic single-flight memoizer (cached_call) + shared Polygon bars
# ---------------------------------------------------------------------------


import asyncio  # noqa: E402
from datetime import date  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    cache.clear_provider_response_cache()
    yield
    cache.clear_provider_response_cache()


async def test_cached_call_dedupes_within_ttl() -> None:
    calls = {"n": 0}

    async def factory() -> dict[str, int]:
        calls["n"] += 1
        return {"v": calls["n"]}

    a = await cache.cached_call(cache_key="k", factory=factory)
    b = await cache.cached_call(cache_key="k", factory=factory)
    assert a == b == {"v": 1}
    assert calls["n"] == 1  # second call served from cache


async def test_cached_call_single_flight_collapses_concurrent() -> None:
    calls = {"n": 0}

    async def slow() -> dict[str, int]:
        calls["n"] += 1
        await asyncio.sleep(0.02)
        return {"v": calls["n"]}

    results = await asyncio.gather(
        cache.cached_call(cache_key="sf", factory=slow),
        cache.cached_call(cache_key="sf", factory=slow),
        cache.cached_call(cache_key="sf", factory=slow),
    )
    assert results == [{"v": 1}, {"v": 1}, {"v": 1}]
    assert calls["n"] == 1  # all three collapsed into one upstream call


async def test_cached_call_does_not_cache_empty() -> None:
    calls = {"n": 0}

    async def empty() -> list[int]:
        calls["n"] += 1
        return []

    await cache.cached_call(cache_key="e", factory=empty)
    await cache.cached_call(cache_key="e", factory=empty)
    assert calls["n"] == 2  # empty result not cached -> retried


async def test_cached_call_serves_stale_on_failure() -> None:
    state = {"fail": False}

    async def factory() -> dict[str, str]:
        if state["fail"]:
            raise RuntimeError("upstream down")
        return {"ok": "yes"}

    first = await cache.cached_call(cache_key="s", factory=factory, ttl=0.0)
    assert first == {"ok": "yes"}
    state["fail"] = True
    # ttl=0 -> fresh window already expired, factory raises -> stale served.
    second = await cache.cached_call(cache_key="s", factory=factory)
    assert second == {"ok": "yes"}


async def test_polygon_bars_fetched_once_across_callers() -> None:
    client = _FakeClient([{"results": [{"c": 1.0}, {"c": 2.0}]}])
    today = date(2026, 6, 16)
    start = date(2026, 6, 1)
    kw = {"ticker": "MU", "api_key": "key", "from_date": start, "to_date": today}

    # Two "components" (F1 + an overlay) request the same ticker/window.
    bars1 = await cache.fetch_polygon_daily_bars_cached(client, **kw)  # type: ignore[arg-type]
    bars2 = await cache.fetch_polygon_daily_bars_cached(client, **kw)  # type: ignore[arg-type]
    assert bars1 == bars2 == [{"c": 1.0}, {"c": 2.0}]
    assert client.calls == 1  # one upstream Polygon call serves both
