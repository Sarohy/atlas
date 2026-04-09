"""Unit tests for EarningsService — pure calculation functions.

All Polygon HTTP calls are mocked; these tests cover only the computation
logic that is deterministic from a known input.

F2 Earnings Quality sub-indicators (0-20 pts each, total 0-100):
  1. Revenue Growth      — YoY revenue change
  2. EPS Beats           — beats vs consensus in last 4 quarters
  3. Guidance Raises     — estimated from EPS revision trend
  4. Backlog / BTB       — book-to-bill proxy from gross-margin direction
  5. Margin Trajectory   — gross-margin direction over trailing quarters
"""

from __future__ import annotations

import pytest

from atlas.services.earnings_service import (
    _compute_eps_beat_rate,
    _compute_guidance_score,
    _compute_margin_trajectory,
    _compute_revenue_growth,
    _grade_from_total,
    _score_eps_beats,
    _score_guidance,
    _score_margin_trajectory,
    _score_revenue_growth,
)

# ---------------------------------------------------------------------------
# Revenue growth
# ---------------------------------------------------------------------------


class TestComputeRevenueGrowth:
    def test_positive_growth(self) -> None:
        result = _compute_revenue_growth(current_ttm=120.0, prior_ttm=100.0)
        assert abs(result - 20.0) < 0.01

    def test_negative_growth(self) -> None:
        result = _compute_revenue_growth(current_ttm=80.0, prior_ttm=100.0)
        assert abs(result - (-20.0)) < 0.01

    def test_flat_growth(self) -> None:
        result = _compute_revenue_growth(current_ttm=100.0, prior_ttm=100.0)
        assert result == 0.0

    def test_zero_prior_returns_none(self) -> None:
        result = _compute_revenue_growth(current_ttm=100.0, prior_ttm=0.0)
        assert result is None

    def test_none_inputs_return_none(self) -> None:
        assert _compute_revenue_growth(None, 100.0) is None
        assert _compute_revenue_growth(100.0, None) is None


class TestScoreRevenueGrowth:
    def test_high_growth_scores_20(self) -> None:
        assert _score_revenue_growth(30.0) == 20

    def test_growth_15_scores_20(self) -> None:
        assert _score_revenue_growth(15.0) == 20

    def test_growth_10_scores_15(self) -> None:
        assert _score_revenue_growth(10.0) == 15

    def test_growth_5_scores_10(self) -> None:
        assert _score_revenue_growth(5.0) == 10

    def test_growth_0_scores_5(self) -> None:
        assert _score_revenue_growth(0.0) == 5

    def test_negative_growth_scores_0(self) -> None:
        assert _score_revenue_growth(-5.0) == 0

    def test_none_returns_0(self) -> None:
        assert _score_revenue_growth(None) == 0


# ---------------------------------------------------------------------------
# EPS beats
# ---------------------------------------------------------------------------


class TestComputeEpsBeatRate:
    def test_all_beats(self) -> None:
        # actual > estimate for all four quarters
        actuals = [1.2, 1.5, 1.8, 2.0]
        estimates = [1.0, 1.2, 1.5, 1.7]
        rate = _compute_eps_beat_rate(actuals, estimates)
        assert rate == 100.0

    def test_no_beats(self) -> None:
        actuals = [0.8, 1.0, 1.2, 1.4]
        estimates = [1.0, 1.2, 1.5, 1.7]
        rate = _compute_eps_beat_rate(actuals, estimates)
        assert rate == 0.0

    def test_half_beats(self) -> None:
        actuals = [1.2, 0.9, 1.8, 1.3]
        estimates = [1.0, 1.0, 1.5, 1.5]
        rate = _compute_eps_beat_rate(actuals, estimates)
        assert rate == 50.0

    def test_empty_lists_return_none(self) -> None:
        assert _compute_eps_beat_rate([], []) is None

    def test_mismatched_length_raises(self) -> None:
        with pytest.raises(ValueError, match="length"):
            _compute_eps_beat_rate([1.0, 1.2], [1.0])


class TestScoreEpsBeats:
    def test_100_pct_beats_scores_20(self) -> None:
        assert _score_eps_beats(100.0) == 20

    def test_75_pct_beats_scores_15(self) -> None:
        assert _score_eps_beats(75.0) == 15

    def test_50_pct_beats_scores_10(self) -> None:
        assert _score_eps_beats(50.0) == 10

    def test_25_pct_beats_scores_5(self) -> None:
        assert _score_eps_beats(25.0) == 5

    def test_0_pct_beats_scores_0(self) -> None:
        assert _score_eps_beats(0.0) == 0

    def test_none_returns_0(self) -> None:
        assert _score_eps_beats(None) == 0


