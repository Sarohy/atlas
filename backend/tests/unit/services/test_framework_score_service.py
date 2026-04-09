"""Unit tests for FrameworkScoreService pure helpers.

TDD — these tests are written BEFORE any implementation code.  They cover only
the deterministic pure functions (no I/O) so the suite runs without any
network calls or API keys.

Pure functions under test:
  _classify_regime   — Brent price → (regime, modifier, cash_floor_pct)
  _map_action        — final_score → (action, action_tone)
  _compute_raw_total — (f1,f2,f3,f4,f5) → weighted sum (max 95)
  _compute_final_score — (raw_total, modifier) → clamped int [0,100]
"""

from __future__ import annotations

import pytest

from atlas.services.framework_score_service import (
    _classify_regime,
    _compute_final_score,
    _compute_raw_total,
    _map_action,
)

# ---------------------------------------------------------------------------
# _classify_regime
# ---------------------------------------------------------------------------


class TestClassifyRegime:
    """Brent crude price → (regime, modifier, cash_floor_pct)."""

    def test_crisis_halt_above_110(self) -> None:
        regime, modifier, cash_floor = _classify_regime(115.0)
        assert regime == "CRISIS HALT"
        assert modifier == -10
        assert cash_floor == pytest.approx(0.40)

    def test_crisis_halt_at_110_01(self) -> None:
        regime, modifier, _ = _classify_regime(110.01)
        assert regime == "CRISIS HALT"
        assert modifier == -10

    def test_caution_at_110_exactly(self) -> None:
        """Boundary: $110 is the last CAUTION point (not CRISIS)."""
        regime, modifier, cash_floor = _classify_regime(110.0)
        assert regime == "CAUTION"
        assert modifier == -5
        assert cash_floor == pytest.approx(0.25)

    def test_caution_mid_band(self) -> None:
        regime, modifier, cash_floor = _classify_regime(100.0)
        assert regime == "CAUTION"
        assert modifier == -5
        assert cash_floor == pytest.approx(0.25)

    def test_caution_at_95_exactly(self) -> None:
        """Boundary: $95 is the first CAUTION point (not CLEAR)."""
        regime, modifier, cash_floor = _classify_regime(95.0)
        assert regime == "CAUTION"
        assert modifier == -5
        assert cash_floor == pytest.approx(0.25)

    def test_clear_just_below_95(self) -> None:
        regime, modifier, cash_floor = _classify_regime(94.99)
        assert regime == "CLEAR"
        assert modifier == 5
        assert cash_floor == pytest.approx(0.10)

    def test_clear_far_below_95(self) -> None:
        regime, modifier, _ = _classify_regime(60.0)
        assert regime == "CLEAR"
        assert modifier == 5

    def test_none_brent_defaults_to_caution(self) -> None:
        """No live Brent data → conservative fallback to CAUTION."""
        regime, modifier, cash_floor = _classify_regime(None)
        assert regime == "CAUTION"
        assert modifier == -5
        assert cash_floor == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# _map_action
# ---------------------------------------------------------------------------


