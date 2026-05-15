"""Unit tests for framework33_service — LEAPS Entry Conditions V2.

Covers:
  - is_excluded_ticker: OTC/thin-option exclusion list
  - evaluate_condition_a: Calm Accumulation (20%+ drawdown + VIX 15-18)
  - evaluate_condition_b: Washout (25%+ sector drawdown + cap volume + VIX declining)
  - evaluate_condition_c: Bull Market Path (T1E ≥85 + dark pool bullish + options flow + no gap)
  - compute_per_name_size_pct: sizing rules with F30 drawdown gate
  - compute_f33_entry: overall condition routing (A OR B OR C qualifies)
"""

from __future__ import annotations

import pytest

from atlas.services.framework33_service import (
    ConditionAResult,
    ConditionBResult,
    ConditionCResult,
    F33EntryResult,
    compute_f33_entry,
    compute_per_name_size_pct,
    evaluate_condition_a,
    evaluate_condition_b,
    evaluate_condition_c,
    is_excluded_ticker,
)


# ---------------------------------------------------------------------------
# is_excluded_ticker
# ---------------------------------------------------------------------------


class TestIsExcludedTicker:
    def test_sive_excluded(self) -> None:
        assert is_excluded_ticker("SIVE") is True

    def test_iqe_excluded(self) -> None:
        assert is_excluded_ticker("IQE") is True

    def test_alrib_excluded(self) -> None:
        assert is_excluded_ticker("ALRIB") is True

    def test_shunsin_excluded(self) -> None:
        assert is_excluded_ticker("SHUNSIN") is True

    def test_poet_excluded(self) -> None:
        assert is_excluded_ticker("POET") is True

    def test_valid_ticker_not_excluded(self) -> None:
        assert is_excluded_ticker("MRVL") is False

    def test_case_insensitive(self) -> None:
        assert is_excluded_ticker("sive") is True

    def test_lite_not_excluded(self) -> None:
        assert is_excluded_ticker("LITE") is False

    def test_mu_not_excluded(self) -> None:
        assert is_excluded_ticker("MU") is False


# ---------------------------------------------------------------------------
# evaluate_condition_a — Calm Accumulation
# ---------------------------------------------------------------------------


