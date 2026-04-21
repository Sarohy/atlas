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

import pytest

from atlas.services.tranche_sizing_service import (
    _AND_GATE_THRESHOLD,
    _BLOCKED,
    _CAP_SUPPRESSION_MESSAGE,
    _CONCENTRATION_CAP_THRESHOLD,
    _T1_VALUE,
    _T2_VALUE,
    _T3_VALUE,
    _T4_VALUE,
    _compute_t1,
    _compute_t2,
    _compute_t3,
    _compute_t4,
    compute_tranche_sizing,
    get_and_gate_signals,
)
from atlas.schemas.tranche_sizing import TrancheSizingResponse


# ---------------------------------------------------------------------------
# Named constants — sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_concentration_cap_threshold_is_8_pct(self) -> None:
        assert _CONCENTRATION_CAP_THRESHOLD == pytest.approx(0.08)

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
# _compute_t2 — CAUTION regime gate (unchanged in v7.3.4)
# ---------------------------------------------------------------------------


class TestComputeT2:
    def test_caution_returns_t2_value(self) -> None:
        assert _compute_t2("CAUTION") == _T2_VALUE

    def test_caution_lowercase_returns_t2_value(self) -> None:
        assert _compute_t2("caution") == _T2_VALUE

    def test_caution_mixed_case_returns_t2_value(self) -> None:
        assert _compute_t2("Caution") == _T2_VALUE

    def test_crisis_returns_blocked(self) -> None:
        assert _compute_t2("CRISIS") == _BLOCKED

    def test_clear_returns_blocked(self) -> None:
        assert _compute_t2("CLEAR") == _BLOCKED

    def test_normal_returns_blocked(self) -> None:
        assert _compute_t2("NORMAL") == _BLOCKED

    def test_empty_string_returns_blocked(self) -> None:
        assert _compute_t2("") == _BLOCKED


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
            position_weight=0.03,
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
            position_weight=0.034,
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
            position_weight=0.051,
            signals_count_override=2,
        )
        assert result.and_gate_passed is False
        assert result.signals_confirmed == 2

    def test_t3_eligible_when_clear_and_gate_passes(self) -> None:
        """Test 2: CLEAR + 3/5 -> T3 eligible."""
        result = compute_tranche_sizing(
            ticker="MRVL",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.034,
            signals_count_override=3,
        )
        assert result.t3 == _T3_VALUE

    def test_t3_waiting_when_clear_but_gate_blocked(self) -> None:
        """Test 3: CLEAR + 2/5 -> T3 blocked (waiting for AND gate)."""
        result = compute_tranche_sizing(
            ticker="LITE",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.051,
            signals_count_override=2,
        )
        assert result.t3 == _BLOCKED

    def test_t3_blocked_with_caution_even_if_5_signals(self) -> None:
        """AND gate alone is not enough - regime must be CLEAR."""
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.03,
            signals_count_override=5,
        )
        assert result.t3 == _BLOCKED

    def test_and_gate_passes_with_4_of_5_signals(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
            signals_count_override=4,
        )
        assert result.and_gate_passed is True

    def test_and_gate_passes_with_5_of_5_signals(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CLEAR",
            position_weight=0.03,
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
            position_weight=0.03,
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
            position_weight=0.03,
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
            position_weight=0.03,
        )
        assert result.message is None

    def test_tranche_display_true_when_cap_not_active(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.03,
        )
        assert result.tranche_display is True

    def test_t1_blocked_when_no_catalyst(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            position_weight=0.03,
        )
        assert result.t1 == _BLOCKED

    def test_t2_active_with_caution_regime(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="CAUTION",
            position_weight=0.03,
        )
        assert result.t2 == _T2_VALUE

    def test_t4_active_when_iran_confirmed(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            iran_resolution="confirmed",
            position_weight=0.03,
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
