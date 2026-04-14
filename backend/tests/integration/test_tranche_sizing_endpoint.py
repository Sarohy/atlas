"""Integration tests for GET /api/v1/tranche-sizing/{ticker}.

These tests exercise the full request/response cycle using the ASGI test
client — no live external services are called.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Validation — required params
# ---------------------------------------------------------------------------


async def test_missing_initial_catalyst_returns_422(client: AsyncClient) -> None:
    """initial_catalyst is required — omitting it must return 422."""
    response = await client.get("/api/v1/tranche-sizing/AAOI")
    assert response.status_code == 422


async def test_invalid_initial_catalyst_returns_422(client: AsyncClient) -> None:
    """initial_catalyst must be 'yes' or 'no'."""
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=maybe")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# T1 — initial catalyst gate
# ---------------------------------------------------------------------------


async def test_t1_active_when_catalyst_yes(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=yes")
    assert response.status_code == 200
    assert response.json()["t1"] == "10-15% of available cash"


async def test_t1_blocked_when_catalyst_no(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=no")
    assert response.status_code == 200
    assert response.json()["t1"] == "Blocked"


async def test_t1_case_insensitive(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=YES")
    assert response.status_code == 200
    assert response.json()["t1"] == "10-15% of available cash"


# ---------------------------------------------------------------------------
# T2 — CAUTION regime gate
# ---------------------------------------------------------------------------


async def test_t2_active_when_regime_caution(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&regime_rule=CAUTION"
    )
    assert response.status_code == 200
    assert response.json()["t2"] == "20-25% of available cash"


async def test_t2_blocked_when_regime_clear(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&regime_rule=CLEAR"
    )
    assert response.status_code == 200
    assert response.json()["t2"] == "Blocked"


async def test_t2_blocked_when_regime_not_provided(client: AsyncClient) -> None:
    """Omitting regime_rule defaults to NORMAL — T2 must remain Blocked."""
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=no")
    assert response.status_code == 200
    assert response.json()["t2"] == "Blocked"


# ---------------------------------------------------------------------------
# T3 — CLEAR regime gate
# ---------------------------------------------------------------------------


async def test_t3_active_when_regime_clear(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&regime_rule=CLEAR"
    )
    assert response.status_code == 200
    assert response.json()["t3"] == "30-40% of available cash"


async def test_t3_blocked_when_regime_caution(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&regime_rule=CAUTION"
    )
    assert response.status_code == 200
    assert response.json()["t3"] == "Blocked"


async def test_t3_blocked_when_regime_not_provided(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=no")
    assert response.status_code == 200
    assert response.json()["t3"] == "Blocked"


# ---------------------------------------------------------------------------
# T4 — Iran resolution gate
# ---------------------------------------------------------------------------


async def test_t4_active_when_iran_confirmed(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&iran_resolution=confirmed"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Remaining cash to floor"


async def test_t4_blocked_when_iran_not_provided(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=no")
    assert response.status_code == 200
    assert response.json()["t4"] == "Blocked"


async def test_t4_blocked_when_iran_pending(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&iran_resolution=pending"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Blocked"


async def test_t4_case_insensitive(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&iran_resolution=CONFIRMED"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Remaining cash to floor"


# ---------------------------------------------------------------------------
# Response shape and ticker normalisation
# ---------------------------------------------------------------------------


async def test_response_contains_all_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=no")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"ticker", "t1", "t2", "t3", "t4"}


async def test_ticker_normalised_to_uppercase(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tranche-sizing/aaoi?initial_catalyst=no")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAOI"


async def test_all_active_scenario(client: AsyncClient) -> None:
    """Catalyst yes + CAUTION + confirmed — T1, T2, T4 active; T3 blocked."""
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=yes&regime_rule=CAUTION&iran_resolution=confirmed"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["t1"] == "10-15% of available cash"
    assert data["t2"] == "20-25% of available cash"
    assert data["t3"] == "Blocked"
    assert data["t4"] == "Remaining cash to floor"
