"""Integration tests for GET /api/v1/framework14/{ticker}.

Tests exercise the full HTTP request/response cycle.
Position weight is always passed via position_weight_override
(live DB not required for integration tests).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_response_contains_all_fields(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/MRVL?position_weight_override=0.034"
    )
    assert response.status_code == 200
    data = response.json()
    required = {
        "ticker",
        "position_weight_pct",
        "nav_dollars",
        "position_dollars",
        "sizing_tier",
        "target_weight_min",
        "target_weight_max",
        "concentration_status",
        "cap_active",
        "soft_cap_breached",
        "hard_review_triggered",
        "grandfathered",
        "grandfathered_expires_at",
        "grandfathered_expiry_near",
        "score_display_cap",
        "cluster",
        "cluster_weight_pct",
        "cluster_status",
        "cluster_yellow_threshold",
        "cluster_red_threshold",
        "adds_permitted",
        "trim_recommended",
        "message",
    }
    assert required.issubset(set(data.keys()))


# ---------------------------------------------------------------------------
# Test 1: MU at 13.6%
# ---------------------------------------------------------------------------


async def test_mu_at_13_6_pct(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/MU?position_weight_override=0.136&cluster_weight_override=0.25"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["concentration_status"] == "GRANDFATHERED"
    assert data["soft_cap_breached"] is True
    assert data["hard_review_triggered"] is True
    assert data["grandfathered"] is True
    assert data["grandfathered_expires_at"] == pytest.approx(0.170)
    assert data["cap_active"] is True
    assert data["adds_permitted"] is False
    assert data["score_display_cap"] == 85
    assert data["cluster"] == "AI Memory"
    assert data["trim_recommended"] is True


# ---------------------------------------------------------------------------
# Test 2: MRVL at 3.4%
# ---------------------------------------------------------------------------


async def test_mrvl_at_3_4_pct(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/MRVL?position_weight_override=0.034&cluster_weight_override=0.08"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["concentration_status"] == "NORMAL"
    assert data["soft_cap_breached"] is False
    assert data["grandfathered"] is False
    assert data["cap_active"] is False
    assert data["adds_permitted"] is True
    assert data["score_display_cap"] is None


# ---------------------------------------------------------------------------
# Test 3: NBIS at 4.3%
# ---------------------------------------------------------------------------


async def test_nbis_at_4_3_pct(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/NBIS?position_weight_override=0.043&cluster_weight_override=0.10"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["concentration_status"] == "NORMAL"
    assert data["soft_cap_breached"] is False
    assert data["cap_active"] is False
    assert data["adds_permitted"] is True
    assert data["cluster"] == "AI Infrastructure"


# ---------------------------------------------------------------------------
# Test 4: COHR at 9.5%
# ---------------------------------------------------------------------------


async def test_cohr_at_9_5_pct(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/COHR?position_weight_override=0.095&cluster_weight_override=0.24"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["concentration_status"] == "GRANDFATHERED"
    assert data["soft_cap_breached"] is True
    assert data["grandfathered"] is True
    assert data["grandfathered_expires_at"] == pytest.approx(0.119)
    assert data["cap_active"] is True
    assert data["adds_permitted"] is False


# ---------------------------------------------------------------------------
# Test 5: AI Optics cluster at 31% — red zone
# ---------------------------------------------------------------------------


async def test_ai_optics_cluster_red_zone(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/COHR?position_weight_override=0.095&cluster_weight_override=0.31"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cluster_status"] == "RED_ZONE"
    assert data["trim_recommended"] is True


# ---------------------------------------------------------------------------
# Test 6: AI Memory cluster at 23% — yellow zone
# ---------------------------------------------------------------------------


async def test_ai_memory_cluster_yellow_zone(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/MU?position_weight_override=0.136&cluster_weight_override=0.23"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cluster_status"] == "YELLOW_ZONE"


# ---------------------------------------------------------------------------
# Test 7: exactly 8.0% triggers soft cap
# ---------------------------------------------------------------------------


async def test_exactly_8_pct_triggers_cap(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/MRVL?position_weight_override=0.08&cluster_weight_override=0.08"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["soft_cap_breached"] is True
    assert data["cap_active"] is True
    assert data["adds_permitted"] is False


# ---------------------------------------------------------------------------
# Test 8: 7.9% does not trigger cap
# ---------------------------------------------------------------------------


async def test_7_9_pct_no_cap(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/MRVL?position_weight_override=0.079&cluster_weight_override=0.05"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["soft_cap_breached"] is False
    assert data["cap_active"] is False
    assert data["adds_permitted"] is True


# ---------------------------------------------------------------------------
# Ticker normalisation
# ---------------------------------------------------------------------------


async def test_ticker_normalised_to_uppercase(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/mrvl?position_weight_override=0.034&cluster_weight_override=0.05"
    )
    assert response.status_code == 200
    assert response.json()["ticker"] == "MRVL"


async def test_missing_ticker_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/%20?position_weight_override=0.034"
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Cluster endpoints
# ---------------------------------------------------------------------------


async def test_cluster_endpoint_returns_cluster_weight(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/cluster/AI%20Memory?cluster_weight_override=0.23"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cluster"] == "AI Memory"
    assert "cluster_weight_pct" in data
    assert "cluster_status" in data
    assert "tickers" in data


async def test_cluster_endpoint_unknown_cluster_returns_404(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/framework14/cluster/UNKNOWN_CLUSTER"
    )
    assert response.status_code == 404
