"""Unit tests for Framework 4 - Tranche Sizing service (v7.3.4).

Framework 4 maps three external signals to four cash-deployment tranches (T1-T4).
v7.3.4 changes:
  - T3 now requires CLEAR regime AND Framework 29 AND gate (3/5 signals).
  - All tranches suppressed when Framework 14 concentration cap is active (>=8% NAV).

Inputs
------
initial_catalyst       : "yes" | "no"   - has a confirmed entry catalyst fired?
regime_rule            : str             - the Framework 2 rule held by the UI
iran_resolution        : str | None      - geopolitical resolution signal
position_weight        : float           - current position weight as fraction of NAV
signals_count_override : int | None      - override AND gate count for testing

Output tranche values
---------------------
T1  "10-15% of available cash"   when initial_catalyst == yes,  else "Blocked"
T2  "20-25% of available cash"   when regime_rule == CAUTION,   else "Blocked"
T3  "30-40% of available cash"   when CLEAR AND and_gate_passed else "Blocked"
T4  "Remaining cash to floor"    when iran_resolution confirmed, else "Blocked"
All tranches None when cap_active == True.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.schemas.tranche_sizing import TrancheSizingResponse
from atlas.services.tranche_sizing_service import (
    _AND_GATE_THRESHOLD,
    _BLOCKED,
    _CAP_SUPPRESSION_MESSAGE,
    _CONCENTRATION_CAP_THRESHOLD,
    _T1_VALUE,
    _T2_BRENT_THRESHOLD,
    _T2_VALUE,
    _T3_VALUE,
    _T4_VALUE,
    _compute_t1,
    _compute_t2,
    _compute_t3,
    _compute_t4,
    _set_and_gate_signals,
    compute_tranche_sizing,
    fire_t2_tranche,
    fire_t3_tranche,
    get_and_gate_signals,
    get_position_weight,
    reset_t1_fired_store,
    reset_t2_fired_store,
    reset_t3_fired_store,
)

# ---------------------------------------------------------------------------
# Named constants — sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_concentration_cap_threshold_is_8_pct(self) -> None:
        assert pytest.approx(0.08) == _CONCENTRATION_CAP_THRESHOLD

    def test_and_gate_threshold_is_3(self) -> None:
        assert _AND_GATE_THRESHOLD == 3

    def test_cap_suppression_message_present(self) -> None:
        assert "concentration cap" in _CAP_SUPPRESSION_MESSAGE.lower()


# ---------------------------------------------------------------------------
# get_and_gate_signals — Framework 29 stub interface
# ---------------------------------------------------------------------------


class TestGetAndGateSignals:
    def test_unknown_ticker_returns_five_false_signals(self) -> None:
        signals = get_and_gate_signals("UNKNOWN_XYZ")
        assert len(signals) == 5
        assert all(s is False for s in signals)

    def test_returns_five_elements_for_any_ticker(self) -> None:
        signals = get_and_gate_signals("AAPL")
        assert len(signals) == 5


# ---------------------------------------------------------------------------
# _compute_t1 — initial catalyst gate
# ---------------------------------------------------------------------------


class TestComputeT1:
    def test_yes_returns_t1_value(self) -> None:
        assert _compute_t1("yes") == _T1_VALUE

    def test_yes_uppercase_returns_t1_value(self) -> None:
        assert _compute_t1("YES") == _T1_VALUE

    def test_yes_mixed_case_returns_t1_value(self) -> None:
        assert _compute_t1("Yes") == _T1_VALUE

    def test_no_returns_blocked(self) -> None:
        assert _compute_t1("no") == _BLOCKED

    def test_no_uppercase_returns_blocked(self) -> None:
        assert _compute_t1("NO") == _BLOCKED

    def test_arbitrary_string_returns_blocked(self) -> None:
        assert _compute_t1("maybe") == _BLOCKED

    def test_empty_string_returns_blocked(self) -> None:
        assert _compute_t1("") == _BLOCKED


# ---------------------------------------------------------------------------
# _compute_t2 — Brent price gate (T2 unlocks when Brent < $110)
# ---------------------------------------------------------------------------


class TestComputeT2:
    def test_brent_below_110_returns_t2_value(self) -> None:
        assert _compute_t2(92.40) == _T2_VALUE

    def test_brent_at_109_99_returns_t2_value(self) -> None:
        assert _compute_t2(109.99) == _T2_VALUE

    def test_brent_at_threshold_returns_blocked(self) -> None:
        """Exactly $110 does not trigger T2 — must be strictly below."""
        assert _compute_t2(_T2_BRENT_THRESHOLD) == _BLOCKED

    def test_brent_above_110_returns_blocked(self) -> None:
        assert _compute_t2(115.0) == _BLOCKED

    def test_none_returns_blocked(self) -> None:
        """No brent data available → T2 blocked."""
        assert _compute_t2(None) == _BLOCKED


# ---------------------------------------------------------------------------
# _compute_t3 — v7.3.4: CLEAR + AND gate required
# ---------------------------------------------------------------------------


class TestComputeT3:
    def test_clear_with_gate_passed_returns_t3_value(self) -> None:
        assert _compute_t3("CLEAR", and_gate_passed=True) == _T3_VALUE

    def test_clear_lowercase_with_gate_passed_returns_t3_value(self) -> None:
        assert _compute_t3("clear", and_gate_passed=True) == _T3_VALUE

    def test_clear_with_gate_blocked_returns_blocked(self) -> None:
        """CLEAR alone is not sufficient in v7.3.4 — AND gate must also pass."""
        assert _compute_t3("CLEAR", and_gate_passed=False) == _BLOCKED

    def test_caution_with_gate_passed_returns_blocked(self) -> None:
        """AND gate alone is not sufficient — regime must be CLEAR."""
        assert _compute_t3("CAUTION", and_gate_passed=True) == _BLOCKED

    def test_caution_with_gate_blocked_returns_blocked(self) -> None:
        assert _compute_t3("CAUTION", and_gate_passed=False) == _BLOCKED

    def test_crisis_returns_blocked(self) -> None:
        assert _compute_t3("CRISIS", and_gate_passed=True) == _BLOCKED

    def test_normal_returns_blocked(self) -> None:
        assert _compute_t3("NORMAL", and_gate_passed=True) == _BLOCKED

    def test_empty_string_returns_blocked(self) -> None:
        assert _compute_t3("", and_gate_passed=True) == _BLOCKED


# ---------------------------------------------------------------------------
# _compute_t4 — Iran resolution gate (unchanged in v7.3.4)
# ---------------------------------------------------------------------------


class TestComputeT4:
    def test_confirmed_returns_t4_value(self) -> None:
        assert _compute_t4("confirmed") == _T4_VALUE

    def test_confirmed_uppercase_returns_t4_value(self) -> None:
        assert _compute_t4("CONFIRMED") == _T4_VALUE

    def test_confirmed_mixed_case_returns_t4_value(self) -> None:
        assert _compute_t4("Confirmed") == _T4_VALUE

    def test_none_returns_blocked(self) -> None:
        assert _compute_t4(None) == _BLOCKED

    def test_pending_returns_blocked(self) -> None:
        assert _compute_t4("pending") == _BLOCKED

    def test_empty_string_returns_blocked(self) -> None:
        assert _compute_t4("") == _BLOCKED

    def test_arbitrary_string_returns_blocked(self) -> None:
        assert _compute_t4("unresolved") == _BLOCKED


# ---------------------------------------------------------------------------
# compute_tranche_sizing — concentration cap suppression (Change 3)
# ---------------------------------------------------------------------------


class TestConcentrationCapSuppression:
    def test_cap_active_at_exactly_8_pct(self) -> None:
        """Test 6: exactly 8.0% NAV triggers cap."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.08,
            signals_count_override=5,
        )
        assert result.cap_active is True

    def test_cap_inactive_below_8_pct(self) -> None:
        """Test 7: 7.9% NAV does not trigger cap."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.079,
            signals_count_override=5,
        )
        assert result.cap_active is False

    def test_cap_suppresses_tranche_display(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.09,
            signals_count_override=5,
        )
        assert result.tranche_display is False

    def test_cap_returns_none_for_all_tranches(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.09,
            signals_count_override=5,
        )
        assert result.t1 is None
        assert result.t2 is None
        assert result.t3 is None
        assert result.t4 is None

    def test_cap_returns_suppression_message(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.09,
        )
        assert result.message == _CAP_SUPPRESSION_MESSAGE

    def test_cap_active_when_position_weight_above_threshold(self) -> None:
        """Test 1: 13.6% NAV (above 8%) must be suppressed."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.136,
            signals_count_override=5,
        )
        assert result.cap_active is True
        assert result.tranche_display is False

    def test_cap_active_at_11_7_pct(self) -> None:
        """Test 5: 11.7% NAV (above 8%) must be suppressed."""
        result = compute_tranche_sizing(
            ticker="TSM",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.117,
            signals_count_override=5,
        )
        assert result.cap_active is True

    def test_position_weight_returned_in_response(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.05,
        )
        assert result.position_weight == pytest.approx(0.05)

    def test_cap_and_gate_fields_are_false_when_suppressed(self) -> None:
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.136,
        )
        assert result.and_gate_active is False
        assert result.and_gate_passed is False
        assert result.signals_confirmed == 0