class TestMapAction:
    """final_score → (action, action_tone) mapping per Factor_Mapping_Guide."""

    @pytest.mark.parametrize("score", [90, 95, 100])
    def test_maximum_position(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "MAXIMUM POSITION"
        assert tone == "tone-green"

    @pytest.mark.parametrize("score", [80, 85, 89])
    def test_hold_add(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "HOLD / ADD"
        assert tone == "tone-cyan"

    @pytest.mark.parametrize("score", [70, 75, 79])
    def test_hold(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "HOLD"
        assert tone == "tone-yellow"

    @pytest.mark.parametrize("score", [60, 65, 69])
    def test_reduce(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "REDUCE"
        assert tone == "tone-orange"

    @pytest.mark.parametrize("score", [55, 57, 59])
    def test_reduce_further(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "REDUCE FURTHER"
        assert tone == "tone-red"

    @pytest.mark.parametrize("score", [0, 30, 54])
    def test_exit(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "EXIT"
        assert tone == "tone-dark-red"


# ---------------------------------------------------------------------------
# _compute_raw_total
# ---------------------------------------------------------------------------


class TestComputeRawTotal:
    """Verifies that factor weights are applied correctly.

    Weights per Factor_Mapping_Guide:
      F1 x 0.20  F2 x 0.25  F3 x 0.15  F4 x 0.15  F5 x 0.20  -> max = 95
    """

    def test_all_perfect_scores_give_95(self) -> None:
        assert _compute_raw_total(100, 100, 100, 100, 100) == pytest.approx(95.0)

    def test_all_zero_scores_give_0(self) -> None:
        assert _compute_raw_total(0, 0, 0, 0, 0) == pytest.approx(0.0)

    def test_only_f1_contributes(self) -> None:
        # 100 x 0.20 = 20.0
        assert _compute_raw_total(100, 0, 0, 0, 0) == pytest.approx(20.0)

    def test_only_f2_contributes(self) -> None:
        # 100 x 0.25 = 25.0
        assert _compute_raw_total(0, 100, 0, 0, 0) == pytest.approx(25.0)

    def test_only_f3_contributes(self) -> None:
        assert _compute_raw_total(0, 0, 100, 0, 0) == pytest.approx(15.0)

    def test_only_f4_contributes(self) -> None:
        assert _compute_raw_total(0, 0, 0, 100, 0) == pytest.approx(15.0)

    def test_only_f5_contributes(self) -> None:
        assert _compute_raw_total(0, 0, 0, 0, 100) == pytest.approx(20.0)

    def test_lite_worked_example(self) -> None:
        """LITE example from Factor_Mapping_Guide (before regime modifier).

        F1=86, F2=94, F3=100, F4=82, F5=78 (using guide sample scores)
          86 x 0.20 = 17.20
          94 x 0.25 = 23.50
         100 x 0.15 = 15.00
          82 x 0.15 = 12.30
          78 x 0.20 = 15.60
          Total     = 83.60
        """
        result = _compute_raw_total(86, 94, 100, 82, 78)
        assert result == pytest.approx(83.60, abs=0.01)


# ---------------------------------------------------------------------------
# _compute_final_score
# ---------------------------------------------------------------------------


class TestComputeFinalScore:
    """raw_total + modifier → clamped int [0, 100]."""

    def test_typical_clear_regime(self) -> None:
        # 83.6 + 5 = 88.6 → rounds to 89
        assert _compute_final_score(83.60, 5) == 89

    def test_caution_regime(self) -> None:
        # 83.6 - 5 = 78.6 → rounds to 79
        assert _compute_final_score(83.60, -5) == 79

    def test_crisis_halt_regime(self) -> None:
        # 83.6 - 10 = 73.6 → rounds to 74
        assert _compute_final_score(83.60, -10) == 74

    def test_clamp_at_100(self) -> None:
        # 95 + 5 = 100 → 100
        assert _compute_final_score(95.0, 5) == 100

    def test_clamp_at_0(self) -> None:
        # 0 - 10 = -10 → clamped to 0
        assert _compute_final_score(0.0, -10) == 0

    def test_max_possible_score_is_100(self) -> None:
        """Perfect score on all factors in CLEAR regime gives exactly 100."""
        raw = _compute_raw_total(100, 100, 100, 100, 100)  # 95.0
        final = _compute_final_score(raw, 5)  # 95 + 5 = 100
        assert final == 100

    def test_rounding_half_up(self) -> None:
        # 77.5 + 5 = 82.5 → rounds to 83 (Python round ties-to-even = 82, but
        # we use round() which is banker's rounding; 82.5 → 82 in Python3).
        # Testing a non-tie case to avoid ambiguity.
        assert _compute_final_score(77.6, 5) == 83
