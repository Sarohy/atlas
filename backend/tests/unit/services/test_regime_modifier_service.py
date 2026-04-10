"""Unit tests for RegimeModifierService pure helpers.

TDD — these tests are written BEFORE any implementation code.  They cover only
the deterministic pure functions (no I/O) so the suite runs without any
network calls or API keys.

Pure functions under test:
  _determine_rule        — (active_war, brent, vix, brent_consec) → 1|2|3|None
  _compute_regime_output — (rule, base_score, position_value) → adjusted values
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from atlas.services.regime_modifier_service import (
    _compute_regime_output,
    _determine_rule,
)

# ---------------------------------------------------------------------------
# _determine_rule
# ---------------------------------------------------------------------------


class TestDetermineRule:
    """Verify rule-trigger logic for all three regime rules."""

    # ── Rule 1 ──────────────────────────────────────────────────────────────

    def test_rule1_triggers_on_active_war(self) -> None:
        rule = _determine_rule(
            active_war=True,
            brent_price=80.0,
            vix_value=20.0,
            brent_consecutive_below_95=True,
        )
        assert rule == 1

    def test_rule1_triggers_on_brent_above_110(self) -> None:
        rule = _determine_rule(
            active_war=False,
            brent_price=111.0,
            vix_value=20.0,
            brent_consecutive_below_95=False,
        )
        assert rule == 1

    def test_rule1_triggers_on_brent_exactly_110(self) -> None:
        # Above $110 — exactly 110 does NOT trigger (must be > 110)
        rule = _determine_rule(
            active_war=False,
            brent_price=110.0,
            vix_value=20.0,
            brent_consecutive_below_95=False,
        )
        assert rule != 1

    def test_rule1_triggers_on_vix_above_35(self) -> None:
        rule = _determine_rule(
            active_war=False,
            brent_price=80.0,
            vix_value=35.1,
            brent_consecutive_below_95=False,
        )
        assert rule == 1

    def test_rule1_triggers_on_vix_exactly_35(self) -> None:
        # VIX must be > 35; exactly 35 does NOT trigger Rule 1
        rule = _determine_rule(
            active_war=False,
            brent_price=80.0,
            vix_value=35.0,
            brent_consecutive_below_95=False,
        )
        assert rule != 1

    def test_rule1_takes_priority_over_rule2(self) -> None:
        """Active war + caution Brent/VIX → Rule 1 wins."""
        rule = _determine_rule(
            active_war=True,
            brent_price=100.0,
            vix_value=28.0,
            brent_consecutive_below_95=False,
        )
        assert rule == 1

    # ── Rule 2 ──────────────────────────────────────────────────────────────

    def test_rule2_triggers_when_both_conditions_met(self) -> None:
        """Brent in [95,110] AND VIX in [24,35] → Rule 2."""
        rule = _determine_rule(
            active_war=False,
            brent_price=100.0,
            vix_value=28.0,
            brent_consecutive_below_95=False,
        )
        assert rule == 2

    def test_rule2_triggers_at_brent_lower_boundary(self) -> None:
        rule = _determine_rule(
            active_war=False,
            brent_price=95.0,
            vix_value=24.0,
            brent_consecutive_below_95=False,
        )
        assert rule == 2

    def test_rule2_triggers_at_brent_upper_boundary(self) -> None:
        rule = _determine_rule(
            active_war=False,
            brent_price=110.0,
            vix_value=35.0,
            brent_consecutive_below_95=False,
        )
        assert rule == 2

    def test_rule2_does_not_trigger_with_only_brent_in_range(self) -> None:
        """Only Brent in caution range — Rule 2 requires BOTH conditions."""
        rule = _determine_rule(
            active_war=False,
            brent_price=100.0,
            vix_value=23.0,  # below VIX caution threshold
            brent_consecutive_below_95=False,
        )
        assert rule is None

    def test_rule2_does_not_trigger_with_only_vix_in_range(self) -> None:
        """Only VIX in caution range — Rule 2 requires BOTH conditions."""
        rule = _determine_rule(
            active_war=False,
            brent_price=94.0,  # below Brent caution threshold
            vix_value=28.0,
            brent_consecutive_below_95=False,
        )
        assert rule is None

    # ── Rule 3 ──────────────────────────────────────────────────────────────

    def test_rule3_triggers_when_both_conditions_met(self) -> None:
        """Brent below $95 two consecutive closes AND VIX below 24 → Rule 3."""
        rule = _determine_rule(
            active_war=False,
            brent_price=90.0,
            vix_value=22.0,
            brent_consecutive_below_95=True,
        )
        assert rule == 3

    def test_rule3_does_not_trigger_with_single_brent_close(self) -> None:
        """Only one close below $95 — Rule 3 requires TWO consecutive closes."""
        rule = _determine_rule(
            active_war=False,
            brent_price=90.0,
            vix_value=22.0,
            brent_consecutive_below_95=False,  # only one close counted
        )
        assert rule is None

    def test_rule3_does_not_trigger_when_vix_at_or_above_24(self) -> None:
        rule = _determine_rule(
            active_war=False,
            brent_price=90.0,
            vix_value=24.0,  # must be strictly below 24
            brent_consecutive_below_95=True,
        )
        assert rule is None

    # ── No rule ─────────────────────────────────────────────────────────────

    def test_no_rule_in_normal_market(self) -> None:
        """Low Brent, low VIX, no war, single close — no rule fires."""
        rule = _determine_rule(
            active_war=False,
            brent_price=85.0,
            vix_value=18.0,
            brent_consecutive_below_95=False,
        )
        assert rule is None


# ---------------------------------------------------------------------------
# _compute_regime_output
# ---------------------------------------------------------------------------


class TestComputeRegimeOutput:
    """Verify score adjustment, cash bounds, and output text per rule."""

    # ── Rule 1 ──────────────────────────────────────────────────────────────

    def test_rule1_deducts_10_from_score(self) -> None:
        adjusted, *_ = _compute_regime_output(1, 75, None)
        assert adjusted == 65

    def test_rule1_clamps_score_at_zero(self) -> None:
        adjusted, *_ = _compute_regime_output(1, 8, None)
        assert adjusted == 0

    def test_rule1_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(1, 75, None)
        assert min_pct == pytest.approx(0.35)
        assert max_pct == pytest.approx(0.40)

    def test_rule1_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("10000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(1, 75, position_value)
        assert min_usd == Decimal("3500.00")
        assert max_usd == Decimal("4000.00")

    def test_rule1_cash_usd_none_when_no_position(self) -> None:
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(1, 75, None)
        assert min_usd is None
        assert max_usd is None

    def test_rule1_output_text(self) -> None:
        *_, output_text = _compute_regime_output(1, 75, None)
        assert "must stay in cash" in output_text
        assert "cannot be touched" in output_text
        assert "for any trade" in output_text

    # ── Rule 2 ──────────────────────────────────────────────────────────────

    def test_rule2_deducts_5_from_score(self) -> None:
        adjusted, *_ = _compute_regime_output(2, 80, None)
        assert adjusted == 75

    def test_rule2_clamps_score_at_zero(self) -> None:
        adjusted, *_ = _compute_regime_output(2, 3, None)
        assert adjusted == 0

    def test_rule2_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(2, 80, None)
        assert min_pct == pytest.approx(0.25)
        assert max_pct == pytest.approx(0.35)

    def test_rule2_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("20000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(2, 80, position_value)
        assert min_usd == Decimal("5000.00")
        assert max_usd == Decimal("7000.00")

    def test_rule2_output_text(self) -> None:
        *_, output_text = _compute_regime_output(2, 80, None)
        assert "must stay in cash" in output_text

    # ── Rule 3 ──────────────────────────────────────────────────────────────

    def test_rule3_adds_5_to_score(self) -> None:
        adjusted, *_ = _compute_regime_output(3, 70, None)
        assert adjusted == 75

    def test_rule3_clamps_score_at_100(self) -> None:
        adjusted, *_ = _compute_regime_output(3, 97, None)
        assert adjusted == 100

    def test_rule3_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(3, 70, None)
        assert min_pct == pytest.approx(0.10)
        assert max_pct == pytest.approx(0.12)

    def test_rule3_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("50000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(3, 70, position_value)
        assert min_usd == Decimal("5000.00")
        assert max_usd == Decimal("6000.00")

    def test_rule3_output_text(self) -> None:
        *_, output_text = _compute_regime_output(3, 70, None)
        assert "only this stays in cash" in output_text
        assert "everything else" in output_text
        assert "can be deployed" in output_text

    # ── No rule ─────────────────────────────────────────────────────────────

    def test_no_rule_preserves_score(self) -> None:
        adjusted, *_ = _compute_regime_output(None, 82, None)
        assert adjusted == 82

    def test_no_rule_zero_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(None, 82, None)
        assert min_pct == pytest.approx(0.0)
        assert max_pct == pytest.approx(0.0)

    def test_no_rule_zero_cash_usd(self) -> None:
        position_value = Decimal("10000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(None, 82, position_value)
        assert min_usd is None
        assert max_usd is None
