"""Unit tests for Framework 4 — Tranche Sizing service.

Framework 4 maps three external signals to four cash-deployment tranches (T1–T4).

Inputs
------
initial_catalyst : "yes" | "no"   — has a confirmed entry catalyst fired?
regime_rule      : str             — the Framework 2 rule already held by the UI
                                     ("CRISIS" | "CAUTION" | "CLEAR" | "NORMAL")
iran_resolution  : str | None      — geopolitical resolution signal

Output tranche values
---------------------
T1  "10-15% of available cash"   when initial_catalyst == yes,  else "Blocked"
T2  "20-25% of available cash"   when regime_rule == CAUTION,   else "Blocked"
T3  "30-40% of available cash"   when regime_rule == CLEAR,     else "Blocked"
T4  "Remaining cash to floor"    when iran_resolution confirmed, else "Blocked"
"""

from __future__ import annotations

import pytest

from atlas.services.tranche_sizing_service import (
    _BLOCKED,
    _T1_VALUE,
    _T2_VALUE,
    _T3_VALUE,
    _T4_VALUE,
    TrancheSizingResponse,
    _compute_t1,
    _compute_t2,
    _compute_t3,
    _compute_t4,
    compute_tranche_sizing,
)


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
# _compute_t2 — CAUTION regime gate
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
# _compute_t3 — CLEAR regime gate
# ---------------------------------------------------------------------------


class TestComputeT3:
    def test_clear_returns_t3_value(self) -> None:
        assert _compute_t3("CLEAR") == _T3_VALUE

    def test_clear_lowercase_returns_t3_value(self) -> None:
        assert _compute_t3("clear") == _T3_VALUE

    def test_clear_mixed_case_returns_t3_value(self) -> None:
        assert _compute_t3("Clear") == _T3_VALUE

    def test_caution_returns_blocked(self) -> None:
        assert _compute_t3("CAUTION") == _BLOCKED

    def test_crisis_returns_blocked(self) -> None:
        assert _compute_t3("CRISIS") == _BLOCKED

    def test_normal_returns_blocked(self) -> None:
        assert _compute_t3("NORMAL") == _BLOCKED

    def test_empty_string_returns_blocked(self) -> None:
        assert _compute_t3("") == _BLOCKED


# ---------------------------------------------------------------------------
# _compute_t4 — Iran resolution gate
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
# compute_tranche_sizing — full integration of helpers
# ---------------------------------------------------------------------------


class TestComputeTrancheSizing:
    def test_returns_tranche_sizing_response(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CAUTION",
            iran_resolution="confirmed",
        )
        assert isinstance(result, TrancheSizingResponse)

    def test_ticker_normalised_to_uppercase(self) -> None:
        result = compute_tranche_sizing(
            ticker="aaoi",
            initial_catalyst="no",
            regime_rule="NORMAL",
        )
        assert result.ticker == "AAOI"

    def test_ticker_stripped_of_whitespace(self) -> None:
        result = compute_tranche_sizing(
            ticker=" AAOI ",
            initial_catalyst="no",
            regime_rule="NORMAL",
        )
        assert result.ticker == "AAOI"

    def test_all_blocked_when_no_catalyst_normal_regime_no_resolution(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            iran_resolution=None,
        )
        assert result.t1 == _BLOCKED
        assert result.t2 == _BLOCKED
        assert result.t3 == _BLOCKED
        assert result.t4 == _BLOCKED

    def test_all_active_when_all_conditions_met(self) -> None:
        # Caution → T2 active; Clear → T3 active...
        # but CAUTION and CLEAR are mutually exclusive so test both separately.
        # Here test the maximum possible combination: yes + CAUTION + confirmed.
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CAUTION",
            iran_resolution="confirmed",
        )
        assert result.t1 == _T1_VALUE
        assert result.t2 == _T2_VALUE
        assert result.t3 == _BLOCKED   # CAUTION != CLEAR
        assert result.t4 == _T4_VALUE

    def test_clear_regime_activates_t3_not_t2(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="yes",
            regime_rule="CLEAR",
            iran_resolution="confirmed",
        )
        assert result.t2 == _BLOCKED   # CLEAR != CAUTION
        assert result.t3 == _T3_VALUE

    def test_default_regime_rule_is_normal(self) -> None:
        """When regime_rule is omitted the default must not unblock T2 or T3."""
        result = compute_tranche_sizing(ticker="AAOI", initial_catalyst="no")
        assert result.t2 == _BLOCKED
        assert result.t3 == _BLOCKED

    def test_t1_value_string(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI", initial_catalyst="yes", regime_rule="NORMAL"
        )
        assert result.t1 == "10-15% of available cash"

    def test_t2_value_string(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI", initial_catalyst="no", regime_rule="CAUTION"
        )
        assert result.t2 == "20-25% of available cash"

    def test_t3_value_string(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI", initial_catalyst="no", regime_rule="CLEAR"
        )
        assert result.t3 == "30-40% of available cash"

    def test_t4_value_string(self) -> None:
        result = compute_tranche_sizing(
            ticker="AAOI",
            initial_catalyst="no",
            regime_rule="NORMAL",
            iran_resolution="confirmed",
        )
        assert result.t4 == "Remaining cash to floor"