# ---------------------------------------------------------------------------
# Guidance raises (derived from EPS revision trend)
# ---------------------------------------------------------------------------


class TestComputeGuidanceScore:
    def test_consistently_rising_estimates_scores_high(self) -> None:
        # estimates have been raised each revision → score should be high
        revised_estimates = [1.0, 1.1, 1.2, 1.4]
        score = _compute_guidance_score(revised_estimates)
        assert score >= 15

    def test_consistently_falling_estimates_scores_low(self) -> None:
        revised_estimates = [1.4, 1.2, 1.0, 0.9]
        score = _compute_guidance_score(revised_estimates)
        assert score <= 5

    def test_flat_estimates_scores_neutral(self) -> None:
        revised_estimates = [1.0, 1.0, 1.0, 1.0]
        score = _compute_guidance_score(revised_estimates)
        assert score == 10

    def test_empty_list_returns_0(self) -> None:
        assert _compute_guidance_score([]) == 0

    def test_single_value_returns_0(self) -> None:
        # cannot compute revision trend with a single data point
        assert _compute_guidance_score([1.0]) == 0


class TestScoreGuidance:
    def test_strong_raise_20(self) -> None:
        assert _score_guidance(2) == 20

    def test_mild_raise_15(self) -> None:
        assert _score_guidance(1) == 15

    def test_flat_10(self) -> None:
        assert _score_guidance(0) == 10

    def test_mild_cut_5(self) -> None:
        assert _score_guidance(-1) == 5

    def test_strong_cut_0(self) -> None:
        assert _score_guidance(-2) == 0


# ---------------------------------------------------------------------------
# Margin trajectory
# ---------------------------------------------------------------------------


class TestComputeMarginTrajectory:
    def test_expanding_margins_positive_direction(self) -> None:
        # gross margins increasing each quarter
        gross_margins = [0.30, 0.32, 0.34, 0.36]
        direction = _compute_margin_trajectory(gross_margins)
        assert direction > 0

    def test_contracting_margins_negative_direction(self) -> None:
        gross_margins = [0.36, 0.34, 0.32, 0.30]
        direction = _compute_margin_trajectory(gross_margins)
        assert direction < 0

    def test_flat_margins_zero_direction(self) -> None:
        gross_margins = [0.35, 0.35, 0.35, 0.35]
        direction = _compute_margin_trajectory(gross_margins)
        assert direction == 0.0

    def test_single_quarter_returns_none(self) -> None:
        assert _compute_margin_trajectory([0.35]) is None

    def test_empty_returns_none(self) -> None:
        assert _compute_margin_trajectory([]) is None


class TestScoreMarginTrajectory:
    def test_strongly_expanding_scores_20(self) -> None:
        assert _score_margin_trajectory(0.03) == 20

    def test_mildly_expanding_scores_15(self) -> None:
        assert _score_margin_trajectory(0.01) == 15

    def test_flat_within_threshold_scores_10(self) -> None:
        assert _score_margin_trajectory(0.0) == 10

    def test_mildly_contracting_scores_5(self) -> None:
        assert _score_margin_trajectory(-0.01) == 5

    def test_strongly_contracting_scores_0(self) -> None:
        assert _score_margin_trajectory(-0.03) == 0

    def test_none_returns_0(self) -> None:
        assert _score_margin_trajectory(None) == 0


# ---------------------------------------------------------------------------
# F2 composite grade
# ---------------------------------------------------------------------------


class TestF2Grade:
    def test_strong_buy_at_80(self) -> None:
        assert _grade_from_total(80) == "STRONG BUY"

    def test_buy_at_60(self) -> None:
        assert _grade_from_total(60) == "BUY"

    def test_neutral_at_40(self) -> None:
        assert _grade_from_total(40) == "NEUTRAL"

    def test_weak_at_20(self) -> None:
        assert _grade_from_total(20) == "WEAK"

    def test_avoid_at_19(self) -> None:
        assert _grade_from_total(19) == "AVOID"

    def test_avoid_at_0(self) -> None:
        assert _grade_from_total(0) == "AVOID"

    def test_strong_buy_at_100(self) -> None:
        assert _grade_from_total(100) == "STRONG BUY"
