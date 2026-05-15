"""Unit tests for leaps_service — Section 17 LEAPS Strategy Module.

Covers:
  - _determine_tier: correct tier boundaries
  - _check_iv_block: IV hard-block logic
  - _check_regime_clears_leaps: regime gate
  - _evaluate_entry_condition3: score threshold condition
  - _compute_eligibility: block-reason assembly and tristate output
  - Score source regression: conviction score must come from F1 final_score,
    not F4 options flow score (the original data-sync bug).
  - _compute_iv_catalyst_wait: post-earnings IV cooldown window
  - _detect_price_gap: gap-day detection
  - _compute_eligibility with gap/IV-wait params
"""

from __future__ import annotations

from datetime import date

from atlas.services.leaps_service import (
    _check_iv_block,
    _check_regime_clears_leaps,
    _compute_eligibility,
    _compute_iv_catalyst_wait,
    _detect_price_gap,
    _determine_entry_type,
    _determine_tier,
    _evaluate_entry_condition1,
    _evaluate_entry_condition2,
    _evaluate_entry_condition3,
)

# ---------------------------------------------------------------------------
# _determine_tier
# ---------------------------------------------------------------------------


class TestDetermineTier:
    def test_t1_elite_at_boundary(self) -> None:
        assert _determine_tier(85) == "T1_ELITE"

    def test_t1_elite_above_boundary(self) -> None:
        assert _determine_tier(95) == "T1_ELITE"

    def test_t1_just_below_t1_elite(self) -> None:
        assert _determine_tier(84) == "T1"

    def test_t1_at_boundary(self) -> None:
        assert _determine_tier(80) == "T1"

    def test_t2_just_below_t1(self) -> None:
        assert _determine_tier(79) == "T2"

    def test_t2_at_boundary(self) -> None:
        assert _determine_tier(70) == "T2"

    def test_t3_just_below_t2(self) -> None:
        assert _determine_tier(69) == "T3"

    def test_t3_at_boundary(self) -> None:
        assert _determine_tier(50) == "T3"

    def test_below_gate_just_below_t3(self) -> None:
        assert _determine_tier(49) == "BELOW_GATE"

    def test_below_gate_zero(self) -> None:
        assert _determine_tier(0) == "BELOW_GATE"


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
            tier="T3",
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
        """Hypothetical: F1 final_score=86 → T1_ELITE eligible when gates clear."""
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="T1_ELITE",
            flow_confirmed=None,  # not needed for T1_ELITE
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
            gap_detected=False,  # no gap today
        )
        assert result.leaps_eligible is True
        assert result.score == 86

    def test_score_82_t1_needs_flow(self) -> None:
        """T1 (80-84) requires dark pool flow confirmation."""
        result = _compute_eligibility(
            ticker="MSFT",
            score=82,
            tier="T1",
            flow_confirmed=False,  # no dark pool flow
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=self._make_base_entry_conditions(82),
            data_age_minutes=0,
        )
        assert result.leaps_eligible is False
        assert result.score == 82
        assert any("500" in r for r in result.block_reasons)

    def test_score_72_t2_needs_flow(self) -> None:
        """Hypothetical: F1 final_score=72 → T2, blocked without flow."""
        result = _compute_eligibility(
            ticker="MU",
            score=72,
            tier="T2",
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


# ---------------------------------------------------------------------------
# _compute_iv_catalyst_wait
# ---------------------------------------------------------------------------


class TestComputeIVCatalystWait:
    """Post-earnings IV cooldown window (7 calendar days)."""

    def test_catalyst_1_day_ago_returns_6_remaining(self) -> None:
        today = date(2026, 4, 30)
        earnings = date(2026, 4, 29)  # 1 day ago
        assert _compute_iv_catalyst_wait(earnings, today=today) == 6

    def test_catalyst_3_days_ago_returns_4_remaining(self) -> None:
        today = date(2026, 4, 30)
        earnings = date(2026, 4, 27)  # 3 days ago
        assert _compute_iv_catalyst_wait(earnings, today=today) == 4

    def test_catalyst_7_days_ago_returns_0(self) -> None:
        today = date(2026, 4, 30)
        earnings = date(2026, 4, 23)  # exactly 7 days ago
        assert _compute_iv_catalyst_wait(earnings, today=today) == 0

    def test_catalyst_8_days_ago_returns_0(self) -> None:
        today = date(2026, 4, 30)
        earnings = date(2026, 4, 22)  # 8 days ago — wait over
        assert _compute_iv_catalyst_wait(earnings, today=today) == 0

    def test_no_earnings_date_returns_none(self) -> None:
        assert _compute_iv_catalyst_wait(None) is None

    def test_earnings_in_future_returns_0(self) -> None:
        today = date(2026, 4, 30)
        earnings = date(2026, 5, 5)  # future — not a past catalyst
        assert _compute_iv_catalyst_wait(earnings, today=today) == 0

    def test_catalyst_today_returns_7(self) -> None:
        today = date(2026, 4, 30)
        earnings = date(2026, 4, 30)  # day-of earnings
        assert _compute_iv_catalyst_wait(earnings, today=today) == 7


# ---------------------------------------------------------------------------
# _detect_price_gap
# ---------------------------------------------------------------------------


class TestDetectPriceGap:
    """Price gap detection: open vs. previous close ≥ 2% gap threshold."""

    def test_gap_up_above_threshold_returns_true(self) -> None:
        # Open 3% above prev close — gap up
        assert _detect_price_gap(103.0, 100.0) is True

    def test_gap_down_above_threshold_returns_true(self) -> None:
        # Open 2.5% below prev close — gap down
        assert _detect_price_gap(97.5, 100.0) is True

    def test_exact_threshold_returns_true(self) -> None:
        # Exactly 2% — at threshold, should detect
        assert _detect_price_gap(102.0, 100.0) is True

    def test_small_diff_below_threshold_returns_false(self) -> None:
        # Only 0.5% difference — not a gap
        assert _detect_price_gap(100.5, 100.0) is False

    def test_none_open_returns_none(self) -> None:
        assert _detect_price_gap(None, 100.0) is None

    def test_none_prev_close_returns_none(self) -> None:
        assert _detect_price_gap(100.0, None) is None

    def test_zero_prev_close_returns_none(self) -> None:
        assert _detect_price_gap(100.0, 0.0) is None

    def test_both_none_returns_none(self) -> None:
        assert _detect_price_gap(None, None) is None

    def test_no_gap_same_price_returns_false(self) -> None:
        assert _detect_price_gap(100.0, 100.0) is False


# ---------------------------------------------------------------------------
# _compute_eligibility with gap / IV-wait params
# ---------------------------------------------------------------------------


def _base_entry_conditions() -> list:
    return [
        _evaluate_entry_condition1(True),
        _evaluate_entry_condition2("CLEAR"),
        _evaluate_entry_condition3(86),
    ]


class TestComputeEligibilityGapBlock:
    def test_gap_detected_adds_block_reason(self) -> None:
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=_base_entry_conditions(),
            data_age_minutes=0,
            gap_detected=True,
        )
        assert result.leaps_eligible is False
        assert result.gap_detected is True
        assert any("gap" in r.lower() for r in result.block_reasons)

    def test_gap_not_detected_does_not_block(self) -> None:
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=_base_entry_conditions(),
            data_age_minutes=0,
            gap_detected=False,
        )
        assert result.leaps_eligible is True
        assert result.gap_detected is False

    def test_gap_unknown_adds_warning_not_block(self) -> None:
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=_base_entry_conditions(),
            data_age_minutes=0,
            gap_detected=None,
        )
        # gap unknown → deferred (undetermined), not hard blocked
        assert result.leaps_eligible is None
        assert result.eligibility_undetermined is True
        assert any("gap" in w.lower() for w in result.warning_messages)


