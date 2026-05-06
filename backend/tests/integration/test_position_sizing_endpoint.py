"""Integration tests for GET /api/v1/position-sizing/{ticker}.

These tests focus on the ``base_score`` query parameter that lets the UI
pass Framework 1's already-computed score, avoiding a second independent
computation and keeping Framework 3 in sync.

Score-to-action bands (v7.3.5):
  >= 85       T1_ELITE    — CORE — LEAPS ELIGIBLE, 5-10% NAV
  80-84       T1          — CORE POSITION, 2-4% NAV
  70-79       T2          — GTC ADDS PERMITTED, 0.5-1.5% NAV
  50-69       T3          — SMALL POSITION ONLY, 0-0.5% NAV
  < 50        BELOW_GATE  — exit rules active
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# base_score short-circuit — no external I/O, fully synchronous path
# ---------------------------------------------------------------------------


async def test_base_score_57_returns_t3(client: AsyncClient) -> None:
    """Score 57 → T3 (50-69 band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=57")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAOI"
    assert data["conviction_score"] == 57
    assert data["tier"] == "T3"
    assert data["action"] == "SMALL POSITION ONLY"


async def test_base_score_63_returns_t3(client: AsyncClient) -> None:
    """Score 63 → T3."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=63")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "T3"
    assert data["conviction_score"] == 63


async def test_base_score_91_returns_t1_elite(client: AsyncClient) -> None:
    """Score 91 → T1_ELITE."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=91")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "T1_ELITE"
    assert data["action"] == "CORE — LEAPS ELIGIBLE"
    assert data["leaps_eligible"] is True


async def test_base_score_85_returns_t1_elite(client: AsyncClient) -> None:
    """Score 85 → T1_ELITE (lower boundary)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=85")
    assert response.status_code == 200
    assert response.json()["tier"] == "T1_ELITE"


async def test_base_score_84_returns_t1(client: AsyncClient) -> None:
    """Score 84 → T1 (upper boundary of T1 band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=84")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "T1"
    assert data["grey_zone"] is False
    assert data["consensus_required"] is False


async def test_base_score_77_returns_t2(client: AsyncClient) -> None:
    """Score 77 → T2 (upper boundary of GTC band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=77")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "T2"
    assert data["action"] == "GTC ADDS PERMITTED"
    assert data["adds_permitted"] is True


async def test_base_score_49_returns_below_gate(client: AsyncClient) -> None:
    """Score 49 → BELOW_GATE."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=49")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "BELOW_GATE"
    assert data["trigger_exit_rules"] is True


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


async def test_concentration_cap_blocks_t1_elite_adds(client: AsyncClient) -> None:
    """Score 87 with concentration_cap_active=true → adds_permitted is False."""
    response = await client.get(
        "/api/v1/position-sizing/AAOI?base_score=87&concentration_cap_active=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "T1_ELITE"
    assert data["adds_permitted"] is False
