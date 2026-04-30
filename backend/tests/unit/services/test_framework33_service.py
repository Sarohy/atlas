"""Unit tests for framework33_service — LEAPS Entry Conditions V2.

Covers:
  - is_excluded_ticker: OTC/thin-option exclusion list
  - evaluate_condition_a: Calm Accumulation (20%+ drawdown + VIX 15-18)
  - evaluate_condition_b: Washout (25%+ sector drawdown + cap volume + VIX declining)
  - compute_per_name_size_pct: sizing rules with F30 drawdown gate
  - compute_f33_entry: overall condition routing (A OR B qualifies)
"""

from __future__ import annotations

import pytest

from atlas.services.framework33_service import (
    ConditionAResult,
    ConditionBResult,
    F33EntryResult,
    compute_f33_entry,
    compute_per_name_size_pct,
    evaluate_condition_a,
    evaluate_condition_b,
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
