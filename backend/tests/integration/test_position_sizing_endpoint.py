"""Integration tests for GET /api/v1/position-sizing/{ticker}.

These tests focus on the ``base_score`` query parameter that lets the UI
pass Framework 1's already-computed score, avoiding a second independent
computation and keeping Framework 3 in sync.

Score-to-action bands (v7.3.4):
  >= 85       TIER_1         — CORE — LEAPS ELIGIBLE
  78 – 84     TIER_2_GREY    — GREY ZONE
  70 – 77     TIER_2         — GTC ADDS PERMITTED
  55 – 69     TIER_3         — SMALL POSITION ONLY
  < 55        WATCHLIST      — WATCHLIST (exit rules active)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# base_score short-circuit — no external I/O, fully synchronous path
# ---------------------------------------------------------------------------


async def test_base_score_57_returns_tier_3(client: AsyncClient) -> None:
    """Score 57 → TIER_3 (55-69 band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=57")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAOI"
    assert data["conviction_score"] == 57
    assert data["tier"] == "TIER_3"
    assert data["action"] == "SMALL POSITION ONLY"


async def test_base_score_63_returns_tier_3(client: AsyncClient) -> None:
    """Score 63 → TIER_3."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=63")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "TIER_3"
    assert data["conviction_score"] == 63


async def test_base_score_91_returns_tier_1(client: AsyncClient) -> None:
    """Score 91 → TIER_1."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=91")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "TIER_1"
    assert data["action"] == "CORE — LEAPS ELIGIBLE"
    assert data["leaps_eligible"] is True


async def test_base_score_85_returns_tier_1(client: AsyncClient) -> None:
    """Score 85 → TIER_1 (lower boundary)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=85")
    assert response.status_code == 200
    assert response.json()["tier"] == "TIER_1"


async def test_base_score_84_returns_tier_2_grey(client: AsyncClient) -> None:
    """Score 84 → TIER_2_GREY (upper boundary of grey zone)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=84")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "TIER_2_GREY"
    assert data["grey_zone"] is True
    assert data["consensus_required"] is True


async def test_base_score_77_returns_tier_2(client: AsyncClient) -> None:
    """Score 77 → TIER_2 (upper boundary of GTC band)."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=77")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "TIER_2"
    assert data["action"] == "GTC ADDS PERMITTED"
    assert data["adds_permitted"] is True


async def test_base_score_54_returns_watchlist(client: AsyncClient) -> None:
    """Score 54 → WATCHLIST."""
    response = await client.get("/api/v1/position-sizing/AAOI?base_score=54")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "WATCHLIST"
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


async def test_concentration_cap_blocks_tier_1_adds(client: AsyncClient) -> None:
    """Score 87 with concentration_cap_active=true → adds_permitted is False."""
    response = await client.get(
        "/api/v1/position-sizing/AAOI?base_score=87&concentration_cap_active=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "TIER_1"
    assert data["adds_permitted"] is False
    """Ticker supplied in lower-case is normalised before processing."""
    response = await client.get("/api/v1/position-sizing/aaoi?base_score=63")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAOI"