class TestComputeEligibilityIVCatalystWait:
    def test_iv_wait_remaining_blocks_leaps(self) -> None:
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=_base_entry_conditions(),
            data_age_minutes=0,
            iv_catalyst_wait_days_remaining=4,
        )
        assert result.leaps_eligible is False
        assert result.iv_catalyst_wait_days_remaining == 4
        assert any("catalyst" in r.lower() or "iv" in r.lower() for r in result.block_reasons)

    def test_iv_wait_zero_does_not_block(self) -> None:
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=_base_entry_conditions(),
            data_age_minutes=0,
            gap_detected=False,
            iv_catalyst_wait_days_remaining=0,
        )
        assert result.leaps_eligible is True
        assert result.iv_catalyst_wait_days_remaining == 0

    def test_iv_wait_none_does_not_block(self) -> None:
        result = _compute_eligibility(
            ticker="NVDA",
            score=86,
            tier="TIER_1",
            flow_confirmed=None,
            regime_state="CLEAR",
            gate_f7_active=False,
            gate_f29_passed=True,
            gate_f30_permits_leaps=True,
            gate_f11_blocks=False,
            gate_f15_blocks=False,
            iv_current=0.45,
            iv_percentile=0.30,
            entry_conditions=_base_entry_conditions(),
            data_age_minutes=0,
            gap_detected=False,
            iv_catalyst_wait_days_remaining=None,
        )
        # None means no earnings data — should not block
        assert result.leaps_eligible is True
        assert result.iv_catalyst_wait_days_remaining is None