class TestEvaluateConditionA:
    def test_confirmed_when_drawdown_20pct_and_vix_in_range(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
        )
        assert result.confirmed is True
        assert result.drawdown_qualifies is True
        assert result.vix_in_calm_range is True

    def test_not_met_when_drawdown_below_threshold(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=15.0,
            vix_current=16.5,
        )
        assert result.confirmed is False
        assert result.drawdown_qualifies is False

    def test_not_met_when_vix_above_range(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=25.0,
            vix_current=19.0,
        )
        assert result.confirmed is False
        assert result.vix_in_calm_range is False

    def test_not_met_when_vix_below_range(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=25.0,
            vix_current=14.9,
        )
        assert result.confirmed is False
        assert result.vix_in_calm_range is False

    def test_confirmed_at_exact_drawdown_boundary(self) -> None:
        # Exactly 20% drawdown qualifies
        result = evaluate_condition_a(
            drawdown_from_high_pct=20.0,
            vix_current=17.0,
        )
        assert result.confirmed is True

    def test_confirmed_at_exact_vix_lower_boundary(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=20.0,
            vix_current=15.0,
        )
        assert result.confirmed is True

    def test_confirmed_at_exact_vix_upper_boundary(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=20.0,
            vix_current=18.0,
        )
        assert result.confirmed is True

    def test_unavailable_when_drawdown_none(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=None,
            vix_current=16.0,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_unavailable_when_vix_none(self) -> None:
        result = evaluate_condition_a(
            drawdown_from_high_pct=25.0,
            vix_current=None,
        )
        assert result.confirmed is None
        assert result.data_missing is True


# ---------------------------------------------------------------------------
# evaluate_condition_b — Washout
# ---------------------------------------------------------------------------


class TestEvaluateConditionB:
    def test_confirmed_when_all_three_criteria_met(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is True
        assert result.sector_drawdown_qualifies is True
        assert result.capitulation_volume_confirmed is True
        assert result.vix_declining is True

    def test_not_met_when_sector_drawdown_below_threshold(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=20.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is False
        assert result.sector_drawdown_qualifies is False

    def test_not_met_when_capitulation_volume_not_confirmed(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=False,
            vix_elevated=True,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is False

    def test_not_met_when_vix_not_elevated(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=False,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is False

    def test_not_met_when_vix_still_climbing(self) -> None:
        # VIX elevated but NOT declining — fear still rising, not peaked
        result = evaluate_condition_b(
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=False,
        )
        assert result.confirmed is False
        assert result.vix_declining is False

    def test_confirmed_at_exact_sector_drawdown_boundary(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=25.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is True

    def test_unavailable_when_sector_drawdown_none(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=None,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_unavailable_when_vix_declining_none(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=None,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_unavailable_when_capitulation_volume_none(self) -> None:
        result = evaluate_condition_b(
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=None,
            vix_elevated=True,
            vix_declining_from_peak=True,
        )
        assert result.confirmed is None
        assert result.data_missing is True


# ---------------------------------------------------------------------------
# compute_per_name_size_pct
# ---------------------------------------------------------------------------


class TestComputePerNameSizePct:
    def test_standard_size_when_no_drawdown_gate(self) -> None:
        result = compute_per_name_size_pct(f30_drawdown_gate_active=False)
        assert result.standard_max_pct == pytest.approx(1.0)
        assert result.baseline_pct == pytest.approx(0.3)
        assert result.carveout_active is False

    def test_drawdown_gate_caps_at_0_5_pct(self) -> None:
        result = compute_per_name_size_pct(f30_drawdown_gate_active=True)
        assert result.standard_max_pct == pytest.approx(0.5)
        assert result.carveout_active is True

    def test_unknown_gate_returns_conservative_size(self) -> None:
        # When F30 state is unknown, apply carveout defensively
        result = compute_per_name_size_pct(f30_drawdown_gate_active=None)
        assert result.standard_max_pct == pytest.approx(0.5)
        assert result.carveout_active is True
        assert result.data_missing is True


# ---------------------------------------------------------------------------
# compute_f33_entry — overall condition routing
# ---------------------------------------------------------------------------


class TestComputeF33Entry:
    def test_qualifies_on_condition_a_alone(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=10.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
        )
        assert result.qualifies is True
        assert result.qualifying_condition == "A"

    def test_qualifies_on_condition_b_alone(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=5.0,
            vix_current=25.0,
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
            f30_drawdown_gate_active=False,
        )
        assert result.qualifies is True
        assert result.qualifying_condition == "B"

    def test_qualifies_on_both_conditions(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
            f30_drawdown_gate_active=False,
        )
        assert result.qualifies is True
        # When both qualify, A takes precedence (calm accumulation preferred)
        assert result.qualifying_condition == "A"

    def test_does_not_qualify_when_neither_condition_met(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=10.0,
            vix_current=25.0,
            sector_drawdown_pct=10.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
        )
        assert result.qualifies is False
        assert result.qualifying_condition is None

    def test_excluded_ticker_blocks_regardless_of_conditions(self) -> None:
        result = compute_f33_entry(
            ticker="SIVE",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
            f30_drawdown_gate_active=False,
        )
        assert result.qualifies is False
        assert result.excluded is True
        assert "SIVE" in result.block_reason

    def test_poet_excluded(self) -> None:
        result = compute_f33_entry(
            ticker="POET",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
            f30_drawdown_gate_active=False,
        )
        assert result.excluded is True

    def test_drawdown_gate_applies_carveout_when_qualifies(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=10.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=True,
        )
        assert result.qualifies is True
        assert result.size_guidance.carveout_active is True
        assert result.size_guidance.standard_max_pct == pytest.approx(0.5)

    def test_unavailable_when_critical_data_missing(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=None,
            vix_current=None,
            sector_drawdown_pct=None,
            capitulation_volume_confirmed=None,
            vix_elevated=None,
            vix_declining_from_peak=None,
            f30_drawdown_gate_active=None,
        )
        assert result.qualifies is None
        assert result.data_missing is True

    def test_and_gate_required_for_entries_above_10k(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=10.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
            intended_entry_usd=15000.0,
            and_gate_passed=False,
        )
        assert result.qualifies is False
        assert result.and_gate_required is True
        assert "AND gate" in result.block_reason

    def test_and_gate_not_required_for_entries_below_10k(self) -> None:
        result = compute_f33_entry(
            ticker="MRVL",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=10.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
            intended_entry_usd=5000.0,
            and_gate_passed=False,
        )
        assert result.qualifies is True
        assert result.and_gate_required is False


# ---------------------------------------------------------------------------
# SizeGuidance.baseline_max_pct — spec gap: 0.3–0.75% baseline range
# ---------------------------------------------------------------------------


class TestSizeGuidanceBaselineMaxPct:
    """Spec says '0.3–0.75% of total portfolio per name baseline'.
    The upper end of the baseline range must be exposed as baseline_max_pct=0.75
    on the SizeGuidance dataclass (no F30 gate active).
    """

    def test_no_gate_baseline_max_pct_is_0_75(self) -> None:
        guidance = compute_per_name_size_pct(f30_drawdown_gate_active=False)
        assert guidance.baseline_max_pct == pytest.approx(0.75)

    def test_carveout_baseline_max_pct_equals_carveout_cap(self) -> None:
        # Under carveout, ceiling is 0.5%; baseline_max == carveout max
        guidance = compute_per_name_size_pct(f30_drawdown_gate_active=True)
        assert guidance.baseline_max_pct == pytest.approx(0.5)

    def test_unknown_gate_baseline_max_pct_equals_conservative_cap(self) -> None:
        guidance = compute_per_name_size_pct(f30_drawdown_gate_active=None)
        assert guidance.baseline_max_pct == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# evaluate_condition_c — Bull Market Path
# ---------------------------------------------------------------------------


class TestEvaluateConditionC:
    """Condition C: T1E score ≥85 + dark pool bullish + options flow bullish + no gap day."""

    def test_confirmed_when_all_criteria_met(self) -> None:
        result = evaluate_condition_c(
            t1e_score=85,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.confirmed is True
        assert result.t1e_qualifies is True
        assert result.dark_pool_bullish is True
        assert result.options_flow_bullish is True
        assert result.no_gap_day is True
        assert result.data_missing is False

    def test_confirmed_at_exact_t1e_boundary(self) -> None:
        result = evaluate_condition_c(
            t1e_score=85,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.confirmed is True
        assert result.t1e_qualifies is True

    def test_not_met_when_t1e_below_threshold(self) -> None:
        result = evaluate_condition_c(
            t1e_score=84,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.confirmed is False
        assert result.t1e_qualifies is False

    def test_not_met_when_dark_pool_not_bullish(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=False,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.confirmed is False
        assert result.dark_pool_bullish is False

    def test_not_met_when_options_flow_not_bullish(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=False,
            no_gap_day=True,
        )
        assert result.confirmed is False
        assert result.options_flow_bullish is False

    def test_not_met_when_gap_day(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=False,
        )
        assert result.confirmed is False
        assert result.no_gap_day is False

    def test_unavailable_when_t1e_score_none(self) -> None:
        result = evaluate_condition_c(
            t1e_score=None,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_unavailable_when_dark_pool_none(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=None,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_unavailable_when_options_flow_none(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=None,
            no_gap_day=True,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_unavailable_when_no_gap_day_none(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=None,
        )
        assert result.confirmed is None
        assert result.data_missing is True

    def test_detail_describes_all_failing_criteria(self) -> None:
        result = evaluate_condition_c(
            t1e_score=70,
            dark_pool_bullish=False,
            options_flow_bullish=False,
            no_gap_day=True,
        )
        assert result.confirmed is False
        assert "T1E" in result.detail
        assert "dark pool" in result.detail.lower()
        assert "options flow" in result.detail.lower()

    def test_detail_mentions_gap_day_when_failing(self) -> None:
        result = evaluate_condition_c(
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=False,
        )
        assert "gap" in result.detail.lower()


# ---------------------------------------------------------------------------
# compute_f33_entry — Condition C routing
# ---------------------------------------------------------------------------


class TestComputeF33EntryConditionC:
    """compute_f33_entry routes through Condition C (bull market path)."""

    def _base_kwargs(self, **overrides) -> dict:  # type: ignore[type-arg]
        """Default args where A and B are NOT met but C inputs are provided."""
        defaults = dict(
            ticker="NVDA",
            drawdown_from_high_pct=5.0,   # below 20% — A not met
            vix_current=13.0,             # below calm range — A not met
            sector_drawdown_pct=5.0,      # below 25% — B not met
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
        )
        defaults.update(overrides)
        return defaults

    def test_qualifies_on_condition_c_when_a_and_b_not_met(self) -> None:
        result = compute_f33_entry(
            **self._base_kwargs(),
            t1e_score=88,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.qualifies is True
        assert result.qualifying_condition == "C"

    def test_condition_a_takes_precedence_over_c(self) -> None:
        result = compute_f33_entry(
            ticker="NVDA",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=5.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.qualifies is True
        assert result.qualifying_condition == "A"

    def test_condition_b_takes_precedence_over_c(self) -> None:
        result = compute_f33_entry(
            ticker="NVDA",
            drawdown_from_high_pct=5.0,
            vix_current=25.0,
            sector_drawdown_pct=30.0,
            capitulation_volume_confirmed=True,
            vix_elevated=True,
            vix_declining_from_peak=True,
            f30_drawdown_gate_active=False,
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.qualifies is True
        assert result.qualifying_condition == "B"

    def test_not_met_when_c_fails_and_a_b_not_met(self) -> None:
        result = compute_f33_entry(
            **self._base_kwargs(),
            t1e_score=80,
            dark_pool_bullish=False,
            options_flow_bullish=False,
            no_gap_day=True,
        )
        assert result.qualifies is False

    def test_c_inputs_default_none_does_not_break_existing_paths(self) -> None:
        """Omitting C inputs (backward compat) routes normally through A/B."""
        result = compute_f33_entry(
            ticker="NVDA",
            drawdown_from_high_pct=22.0,
            vix_current=16.5,
            sector_drawdown_pct=5.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
            # No C args — backward compat
        )
        assert result.qualifies is True
        assert result.qualifying_condition == "A"

    def test_all_none_still_returns_unavailable_when_c_inputs_none(self) -> None:
        result = compute_f33_entry(
            ticker="NVDA",
            drawdown_from_high_pct=None,
            vix_current=None,
            sector_drawdown_pct=None,
            capitulation_volume_confirmed=None,
            vix_elevated=None,
            vix_declining_from_peak=None,
            f30_drawdown_gate_active=None,
            t1e_score=None,
            dark_pool_bullish=None,
            options_flow_bullish=None,
            no_gap_day=None,
        )
        assert result.qualifies is None
        assert result.data_missing is True

    def test_condition_c_result_attached_to_entry_result(self) -> None:
        result = compute_f33_entry(
            **self._base_kwargs(),
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert hasattr(result, "condition_c")
        assert isinstance(result.condition_c, ConditionCResult)

    def test_excluded_ticker_still_blocked_even_with_c_met(self) -> None:
        result = compute_f33_entry(
            ticker="SIVE",
            drawdown_from_high_pct=5.0,
            vix_current=13.0,
            sector_drawdown_pct=5.0,
            capitulation_volume_confirmed=False,
            vix_elevated=False,
            vix_declining_from_peak=False,
            f30_drawdown_gate_active=False,
            t1e_score=90,
            dark_pool_bullish=True,
            options_flow_bullish=True,
            no_gap_day=True,
        )
        assert result.qualifies is False
        assert result.excluded is True
