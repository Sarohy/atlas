"""Unit tests for FrameworkScoreService pure helpers.

TDD — these tests are written BEFORE any implementation code.  They cover only
the deterministic pure functions (no I/O) so the suite runs without any
network calls or API keys.

Pure functions under test:
  _map_action        — final_score → (action, action_tone)
  _compute_raw_total — (f1,f2,f3,f4,f5) → weighted sum (max 95)
  _compute_final_score — raw_total → clamped int [0,100]
"""

from __future__ import annotations

import pytest

from atlas.services.framework_score_service import (
    _compute_final_score,
    _compute_raw_total,
    _map_action,
)

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
      F1 x 0.15  F2 x 0.25  F3 x 0.15  F4 x 0.15  F5 x 0.30  -> max = 100
    """

    def test_all_perfect_scores_give_100(self) -> None:
        assert _compute_raw_total(100, 100, 100, 100, 100) == pytest.approx(100.0)

    def test_all_zero_scores_give_0(self) -> None:
        assert _compute_raw_total(0, 0, 0, 0, 0) == pytest.approx(0.0)

    def test_only_f1_contributes(self) -> None:
        # 100 x 0.15 = 15.0
        assert _compute_raw_total(100, 0, 0, 0, 0) == pytest.approx(15.0)

    def test_only_f2_contributes(self) -> None:
        # 100 x 0.25 = 25.0
        assert _compute_raw_total(0, 100, 0, 0, 0) == pytest.approx(25.0)

    def test_only_f3_contributes(self) -> None:
        # 100 x 0.15 = 15.0
        assert _compute_raw_total(0, 0, 100, 0, 0) == pytest.approx(15.0)

    def test_only_f4_contributes(self) -> None:
        # 100 x 0.15 = 15.0
        assert _compute_raw_total(0, 0, 0, 100, 0) == pytest.approx(15.0)

    def test_only_f5_contributes(self) -> None:
        # 100 x 0.30 = 30.0
        assert _compute_raw_total(0, 0, 0, 0, 100) == pytest.approx(30.0)

    def test_lite_worked_example(self) -> None:
        """LITE example from Factor_Mapping_Guide (before regime modifier).

        F1=86, F2=94, F3=100, F4=82, F5=78 (using guide sample scores)
          86 x 0.15 = 12.90
          94 x 0.25 = 23.50
         100 x 0.15 = 15.00
          82 x 0.15 = 12.30
          78 x 0.30 = 23.40
          Total     = 87.10
        """
        result = _compute_raw_total(86, 94, 100, 82, 78)
        assert result == pytest.approx(87.10, abs=0.01)


# ---------------------------------------------------------------------------
# _compute_final_score
# ---------------------------------------------------------------------------


class TestComputeFinalScore:
    """raw_total → clamped int [0, 100]."""

    def test_typical_score(self) -> None:
        # 83.6 → rounds to 84
        assert _compute_final_score(83.60) == 84

    def test_clamp_at_100(self) -> None:
        assert _compute_final_score(100.0) == 100

    def test_clamp_at_0(self) -> None:
        assert _compute_final_score(0.0) == 0

    def test_max_possible_score_is_100(self) -> None:
        """Perfect score on all factors gives 100 (weights sum to 1.00)."""
        raw = _compute_raw_total(100, 100, 100, 100, 100)  # 100.0
        final = _compute_final_score(raw)  # 100
        assert final == 100

    def test_rounding(self) -> None:
        # 82.6 → rounds to 83
        assert _compute_final_score(82.6) == 83
