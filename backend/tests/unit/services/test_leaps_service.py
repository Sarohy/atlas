"""Unit tests for leaps_service — Section 17 LEAPS Strategy Module.

Covers:
  - _determine_tier: correct tier boundaries
  - _check_iv_block: IV hard-block logic
  - _check_regime_clears_leaps: regime gate
  - _evaluate_entry_condition3: score threshold condition
  - _compute_eligibility: block-reason assembly and tristate output
  - Score source regression: conviction score must come from F1 final_score,
    not F4 options flow score (the original data-sync bug).
"""

from __future__ import annotations

from atlas.services.leaps_service import (
    _check_iv_block,
    _check_regime_clears_leaps,
    _compute_eligibility,
    _determine_tier,
    _evaluate_entry_condition1,
    _evaluate_entry_condition2,
    _evaluate_entry_condition3,
)

# ---------------------------------------------------------------------------
# _determine_tier
# ---------------------------------------------------------------------------


class TestDetermineTier:
    def test_tier1_at_boundary(self) -> None:
        assert _determine_tier(85) == "TIER_1"

    def test_tier1_above_boundary(self) -> None:
        assert _determine_tier(95) == "TIER_1"

    def test_tier2_just_below_tier1(self) -> None:
        assert _determine_tier(84) == "TIER_2"

    def test_tier2_at_boundary(self) -> None:
        assert _determine_tier(70) == "TIER_2"

    def test_tier3_just_below_tier2(self) -> None:
        assert _determine_tier(69) == "TIER_3"

    def test_tier3_low_score(self) -> None:
        assert _determine_tier(40) == "TIER_3"

    def test_tier3_zero(self) -> None:
        assert _determine_tier(0) == "TIER_3"


# ---------------------------------------------------------------------------
# _check_iv_block
# ---------------------------------------------------------------------------


class TestCheckIVBlock:
    def test_iv_above_threshold_blocks(self) -> None:
        assert _check_iv_block(0.91) is True

    def test_iv_at_threshold_blocks(self) -> None:
        assert _check_iv_block(0.90) is False  # rule is strictly >90%

    def test_iv_below_threshold_does_not_block(self) -> None:
        assert _check_iv_block(0.50) is False

    def test_iv_none_returns_none(self) -> None:
        assert _check_iv_block(None) is None


# ---------------------------------------------------------------------------
# _check_regime_clears_leaps
# ---------------------------------------------------------------------------


class TestCheckRegimeClearsLeaps:
    def test_clear_regime_permitted(self) -> None:
        assert _check_regime_clears_leaps("CLEAR") is True

    def test_soft_caution_permitted(self) -> None:
        assert _check_regime_clears_leaps("SOFT_CAUTION") is True

    def test_normal_permitted(self) -> None:
        assert _check_regime_clears_leaps("NORMAL") is True

    def test_caution_blocks(self) -> None:
        assert _check_regime_clears_leaps("CAUTION") is False

    def test_crisis_halt_blocks(self) -> None:
        assert _check_regime_clears_leaps("CRISIS_HALT") is False

    def test_none_regime_returns_none(self) -> None:
        assert _check_regime_clears_leaps(None) is None

    def test_case_insensitive(self) -> None:
        assert _check_regime_clears_leaps("clear") is True


# ---------------------------------------------------------------------------
# _evaluate_entry_condition3 (score threshold)
# ---------------------------------------------------------------------------


class TestEvaluateEntryCondition3:
    def test_score_meets_threshold(self) -> None:
        cond = _evaluate_entry_condition3(70)
        assert cond.met is True
        assert "70" in cond.detail

    def test_score_at_threshold(self) -> None:
        cond = _evaluate_entry_condition3(70)
        assert cond.met is True

    def test_score_below_threshold(self) -> None:
        # MU regression: final_score 68 must show as below-threshold.
        cond = _evaluate_entry_condition3(68)
        assert cond.met is False
        assert "68" in cond.detail

    def test_score_f4_value_below_threshold(self) -> None:
        # F4 options flow score for MU is 50 — must be flagged below threshold.
        cond = _evaluate_entry_condition3(50)
        assert cond.met is False
        assert "50" in cond.detail

    def test_score_none_returns_incomplete(self) -> None:
        cond = _evaluate_entry_condition3(None)
        assert cond.met is None