# ---------------------------------------------------------------------------
# compute_tranche_sizing — AND gate logic (Change 1 + 2)
# ---------------------------------------------------------------------------


class TestAndGateLogic:
    def test_and_gate_active_only_when_clear(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=0,
        )
        assert result.and_gate_active is True

    def test_and_gate_inactive_when_caution(self) -> None:
        """Test 4: CAUTION regime - and_gate_active must be False."""
        result = compute_tranche_sizing(
            ticker="AVGO",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.034,
        )
        assert result.and_gate_active is False

    def test_and_gate_inactive_when_normal(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.03,
        )
        assert result.and_gate_active is False

    def test_and_gate_passes_with_3_of_5_signals(self) -> None:
        """Test 2: MRVL CLEAR + 3/5 confirmed -> and_gate_passed=True."""
        result = compute_tranche_sizing(
            ticker="MRVL",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MRVL 1% beta cap
            signals_count_override=3,
        )
        assert result.and_gate_passed is True
        assert result.signals_confirmed == 3

    def test_and_gate_blocked_with_2_of_5_signals(self) -> None:
        """Test 3: LITE CLEAR + 2/5 confirmed -> and_gate_passed=False."""
        result = compute_tranche_sizing(
            ticker="LITE",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.015,  # 1.5% NAV — below LITE 2.5% beta cap
            signals_count_override=2,
        )
        assert result.and_gate_passed is False
        assert result.signals_confirmed == 2

    def test_t3_eligible_when_clear_and_gate_passes(self) -> None:
        """Test 2: CLEAR + 3/5 + T1 fired -> T3 eligible."""
        result = compute_tranche_sizing(
            ticker="MRVL",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MRVL 1% beta cap
            signals_count_override=3,
            t1_fired_override=True,
        )
        assert result.t3 == _T3_VALUE

    def test_t3_waiting_when_clear_but_gate_blocked(self) -> None:
        """Test 3: CLEAR + 2/5 -> T3 blocked (waiting for AND gate)."""
        result = compute_tranche_sizing(
            ticker="LITE",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.015,  # 1.5% NAV — below LITE 2.5% beta cap
            signals_count_override=2,
        )
        assert result.t3 == _BLOCKED

    def test_t3_blocked_with_caution_even_if_5_signals(self) -> None:
        """AND gate alone is not enough - regime must be CLEAR."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=5,
        )
        assert result.t3 == _BLOCKED

    def test_and_gate_passes_with_4_of_5_signals(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=4,
        )
        assert result.and_gate_passed is True

    def test_and_gate_passes_with_5_of_5_signals(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=5,
        )
        assert result.and_gate_passed is True

    def test_signals_detail_has_5_entries(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=3,
        )
        assert len(result.signals_detail) == 5

    def test_signals_detail_first_3_confirmed_when_override_3(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=3,
        )
        for i, signal in enumerate(result.signals_detail):
            if i < 3:
                assert signal.confirmed is True
            else:
                assert signal.confirmed is False

    def test_signals_detail_empty_when_gate_not_active(self) -> None:
        """When regime is not CLEAR, signals_detail still has 5 items but all False."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.03,
        )
        assert len(result.signals_detail) == 5
        assert all(s.confirmed is False for s in result.signals_detail)

    def test_signal_detail_has_signal_index(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=2,
        )
        indices = [s.signal_index for s in result.signals_detail]
        assert indices == [1, 2, 3, 4, 5]

    def test_signal_detail_has_name(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=2,
        )
        for signal in result.signals_detail:
            assert len(signal.name) > 0

    def test_leaps_clear_gate_blocked_returns_gate_not_passed(self) -> None:
        """Test 8: LEAPS >$10K blocked when CLEAR but only 2/5 signals."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=2,
        )
        assert result.and_gate_passed is False
        assert result.signals_confirmed == 2


# ---------------------------------------------------------------------------
# compute_tranche_sizing — complete response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_returns_tranche_sizing_response(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CAUTION",
            iran_resolution="confirmed",
            position_weight=0.03,
        )
        assert isinstance(result, TrancheSizingResponse)

    def test_ticker_normalised_to_uppercase(self) -> None:
        result = compute_tranche_sizing(
            ticker="aaoi",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.0,
        )
        assert result.ticker == "AAOI"

    def test_ticker_stripped_of_whitespace(self) -> None:
        result = compute_tranche_sizing(
            ticker=" AAOI ",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.0,
        )
        assert result.ticker == "AAOI"

    def test_no_message_when_cap_not_active(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
        )
        assert result.message is None

    def test_tranche_display_true_when_cap_not_active(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
        )
        assert result.tranche_display is True

    def test_t1_blocked_when_no_catalyst(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
        )
        assert result.t1 == _BLOCKED

    def test_t2_active_with_brent_below_110(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            t1_fired_override=True,
            brent_price=92.40,
        )
        assert result.t2 == _T2_VALUE

    def test_t4_active_when_iran_confirmed(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            iran_resolution="confirmed",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            t1_fired_override=True,
        )
        assert result.t4 == _T4_VALUE

    def test_default_regime_rule_is_normal(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            position_weight=0.0,
        )
        assert result.t2 == _BLOCKED
        assert result.t3 == _BLOCKED


# ---------------------------------------------------------------------------
# compute_tranche_sizing — sequential gate (T1 must fire before T2/T3/T4)
# ---------------------------------------------------------------------------


class TestSequentialGate:
    """Tests for the T1 sequential gate: T2/T3/T4 are blocked until T1 fires.

    Bug being fixed: T2 was eligible when regime=CAUTION even with T1 not fired.
    Spec reference: Framework 4 v7.4 — T1 must fire before T2/T3/T4 can deploy.
    """

    def test_t2_blocked_when_t1_not_fired_in_caution_regime(self) -> None:
        """Test 1: CAUTION regime with T1 not fired — T2 must be BLOCKED."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            t1_fired_override=False,
        )
        assert result.t2 == _BLOCKED
        assert result.t1_fired is False

    def test_t2_eligible_when_t1_fired_and_brent_below_110(self) -> None:
        """Test 2: T2 becomes eligible once T1 has fired and Brent is below $110."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            t1_fired_override=True,
            brent_price=92.40,
        )
        assert result.t2 == _T2_VALUE
        assert result.t1_fired is True

    def test_all_gated_blocked_when_t1_not_fired_clear_regime_and_gate_passes(self) -> None:
        """Test 3: CLEAR + AND gate 3/5 — all T2/T3/T4 still BLOCKED if T1 not fired."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            signals_count_override=3,
            t1_fired_override=False,
        )
        assert result.t2 == _BLOCKED
        assert result.t3 == _BLOCKED
        assert result.t4 == _BLOCKED
        assert result.t1_fired is False

    def test_t1_fires_and_persists_when_catalyst_yes(self) -> None:
        """Setting initial_catalyst='yes' persists T1 to the store."""
        # First call fires T1
        compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="yes",
            regime_rule="CAUTION",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            brent_price=92.40,
        )
        # Second call with catalyst='no' still sees T1 as fired (from store)
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            brent_price=92.40,
        )
        assert result.t1_fired is True
        assert result.t2 == _T2_VALUE

    def test_and_gate_still_computed_when_t1_not_fired(self) -> None:
        """AND gate state is still computed even when T1 has not fired."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            signals_count_override=3,
            t1_fired_override=False,
        )
        assert result.and_gate_active is True
        assert result.and_gate_passed is True
        assert result.signals_confirmed == 3


# ---------------------------------------------------------------------------
# compute_tranche_sizing — signal auto-detection (signal 2 and signal 5)
# ---------------------------------------------------------------------------


class TestSignalAutoDetection:
    def test_signal_2_confirmed_when_brent_consecutive_gte_2(self) -> None:
        """Signal 2: Brent second consecutive close below $95 — auto-detected."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            brent_consecutive_below_95_count=2,
        )
        assert result.signals_detail[1].confirmed is True

    def test_signal_2_pending_when_brent_consecutive_is_1(self) -> None:
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_consecutive_below_95_count=1,
        )
        assert result.signals_detail[1].confirmed is False

    def test_signal_2_pending_when_brent_consecutive_is_0(self) -> None:
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_consecutive_below_95_count=0,
        )
        assert result.signals_detail[1].confirmed is False

    def test_signal_5_confirmed_when_geo_resolved(self) -> None:
        """Signal 5: geo param RESOLVED triggers confirmation directly."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            geopolitical_state="RESOLVED",
        )
        assert result.signals_detail[4].confirmed is True

    def test_signal_5_pending_when_geo_active_risk(self) -> None:
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            geopolitical_state="ACTIVE_RISK",
        )
        assert result.signals_detail[4].confirmed is False

    def test_signal_5_pending_when_geo_none(self) -> None:
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            geopolitical_state="NONE",
        )
        assert result.signals_detail[4].confirmed is False

    def test_mu_test_case_2_of_5_signals_confirmed(self) -> None:
        """MU: brent_consecutive=2, geo=RESOLVED → signals 2 and 5 auto-detected."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            brent_consecutive_below_95_count=2,
            geopolitical_state="RESOLVED",
        )
        assert result.signals_confirmed == 2
        assert result.signals_detail[1].confirmed is True  # signal 2
        assert result.signals_detail[4].confirmed is True  # signal 5
        assert result.and_gate_passed is False  # 2 < 3 threshold

    def test_signals_count_override_bypasses_auto_detection(self) -> None:
        """signals_count_override takes precedence over auto-detection."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below MU 1.0% beta cap (beta 2.42)
            brent_consecutive_below_95_count=2,
            geopolitical_state="RESOLVED",
            signals_count_override=4,
        )
        assert result.signals_confirmed == 4


# ---------------------------------------------------------------------------
# T2 auto-trigger: pending + fired state (Framework 17)
# ---------------------------------------------------------------------------


class TestT2AutoTrigger:
    """T2 is price-based and auto-triggered.

    When T1 has fired AND Brent < $110 the system sets t2_pending=True and
    shows the operator a confirmation modal.  Only when the operator confirms
    (fire_t2_tranche) does t2_fired become True.
    """

    def setup_method(self) -> None:
        reset_t1_fired_store()
        reset_t2_fired_store()

    def teardown_method(self) -> None:
        reset_t1_fired_store()
        reset_t2_fired_store()

    def test_t2_pending_true_when_t1_fired_and_brent_below_110(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            brent_price=92.40,
        )
        assert result.t1_fired is True
        assert result.t2_pending is True
        assert result.t2_fired is False

    def test_t2_pending_false_when_t1_not_fired(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_price=92.40,
        )
        assert result.t1_fired is False
        assert result.t2_pending is False

    def test_t2_pending_false_when_brent_above_110(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_price=115.0,
        )
        assert result.t2_pending is False

    def test_t2_pending_false_when_brent_none(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_price=None,
        )
        assert result.t2_pending is False

    def test_t2_fired_false_before_confirm(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_price=92.40,
        )
        assert result.t2_fired is False

    def test_t2_fired_true_after_fire_t2_tranche(self) -> None:
        # Precondition: T1 must fire first.
        compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            brent_price=92.40,
        )
        fire_t2_tranche("AAOI")
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            brent_price=92.40,
        )
        assert result.t2_fired is True
        assert result.t2_pending is False

    def test_t2_pending_false_once_fired(self) -> None:
        fire_t2_tranche("AAOI")
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            brent_price=92.40,
        )
        assert result.t2_pending is False
        assert result.t2_fired is True

    def test_t2_fired_is_ticker_scoped(self) -> None:
        fire_t2_tranche("AAOI")
        result_other = compute_tranche_sizing(
            ticker="AAPL",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            brent_price=92.40,
        )
        assert result_other.t2_fired is False


# ---------------------------------------------------------------------------
# T3 auto-trigger: pending + fired state (Framework 17)
# ---------------------------------------------------------------------------


class TestT3AutoTrigger:
    """T3 is auto-triggered when CLEAR regime AND AND gate passes.

    The operator confirms the deployment order; they do not decide the trigger.
    """

    def setup_method(self) -> None:
        reset_t1_fired_store()
        reset_t3_fired_store()

    def teardown_method(self) -> None:
        reset_t1_fired_store()
        reset_t3_fired_store()

    def test_t3_pending_true_when_clear_and_gate_passed_and_t1_fired(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=3,
        )
        assert result.and_gate_passed is True
        assert result.t1_fired is True
        assert result.t3_pending is True
        assert result.t3_fired is False

    def test_t3_pending_false_when_and_gate_not_passed(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=2,
        )
        assert result.and_gate_passed is False
        assert result.t3_pending is False

    def test_t3_pending_false_when_t1_not_fired(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=3,
        )
        assert result.t1_fired is False
        assert result.t3_pending is False

    def test_t3_pending_false_when_regime_not_clear(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CAUTION",
            position_weight=0.03,
            signals_count_override=3,
        )
        assert result.t3_pending is False

    def test_t3_fired_false_before_confirm(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=3,
        )
        assert result.t3_fired is False

    def test_t3_fired_true_after_fire_t3_tranche(self) -> None:
        compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=3,
        )
        fire_t3_tranche("AAOI")
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.005,  # 0.5% NAV — below AAOI 1% beta cap
            signals_count_override=3,
        )
        assert result.t3_fired is True
        assert result.t3_pending is False

    def test_t3_fired_is_ticker_scoped(self) -> None:
        fire_t3_tranche("AAOI")
        result_other = compute_tranche_sizing(
            ticker="AAPL",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=3,
        )
        assert result_other.t3_fired is False


# ---------------------------------------------------------------------------
# get_position_weight — async DB helper
# ---------------------------------------------------------------------------


def _make_session(
    position_value: Decimal | None,
    all_values: list[Decimal],
    cash: Decimal | None,
) -> AsyncMock:
    """Build a minimal AsyncSession mock for get_position_weight."""
    session = AsyncMock()

    # First execute: single ticker position_value
    ticker_result = MagicMock()
    ticker_result.scalar_one_or_none.return_value = position_value

    # Second execute: all position values
    all_result = MagicMock()
    all_result.scalars.return_value.all.return_value = all_values

    session.execute.side_effect = [ticker_result, all_result]

    # session.get: PortfolioConfig
    if cash is not None:
        config = MagicMock()
        config.cash_balance = cash
    else:
        config = None
    session.get = AsyncMock(return_value=config)

    return session


class TestGetPositionWeight:
    @pytest.mark.asyncio
    async def test_returns_zero_when_ticker_not_in_portfolio(self) -> None:
        session = _make_session(position_value=None, all_values=[], cash=Decimal("10000"))
        result = await get_position_weight("AAPL", session)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_returns_correct_fraction(self) -> None:
        # AAPL worth 2000, total invested 8000, cash 2000 => NAV 10000, weight 0.2
        session = _make_session(
            position_value=Decimal("2000"),
            all_values=[Decimal("2000"), Decimal("6000")],
            cash=Decimal("2000"),
        )
        result = await get_position_weight("AAPL", session)
        assert abs(result - 0.2) < 1e-9

    @pytest.mark.asyncio
    async def test_returns_zero_when_total_nav_is_zero(self) -> None:
        session = _make_session(
            position_value=Decimal("0"),
            all_values=[Decimal("0")],
            cash=Decimal("0"),
        )
        result = await get_position_weight("AAPL", session)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_handles_none_config(self) -> None:
        # cash=None means PortfolioConfig row missing → cash defaults to 0
        session = _make_session(
            position_value=Decimal("1000"),
            all_values=[Decimal("1000")],
            cash=None,
        )
        result = await get_position_weight("AAPL", session)
        assert abs(result - 1.0) < 1e-9


class TestSetAndGateSignals:
    def test_set_and_gate_signals_mutates_store(self) -> None:
        _set_and_gate_signals("TESTX", [True, False, True, False, True])
        signals = get_and_gate_signals("TESTX")
        assert signals == [True, False, True, False, True]


# ---------------------------------------------------------------------------
# Beta cap suppression — confirmed ticker regression (bug fix tests)
#
# All three tickers below were confirmed broken in production.
# Root cause: MU beta was 1.65 (cap 2.5%) — updated to 2.42 (cap 1.0%).
# AAOI and FN betas were already correct but tests validate the integration.
# ---------------------------------------------------------------------------


class TestBetaCapSuppressionRegression:
    """Test 1–4 from the beta cap suppression bug report.

    These four tests must ALL pass before the bug is considered fixed.
    Tests 1–3 confirm suppressed tickers; Test 4 confirms a clear ticker.
    """

    def test_mu_at_1_3pct_is_beta_capped(self) -> None:
        """Test 1: MU position 1.3% — beta 2.42 — cap 1.0% — must suppress."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.013,  # 1.3% NAV — above 1.0% cap (beta 2.42)
        )
        assert result.beta_cap_active is True
        assert result.tranche_display is False
        assert result.t1 is None
        assert result.t2 is None
        assert result.t3 is None
        assert result.t4 is None
        assert result.message is not None
        assert "beta cap" in result.message.lower()

    def test_fn_at_1_8pct_is_beta_capped(self) -> None:
        """Test 2: FN position 1.8% — beta 2.70 — cap 1.0% — must suppress."""
        result = compute_tranche_sizing(
            ticker="FN",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.018,  # 1.8% NAV — above 1.0% cap (beta 2.70)
        )
        assert result.beta_cap_active is True
        assert result.tranche_display is False
        assert result.t1 is None
        assert result.t2 is None
        assert result.t3 is None
        assert result.t4 is None

    def test_aaoi_at_4_4pct_is_beta_capped(self) -> None:
        """Test 3: AAOI position 4.4% — beta 4.03 — cap 1.0% — must suppress."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.044,  # 4.4% NAV — above 1.0% cap (beta 4.03)
        )
        assert result.beta_cap_active is True
        assert result.tranche_display is False
        assert result.t1 is None
        assert result.t2 is None
        assert result.t3 is None
        assert result.t4 is None

    def test_nem_at_5pct_below_caps_shows_tranches(self) -> None:
        """Test 4: NEM position 4.0% — beta 0.55 — no beta cap — tranches shown."""
        result = compute_tranche_sizing(
            ticker="NEM",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.04,  # 4.0% NAV — strictly below 5% beta-floor cap and 8% conc cap
        )
        assert result.beta_cap_active is False
        assert result.cap_active is False
        assert result.tranche_display is True

    def test_mu_beta_cap_message_contains_beta_and_cap_values(self) -> None:
        """Suppression message must include beta value and cap limit."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.013,
        )
        assert result.message is not None
        # Message must reference beta and cap limit percentage
        assert "2.42" in result.message
        assert "1.0" in result.message

    def test_mu_just_below_new_cap_shows_tranches(self) -> None:
        """MU at 0.9% (below new 1.0% cap with beta 2.42) must not suppress."""
        result = compute_tranche_sizing(
            ticker="MU",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.009,  # 0.9% NAV — just below new 1.0% cap
        )
        assert result.beta_cap_active is False
        assert result.tranche_display is True
