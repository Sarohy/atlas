"""Integration tests for GET /api/v1/position-sizing/{ticker}.

These tests focus on the ``base_score`` query parameter that lets the UI
pass Framework 1's already-computed score, avoiding a second independent
computation and keeping Framework 3 in sync.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# base_score short-circuit — no external I/O, fully synchronous path
# ---------------------------------------------------------------------------


async def test_base_score_57_returns_reduce_aggressively(client: AsyncClient) -> None:
    """Score 57 → REDUCE AGGRESSIVELY when caller passes base_score."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=57")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAOI"
    assert data["conviction_score"] == 57
    assert data["action"] == "REDUCE AGGRESSIVELY"


async def test_base_score_63_returns_reduce_25_50(client: AsyncClient) -> None:
    """Score 63 → REDUCE 25-50%."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=63")
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "REDUCE 25-50%"
    assert data["conviction_score"] == 63


async def test_base_score_91_returns_maximum_position(client: AsyncClient) -> None:
    """Score 91 → MAXIMUM POSITION."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=91")
    assert response.status_code == 200
    assert response.json()["action"] == "MAXIMUM POSITION"


async def test_base_score_80_returns_hold_full(client: AsyncClient) -> None:
    """Score 80 → HOLD FULL (lower boundary of HOLD FULL band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=80")
    assert response.status_code == 200
    assert response.json()["action"] == "HOLD FULL"


async def test_base_score_79_returns_hold(client: AsyncClient) -> None:
    """Score 79 → HOLD (upper boundary of HOLD band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=79")
    assert response.status_code == 200
    assert response.json()["action"] == "HOLD"


async def test_base_score_54_returns_exit(client: AsyncClient) -> None:
    """Score 54 → EXIT (one below REDUCE AGGRESSIVELY floor)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=54")
    assert response.status_code == 200
    assert response.json()["action"] == "EXIT"


async def test_base_score_clamps_above_100(client: AsyncClient) -> None:
    """base_score > 100 is clamped to 100 before mapping."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=150")
    assert response.status_code == 200
    assert response.json()["conviction_score"] == 100


async def test_base_score_clamps_below_0(client: AsyncClient) -> None:
    """base_score < 0 is clamped to 0 before mapping."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=-10")
    assert response.status_code == 200
    assert response.json()["conviction_score"] == 0


async def test_ticker_is_normalised_to_uppercase(client: AsyncClient) -> None:
    """Ticker supplied in lower-case is normalised before processing."""
    response = await client.get("/api/v1/position-sizing/aaoi?base_score=63")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAOI"
