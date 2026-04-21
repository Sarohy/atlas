"""Integration tests for GET /api/v1/tranche-sizing/{ticker} (v7.3.4).

These tests exercise the full request/response cycle using the ASGI test
client - no live external services are called.

v7.3.4 changes:
  - position_weight_override query param for testing cap threshold
  - signals_count_override query param for testing AND gate scenarios
  - New response fields: cap_active, tranche_display, position_weight, message,
    and_gate_active, and_gate_passed, signals_confirmed, signals_detail
  - T3 now requires CLEAR + AND gate (3/5 signals); CLEAR alone is insufficient
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Validation - required params
# ---------------------------------------------------------------------------


async def test_missing_initial_catalyst_returns_422(client: AsyncClient) -> None:
    """initial_catalyst is required - omitting it must return 422."""
    response = await client.get("/api/v1/tranche-sizing/AAOI")
    assert response.status_code == 422


async def test_invalid_initial_catalyst_returns_422(client: AsyncClient) -> None:
    """initial_catalyst must be 'yes' or 'no'."""
    response = await client.get("/api/v1/tranche-sizing/AAOI?initial_catalyst=maybe")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Response shape - all new fields present
# ---------------------------------------------------------------------------


async def test_response_contains_all_v734_fields(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&position_weight_override=0.03"
    )
    assert response.status_code == 200
    data = response.json()
    required = {
        "ticker",
        "cap_active",
        "tranche_display",
        "position_weight",
        "message",
        "and_gate_active",
        "and_gate_passed",
        "signals_confirmed",
        "signals_detail",
        "t1",
        "t2",
        "t3",
        "t4",
    }
    assert required.issubset(set(data.keys()))


async def test_signals_detail_has_5_entries(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&position_weight_override=0.03"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["signals_detail"]) == 5


# ---------------------------------------------------------------------------
# T1 - initial catalyst gate (unchanged)
# ---------------------------------------------------------------------------


async def test_t1_active_when_catalyst_yes(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=yes&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t1"] == "10-15% of available cash"


async def test_t1_blocked_when_catalyst_no(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t1"] == "Blocked"


async def test_t1_case_insensitive(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=YES&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t1"] == "10-15% of available cash"


# ---------------------------------------------------------------------------
# T2 - CAUTION regime gate (unchanged)
# ---------------------------------------------------------------------------


async def test_t2_active_when_regime_caution(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&regime_rule=CAUTION&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t2"] == "20-25% of available cash"


async def test_t2_blocked_when_regime_clear(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&regime_rule=CLEAR&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t2"] == "Blocked"


async def test_t2_blocked_when_regime_not_provided(client: AsyncClient) -> None:
    """Omitting regime_rule defaults to NORMAL - T2 must remain Blocked."""
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t2"] == "Blocked"


# ---------------------------------------------------------------------------
# T3 - v7.3.4: CLEAR + AND gate required
# ---------------------------------------------------------------------------


async def test_t3_blocked_when_clear_but_no_gate_override(client: AsyncClient) -> None:
    """CLEAR alone is not enough in v7.3.4 - AND gate must pass (no override = 0/5)."""
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&regime_rule=CLEAR&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t3"] == "Blocked"


async def test_t3_active_when_clear_and_gate_passes(client: AsyncClient) -> None:
    """Test 2: CLEAR + 3/5 signals -> T3 eligible."""
    response = await client.get(
        "/api/v1/tranche-sizing/MRVL"
        "?initial_catalyst=no&regime_rule=CLEAR"
        "&position_weight_override=0.034&signals_count_override=3"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["t3"] == "30-40% of available cash"
    assert data["and_gate_passed"] is True
    assert data["signals_confirmed"] == 3


async def test_t3_blocked_when_clear_but_only_2_of_5(client: AsyncClient) -> None:
    """Test 3: CLEAR + 2/5 signals -> T3 blocked."""
    response = await client.get(
        "/api/v1/tranche-sizing/LITE"
        "?initial_catalyst=no&regime_rule=CLEAR"
        "&position_weight_override=0.051&signals_count_override=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["t3"] == "Blocked"
    assert data["and_gate_passed"] is False
    assert data["signals_confirmed"] == 2


async def test_t3_blocked_when_regime_caution(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&regime_rule=CAUTION&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t3"] == "Blocked"


# ---------------------------------------------------------------------------
# T4 - Iran resolution gate (unchanged)
# ---------------------------------------------------------------------------


async def test_t4_active_when_iran_confirmed(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&iran_resolution=confirmed&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Remaining cash to floor"


async def test_t4_blocked_when_iran_not_provided(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI?initial_catalyst=no&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Blocked"


async def test_t4_blocked_when_iran_pending(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&iran_resolution=pending&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Blocked"


async def test_t4_case_insensitive(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&iran_resolution=CONFIRMED&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["t4"] == "Remaining cash to floor"


# ---------------------------------------------------------------------------
# Concentration cap suppression (Change 3)
# ---------------------------------------------------------------------------


async def test_cap_active_at_exactly_8_pct(client: AsyncClient) -> None:
    """Test 6: exactly 8.0% NAV triggers cap."""
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=yes&regime_rule=CLEAR"
        "&position_weight_override=0.08&signals_count_override=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cap_active"] is True
    assert data["tranche_display"] is False


async def test_cap_inactive_at_7_9_pct(client: AsyncClient) -> None:
    """Test 7: 7.9% NAV does not trigger cap."""
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=yes&regime_rule=CLEAR"
        "&position_weight_override=0.079&signals_count_override=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cap_active"] is False
    assert data["tranche_display"] is True


async def test_cap_suppresses_all_tranches_to_null(client: AsyncClient) -> None:
    """Test 1 / Test 5: T1-T4 must be None (not Blocked) when cap active."""
    response = await client.get(
        "/api/v1/tranche-sizing/MU?initial_catalyst=yes&position_weight_override=0.136"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cap_active"] is True
    assert data["t1"] is None
    assert data["t2"] is None
    assert data["t3"] is None
    assert data["t4"] is None


async def test_cap_returns_suppression_message(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/TSM?initial_catalyst=no&position_weight_override=0.117"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cap_active"] is True
    assert data["message"] is not None
    assert "concentration cap" in data["message"].lower()


# ---------------------------------------------------------------------------
# AND gate status in response (Change 1 + 2)
# ---------------------------------------------------------------------------


async def test_and_gate_active_when_clear_regime(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=no&regime_rule=CLEAR"
        "&position_weight_override=0.03&signals_count_override=0"
    )
    assert response.status_code == 200
    assert response.json()["and_gate_active"] is True


async def test_and_gate_inactive_when_caution_regime(client: AsyncClient) -> None:
    """Test 4: AVGO at CAUTION - and_gate_active must be False."""
    response = await client.get(
        "/api/v1/tranche-sizing/AVGO"
        "?initial_catalyst=no&regime_rule=CAUTION&position_weight_override=0.034"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["and_gate_active"] is False


# ---------------------------------------------------------------------------
# Ticker normalisation
# ---------------------------------------------------------------------------


async def test_ticker_normalised_to_uppercase(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/tranche-sizing/aaoi?initial_catalyst=no&position_weight_override=0.03"
    )
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAOI"


# ---------------------------------------------------------------------------
# Legacy scenario: catalyst+CAUTION+iran - T1, T2, T4 active; T3 blocked
# ---------------------------------------------------------------------------


async def test_no_override_uses_db_weight_for_unknown_ticker(client: AsyncClient) -> None:
    """When position_weight_override is omitted, weight is fetched from the DB.

    A ticker not in the portfolio returns 0.0 NAV weight - cap is not active,
    and the response is a valid 200 with the correct shape.
    """
    response = await client.get(
        "/api/v1/tranche-sizing/ZZZTEST?initial_catalyst=no"
    )
    assert response.status_code == 200
    data = response.json()
    # ZZZTEST will never be in the portfolio - weight resolves to 0.0 from DB
    assert data["cap_active"] is False
    assert data["position_weight"] == pytest.approx(0.0)



    """Catalyst yes + CAUTION + confirmed - T1, T2, T4 active; T3 blocked."""
    response = await client.get(
        "/api/v1/tranche-sizing/AAOI"
        "?initial_catalyst=yes&regime_rule=CAUTION"
        "&iran_resolution=confirmed&position_weight_override=0.03"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["t1"] == "10-15% of available cash"
    assert data["t2"] == "20-25% of available cash"
    assert data["t3"] == "Blocked"
    assert data["t4"] == "Remaining cash to floor"