# ---------------------------------------------------------------------------
# _compute_eligibility: score-source regression test
# ---------------------------------------------------------------------------


class TestComputeEligibilityScoreRegression:
    """Regression: the conviction score used in _compute_eligibility must be
    F1 final_score (post-regime), never an F4 options-flow sub-score.

    MU specifics (April 2026):
      F1 final_score: 68   ← correct source (post-regime conviction score)
      F9 f4_score:    50   ← wrong source (options flow sub-score)

    Both 68 and 50 are below the LEAPS minimum of 70, so LEAPS is BLOCKED
    in both cases.  The difference is the error message must cite 68, not 50.
    """

    def _make_base_entry_conditions(self, score: int | None) -> list:
        return [
            _evaluate_entry_condition1(True),
            _evaluate_entry_condition2("CLEAR"),
            _evaluate_entry_condition3(score),
        ]

    def test_score_68_block_reason_cites_68(self) -> None:
        """With F1 final_score=68, block reason must mention 68 not 50."""
        result = _compute_eligibility(
            ticker="MU",
            score=68,
            tier="TIER_3",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.71,
            iv_percentile=0.60,
            entry_conditions=self._make_base_entry_conditions(68),
            data_age_minutes=0,
        )
        assert result.leaps_eligible is False
        assert result.score == 68
        # Block reason must mention 68, must NOT mention 50.
        assert any("68" in r for r in result.block_reasons), (
            f"Block reasons should cite score 68, got: {result.block_reasons}"
        )
        assert not any("50" in r for r in result.block_reasons), (
            f"Block reasons must not cite F4 score 50, got: {result.block_reasons}"
        )

    def test_score_50_would_also_block_but_with_different_message(self) -> None:
        """Score 50 also blocks LEAPS but the block message must cite 50.

        This test documents the previous incorrect behaviour so we can confirm
        it is gone — the service must never pass 50 as the score when 68 is
        the correct F1 value.
        """
        result = _compute_eligibility(
            ticker="MU",
            score=50,
            tier="TIER_3",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.71,
            iv_percentile=0.60,
            entry_conditions=self._make_base_entry_conditions(50),
            data_age_minutes=0,
        )
        assert result.leaps_eligible is False
        assert result.score == 50
        assert any("50" in r for r in result.block_reasons)

    def test_score_86_tier1_eligible(self) -> None:
        """Hypothetical: F1 final_score=86 → TIER_1 eligible when gates clear."""
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,  # not needed for Tier 1
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=self._make_base_entry_conditions(86),
            data_age_minutes=0,
        )
        assert result.leaps_eligible is True
        assert result.score == 86

    def test_score_72_tier2_needs_flow(self) -> None:
        """Hypothetical: F1 final_score=72 → Tier 2, blocked without flow."""
        result = _compute_eligibility(
            ticker="MU",
            score=72,
            tier="TIER_2",
            flow_confirmed=False,  # no dark pool flow
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=self._make_base_entry_conditions(72),
            data_age_minutes=0,
        )
        assert result.leaps_eligible is False
        assert result.score == 72
        assert any("500" in r for r in result.block_reasons)  # dark pool threshold

    def test_score_none_returns_undetermined(self) -> None:
        """When F1 is unavailable, leaps_eligible must be None — no fallback score."""
        result = _compute_eligibility(
            ticker="MU",
            score=None,
            tier=None,
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=self._make_base_entry_conditions(None),
            data_age_minutes=0,
        )
        # score=None means data unavailable — must NOT default to 0 or 55.
        assert result.leaps_eligible is None
        assert result.score is None
        assert result.eligibility_undetermined is True