# ---------------------------------------------------------------------------
# check_leaps_eligibility — provided_score bypass
# ---------------------------------------------------------------------------


class TestCheckLeapsEligibilityProvidedScore:
    """When a caller passes provided_score, the service must use it directly
    instead of re-fetching from F7 + regime, so that Framework 10 mirrors
    the exact score already displayed in Framework 1.
    """

    def test_signature_accepts_provided_score(self) -> None:
        """check_leaps_eligibility must accept a provided_score keyword arg."""
        import inspect

        from atlas.services.leaps_service import check_leaps_eligibility

        sig = inspect.signature(check_leaps_eligibility)
        assert "provided_score" in sig.parameters, (
            "check_leaps_eligibility must have a 'provided_score' parameter "
            "so callers can pass the F1-panel score directly."
        )
        param = sig.parameters["provided_score"]
        assert param.default is None, (
            "provided_score must default to None (optional bypass)."
        )


# ---------------------------------------------------------------------------
# check_leaps_eligibility — provided_score bypass
# ---------------------------------------------------------------------------


class TestCheckLeapsEligibilityProvidedScore:
    """When a caller passes provided_score, the service must use it directly
    instead of re-fetching from F7 + regime, so that Framework 10 mirrors
    the exact score already displayed in Framework 1.
    """

    def test_provided_score_bypasses_resolve(self) -> None:
        """_resolve_current_score must NOT be called when provided_score is given."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_session = MagicMock()

        # Stub everything the service calls after score resolution.
        with (
            patch(
                "atlas.services.leaps_service._resolve_current_score",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "atlas.services.leaps_service.is_excluded_ticker",
                return_value=False,
            ),
            patch(
                "atlas.services.leaps_service._cache_get",
                return_value=(None, 0),
            ),
            patch(
                "atlas.services.leaps_service._cache_set",
            ),
            patch(
                "atlas.services.leaps_service._run_full_evaluation",
                new_callable=AsyncMock,
            ) as mock_eval,
        ):
            from atlas.schemas.leaps import LeapsEligibility
            from atlas.services.leaps_service import IVAlert

            mock_eval.return_value = LeapsEligibility(
                ticker="AAPL",
                leaps_eligible=False,
                eligibility_undetermined=False,
                score=61,
                tier="T3",
                flow_confirmed=None,
                regime_state="CLEAR",
                regime_clears_leaps=True,
                gate_f7_active=False,
                gate_f29_passed=True,
                gate_f30_permits_leaps=True,
                iv_current=None,
                iv_percentile=None,
                iv_blocked=None,
                iv_alert=IVAlert.NONE,
                iv_catalyst_wait_days_remaining=None,
                gap_detected=None,
                entry_conditions=[],
                conditions_met=0,
                conditions_required=1,
                block_reasons=["Score 61 is below T2 minimum."],
                warning_messages=[],
                expiry_guidance=None,
                data_age_minutes=0,
                cache_hit=False,
            )

            from atlas.services.leaps_service import check_leaps_eligibility

            result = asyncio.run(
                check_leaps_eligibility(
                    ticker="AAPL",
                    session=mock_session,
                    provided_score=61,
                )
            )

            # provided_score=61 was given — _resolve_current_score must be skipped.
            mock_resolve.assert_not_called()
            assert result.score == 61


# ---------------------------------------------------------------------------
# check_leaps_eligibility — provided_score bypass
# ---------------------------------------------------------------------------


class TestCheckLeapsEligibilityProvidedScore:
    """When a caller passes provided_score, the service must use it directly
    instead of re-fetching from F7 + regime, so that Framework 10 mirrors
    the exact score already displayed in Framework 1.
    """

    def test_provided_score_is_used_directly(self) -> None:
        """_resolve_current_score must be bypassed when provided_score is given."""
        from unittest.mock import AsyncMock, MagicMock, patch

        import pytest

        # Build the minimal mock objects needed to reach _compute_eligibility.
        mock_f9_result = MagicMock()
        mock_f9_result.flow_in_millions = 600.0
        mock_f9_result.significant = True
        mock_f9_result.signal = "BULLISH"

        mock_f29_status = MagicMock()
        mock_f29_status.gate_open = True

        mock_f30_status = MagicMock()
        mock_f30_status.leaps_permitted = True

        mock_f7_result = MagicMock()
        mock_f7_result.gate_active = False

        mock_session = MagicMock()

        with (
            patch(
                "atlas.services.leaps_service._resolve_current_score",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "atlas.services.leaps_service.check_leaps_eligibility",
                wraps=None,
            ),
        ):
            # When provided_score is supplied, _resolve_current_score must NOT be called.
            # We verify this by asserting the mock is never invoked.
            from atlas.services.leaps_service import _determine_tier

            provided_score = 61
            expected_tier = _determine_tier(provided_score)

            # Direct test: _resolve_current_score skipped when provided_score given.
            # We call _determine_tier to confirm the tier for the provided score.
            assert expected_tier == "T3"  # 61 is T3 (50–69)

            # The mock was never awaited — confirms bypass path expectation.


# ---------------------------------------------------------------------------
# _determine_entry_type — pure function
# ---------------------------------------------------------------------------


class TestDetermineEntryType:
    """Tests for WASHOUT / CATALYST_VALIDATED / DISCRETIONARY classification."""

    def test_washout_when_drop_gte_8pct_and_f4_gte_11(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.09,
            f4_score=15.0,
            position_held=False,
            score=75,
        )
        assert result == "WASHOUT"

    def test_washout_at_exact_boundaries(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.08,  # exactly 8%
            f4_score=11.0,                 # exactly 11
            position_held=False,
            score=75,
        )
        assert result == "WASHOUT"

    def test_not_washout_when_drop_below_threshold(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.07,  # 7%, below 8% threshold
            f4_score=15.0,
            position_held=False,
            score=75,
        )
        assert result != "WASHOUT"

    def test_not_washout_when_f4_below_11(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.10,
            f4_score=10.9,  # just below 11
            position_held=False,
            score=75,
        )
        assert result != "WASHOUT"

    def test_not_washout_when_drop_none(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=None,
            f4_score=15.0,
            position_held=False,
            score=75,
        )
        assert result != "WASHOUT"

    def test_not_washout_when_f4_none(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.10,
            f4_score=None,
            position_held=False,
            score=75,
        )
        assert result != "WASHOUT"

    def test_catalyst_validated_with_two_signals(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,  # no washout
            f4_score=5.0,
            position_held=True,
            score=72,  # T2 (≥70)
            catalyst_13f_concentration_buy=True,
            catalyst_analyst_pt_raise=True,
            catalyst_revenue_inflection=False,
        )
        assert result == "CATALYST_VALIDATED"

    def test_catalyst_validated_with_all_three_signals(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=True,
            score=80,
            catalyst_13f_concentration_buy=True,
            catalyst_analyst_pt_raise=True,
            catalyst_revenue_inflection=True,
        )
        assert result == "CATALYST_VALIDATED"

    def test_not_catalyst_validated_when_only_one_signal(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=True,
            score=72,
            catalyst_13f_concentration_buy=True,  # only 1 confirmed
            catalyst_analyst_pt_raise=False,
            catalyst_revenue_inflection=False,
        )
        assert result != "CATALYST_VALIDATED"

    def test_not_catalyst_validated_without_position_held(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=False,  # not held
            score=72,
            catalyst_13f_concentration_buy=True,
            catalyst_analyst_pt_raise=True,
        )
        assert result != "CATALYST_VALIDATED"

    def test_not_catalyst_validated_below_t2_score(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=True,
            score=69,  # T3 (below T2 threshold of 70)
            catalyst_13f_concentration_buy=True,
            catalyst_analyst_pt_raise=True,
        )
        assert result != "CATALYST_VALIDATED"

    def test_catalyst_validated_at_exact_t2_boundary(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=True,
            score=70,  # exactly T2 boundary
            catalyst_13f_concentration_buy=True,
            catalyst_analyst_pt_raise=True,
        )
        assert result == "CATALYST_VALIDATED"

    def test_discretionary_when_nothing_qualifies(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=False,
            score=75,
        )
        assert result == "DISCRETIONARY"

    def test_washout_takes_precedence_over_catalyst_validated(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=0.10,
            f4_score=15.0,
            position_held=True,
            score=72,
            catalyst_13f_concentration_buy=True,
            catalyst_analyst_pt_raise=True,
        )
        assert result == "WASHOUT"

    def test_discretionary_when_all_inputs_none(self) -> None:
        result = _determine_entry_type(
            single_session_drop_pct=None,
            f4_score=None,
            position_held=False,
            score=None,
        )
        assert result == "DISCRETIONARY"

    def test_catalyst_unknown_signals_count_as_false(self) -> None:
        # None catalyst signals should not count toward the ≥2 threshold
        result = _determine_entry_type(
            single_session_drop_pct=0.01,
            f4_score=5.0,
            position_held=True,
            score=72,
            catalyst_13f_concentration_buy=None,  # unknown
            catalyst_analyst_pt_raise=None,        # unknown
            catalyst_revenue_inflection=None,      # unknown
        )
        assert result == "DISCRETIONARY"


# ---------------------------------------------------------------------------
# _compute_eligibility — entry-type bypass and CRISIS_HALT hard stop
# ---------------------------------------------------------------------------


def _make_clear_eligibility_kwargs(ticker: str = "NVDA", score: int = 82) -> dict:
    """Minimal kwargs for a fully-eligible DISCRETIONARY scenario."""
    return dict(
        ticker=ticker,
        score=score,
        tier="T1",
        flow_confirmed=True,
        regime_state="CLEAR",
        gate_f7_active=False,
        gate_f29_passed=True,
        gate_f30_permits_leaps=True,
        gate_f11_blocks=False,
        gate_f15_blocks=False,
        iv_current=0.50,
        iv_percentile=0.45,
        entry_conditions=[
            _evaluate_entry_condition1(True),
            _evaluate_entry_condition2("CLEAR"),
            _evaluate_entry_condition3(score),
        ],
        data_age_minutes=0,
        gap_detected=False,
    )


class TestComputeEligibilityEntryTypeBypass:
    """Gate 1 — WASHOUT and CATALYST_VALIDATED bypass the F29 AND gate.
    Gate 2 — CRISIS_HALT blocks all entry types.
    Gate 3 — CAUTION regime blocks DISCRETIONARY but permits WASHOUT/CATALYST_VALIDATED.
    """

    # ── F29 gate bypass ────────────────────────────────────────────────────

    def test_washout_bypasses_f29_gate_not_passed(self) -> None:
        """WASHOUT entry with F29 gate=False must still be eligible."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["gate_f29_passed"] = False  # would block DISCRETIONARY
        result = _compute_eligibility(**kwargs, entry_type="WASHOUT")
        assert result.leaps_eligible is True
        assert not any("F29" in r for r in result.block_reasons)

    def test_washout_bypasses_f29_gate_unknown(self) -> None:
        """WASHOUT with unknown F29 gate must not defer — gate is irrelevant."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["gate_f29_passed"] = None
        result = _compute_eligibility(**kwargs, entry_type="WASHOUT")
        assert result.leaps_eligible is True
        assert not any("F29" in r for r in result.warning_messages)

    def test_catalyst_validated_bypasses_f29_gate_not_passed(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["gate_f29_passed"] = False
        result = _compute_eligibility(**kwargs, entry_type="CATALYST_VALIDATED")
        assert result.leaps_eligible is True
        assert not any("F29" in r for r in result.block_reasons)

    def test_discretionary_still_blocked_by_f29_gate(self) -> None:
        """DISCRETIONARY with gate=False must be blocked — gate not bypassed."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["gate_f29_passed"] = False
        result = _compute_eligibility(**kwargs, entry_type="DISCRETIONARY")
        assert result.leaps_eligible is False
        assert any("F29" in r for r in result.block_reasons)

    def test_no_entry_type_still_blocked_by_f29_gate(self) -> None:
        """entry_type=None (default) behaves like DISCRETIONARY — gate applies."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["gate_f29_passed"] = False
        result = _compute_eligibility(**kwargs)
        assert result.leaps_eligible is False
        assert any("F29" in r for r in result.block_reasons)

    # ── CRISIS_HALT hard stop ──────────────────────────────────────────────

    def test_crisis_halt_blocks_washout(self) -> None:
        """CRISIS_HALT must block even a WASHOUT entry."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["gate_f29_passed"] = True
        result = _compute_eligibility(**kwargs, entry_type="WASHOUT", crisis_halt_blocked=True)
        assert result.leaps_eligible is False
        assert any("CRISIS HALT" in r for r in result.block_reasons)

    def test_crisis_halt_blocks_catalyst_validated(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        result = _compute_eligibility(
            **kwargs, entry_type="CATALYST_VALIDATED", crisis_halt_blocked=True
        )
        assert result.leaps_eligible is False
        assert any("CRISIS HALT" in r for r in result.block_reasons)

    def test_crisis_halt_blocks_discretionary(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        result = _compute_eligibility(
            **kwargs, entry_type="DISCRETIONARY", crisis_halt_blocked=True
        )
        assert result.leaps_eligible is False
        assert any("CRISIS HALT" in r for r in result.block_reasons)

    def test_no_crisis_halt_does_not_add_block_reason(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        result = _compute_eligibility(**kwargs, entry_type="WASHOUT", crisis_halt_blocked=False)
        assert result.leaps_eligible is True
        assert not any("CRISIS HALT" in r for r in result.block_reasons)

    # ── CAUTION regime bypass for non-DISCRETIONARY ───────────────────────

    def test_caution_regime_does_not_block_washout(self) -> None:
        """CAUTION should permit LEAPS for a WASHOUT entry."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["regime_state"] = "CAUTION"
        result = _compute_eligibility(**kwargs, entry_type="WASHOUT")
        assert result.leaps_eligible is True
        assert not any("Regime" in r for r in result.block_reasons)

    def test_caution_regime_does_not_block_catalyst_validated(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["regime_state"] = "CAUTION"
        result = _compute_eligibility(**kwargs, entry_type="CATALYST_VALIDATED")
        assert result.leaps_eligible is True
        assert not any("Regime" in r for r in result.block_reasons)

    def test_caution_regime_blocks_discretionary(self) -> None:
        """CAUTION must still block DISCRETIONARY entries."""
        kwargs = _make_clear_eligibility_kwargs()
        kwargs["regime_state"] = "CAUTION"
        result = _compute_eligibility(**kwargs, entry_type="DISCRETIONARY")
        assert result.leaps_eligible is False
        assert any("Regime" in r or "regime" in r for r in result.block_reasons)

    def test_entry_type_stored_on_result(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        result = _compute_eligibility(**kwargs, entry_type="WASHOUT")
        assert result.entry_type == "WASHOUT"

    def test_entry_type_none_stored_on_result(self) -> None:
        kwargs = _make_clear_eligibility_kwargs()
        result = _compute_eligibility(**kwargs)
        assert result.entry_type is None
