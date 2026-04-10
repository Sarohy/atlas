"""Unit tests for AnalystService — pure calculation functions.

All Polygon HTTP calls are mocked; these tests cover only the computation
logic that is deterministic from a known input.

F3 Analyst Conviction sub-indicators (0-20 pts each, total 0-100):
  1. Consensus Rating    — buy/hold/sell analyst breakdown
  2. PT Upside           — % upside from current price to consensus price target
  3. PT Direction        — whether the consensus PT is being raised or cut
  4. Analyst Coverage    — number of analysts covering the stock
  5. Recent Upgrades     — net upgrade/downgrade balance in the last 90 days
"""

from __future__ import annotations

import pytest

from atlas.services.analyst_service import (
    _compute_consensus_rating,
    _compute_net_upgrades,
    _compute_pt_direction,
    _compute_pt_upside,
    _grade_from_total,
    _score_analyst_coverage,
    _score_consensus,
    _score_net_upgrades,
    _score_pt_direction,
    _score_pt_upside,
)

# ---------------------------------------------------------------------------
# Consensus rating
# ---------------------------------------------------------------------------


class TestComputeConsensusRating:
    def test_all_buy_returns_strong_buy_label(self) -> None:
        label, buy_pct = _compute_consensus_rating(buy=10, hold=0, sell=0)
        assert label == "STRONG BUY"
        assert buy_pct == 100.0

    def test_all_sell_returns_sell_label(self) -> None:
        label, buy_pct = _compute_consensus_rating(buy=0, hold=0, sell=10)
        assert label == "SELL"
        assert buy_pct == 0.0

    def test_majority_buy_returns_buy_label(self) -> None:
        label, buy_pct = _compute_consensus_rating(buy=6, hold=3, sell=1)
        assert label == "BUY"
        assert abs(buy_pct - 60.0) < 0.01

    def test_majority_hold_returns_hold_label(self) -> None:
        label, buy_pct = _compute_consensus_rating(buy=3, hold=6, sell=1)
        assert label == "HOLD"
        assert abs(buy_pct - 30.0) < 0.01

    def test_zero_analysts_returns_no_data(self) -> None:
        label, buy_pct = _compute_consensus_rating(buy=0, hold=0, sell=0)
        assert label == "NO DATA"
        assert buy_pct is None

    def test_exact_70_pct_buy_is_strong_buy(self) -> None:
        label, buy_pct = _compute_consensus_rating(buy=7, hold=2, sell=1)
        assert label == "STRONG BUY"


class TestScoreConsensus:
    def test_100_pct_buy_scores_20(self) -> None:
        assert _score_consensus(100.0) == 20

    def test_70_pct_buy_scores_20(self) -> None:
        assert _score_consensus(70.0) == 20

    def test_60_pct_buy_scores_15(self) -> None:
        assert _score_consensus(60.0) == 15

    def test_50_pct_buy_scores_15(self) -> None:
        assert _score_consensus(50.0) == 15

    def test_40_pct_buy_scores_10(self) -> None:
        assert _score_consensus(40.0) == 10

    def test_30_pct_buy_scores_10(self) -> None:
        assert _score_consensus(30.0) == 10

    def test_25_pct_buy_scores_5(self) -> None:
        assert _score_consensus(25.0) == 5

    def test_10_pct_buy_scores_0(self) -> None:
        assert _score_consensus(10.0) == 0

    def test_none_returns_0(self) -> None:
        assert _score_consensus(None) == 0


# ---------------------------------------------------------------------------
# Price target upside
# ---------------------------------------------------------------------------


class TestComputePtUpside:
    def test_positive_upside(self) -> None:
        result = _compute_pt_upside(current_price=100.0, consensus_pt=130.0)
        assert abs(result - 30.0) < 0.01

    def test_negative_upside_downside(self) -> None:
        result = _compute_pt_upside(current_price=100.0, consensus_pt=85.0)
        assert abs(result - (-15.0)) < 0.01

    def test_price_equal_to_pt_is_zero(self) -> None:
        result = _compute_pt_upside(current_price=100.0, consensus_pt=100.0)
        assert result == 0.0

    def test_zero_current_price_returns_none(self) -> None:
        assert _compute_pt_upside(current_price=0.0, consensus_pt=150.0) is None

    def test_none_current_price_returns_none(self) -> None:
        assert _compute_pt_upside(current_price=None, consensus_pt=150.0) is None

    def test_none_consensus_pt_returns_none(self) -> None:
        assert _compute_pt_upside(current_price=100.0, consensus_pt=None) is None


class TestScorePtUpside:
    def test_30_pct_upside_scores_20(self) -> None:
        assert _score_pt_upside(30.0) == 20

    def test_25_pct_upside_scores_20(self) -> None:
        assert _score_pt_upside(25.0) == 20

    def test_15_pct_upside_scores_15(self) -> None:
        assert _score_pt_upside(15.0) == 15

    def test_10_pct_upside_scores_15(self) -> None:
        assert _score_pt_upside(10.0) == 15

    def test_7_pct_upside_scores_10(self) -> None:
        assert _score_pt_upside(7.0) == 10

    def test_5_pct_upside_scores_10(self) -> None:
        assert _score_pt_upside(5.0) == 10

    def test_2_pct_upside_scores_5(self) -> None:
        assert _score_pt_upside(2.0) == 5

    def test_negative_scores_0(self) -> None:
        assert _score_pt_upside(-5.0) == 0

    def test_none_returns_0(self) -> None:
        assert _score_pt_upside(None) == 0


# ---------------------------------------------------------------------------
# Price target direction
# ---------------------------------------------------------------------------


class TestComputePtDirection:
    def test_raised_pt_positive(self) -> None:
        result = _compute_pt_direction(current_pt=220.0, prior_pt=200.0)
        assert abs(result - 10.0) < 0.01  # 10% raise

    def test_cut_pt_negative(self) -> None:
        result = _compute_pt_direction(current_pt=180.0, prior_pt=200.0)
        assert abs(result - (-10.0)) < 0.01  # 10% cut

    def test_flat_pt_zero(self) -> None:
        result = _compute_pt_direction(current_pt=200.0, prior_pt=200.0)
        assert result == 0.0

    def test_zero_prior_returns_none(self) -> None:
        assert _compute_pt_direction(current_pt=200.0, prior_pt=0.0) is None

    def test_none_inputs_return_none(self) -> None:
        assert _compute_pt_direction(None, 200.0) is None
        assert _compute_pt_direction(200.0, None) is None


class TestScorePtDirection:
    def test_strong_raise_scores_20(self) -> None:
        assert _score_pt_direction(10.0) == 20

    def test_mild_raise_scores_15(self) -> None:
        assert _score_pt_direction(2.0) == 15

    def test_flat_scores_10(self) -> None:
        assert _score_pt_direction(0.0) == 10

    def test_slight_cut_scores_5(self) -> None:
        assert _score_pt_direction(-2.0) == 5

    def test_strong_cut_scores_0(self) -> None:
        assert _score_pt_direction(-10.0) == 0

    def test_none_returns_10(self) -> None:
        # No historical PT data → neutral
        assert _score_pt_direction(None) == 10


# ---------------------------------------------------------------------------
# Analyst coverage
# ---------------------------------------------------------------------------


class TestScoreAnalystCoverage:
    def test_20_analysts_scores_20(self) -> None:
        assert _score_analyst_coverage(20) == 20

    def test_25_analysts_scores_20(self) -> None:
        assert _score_analyst_coverage(25) == 20

    def test_10_analysts_scores_15(self) -> None:
        assert _score_analyst_coverage(10) == 15

    def test_5_analysts_scores_10(self) -> None:
        assert _score_analyst_coverage(5) == 10

    def test_2_analysts_scores_5(self) -> None:
        assert _score_analyst_coverage(2) == 5

    def test_1_analyst_scores_0(self) -> None:
        assert _score_analyst_coverage(1) == 0

    def test_0_analysts_scores_0(self) -> None:
        assert _score_analyst_coverage(0) == 0

    def test_none_returns_0(self) -> None:
        assert _score_analyst_coverage(None) == 0


# ---------------------------------------------------------------------------
# Net upgrades
# ---------------------------------------------------------------------------


class TestComputeNetUpgrades:
    def test_more_upgrades_than_downgrades(self) -> None:
        assert _compute_net_upgrades(upgrades=5, downgrades=1) == 4

    def test_more_downgrades_than_upgrades(self) -> None:
        assert _compute_net_upgrades(upgrades=1, downgrades=4) == -3

    def test_equal_upgrades_and_downgrades(self) -> None:
        assert _compute_net_upgrades(upgrades=2, downgrades=2) == 0

    def test_no_activity_is_zero(self) -> None:
        assert _compute_net_upgrades(upgrades=0, downgrades=0) == 0


class TestScoreNetUpgrades:
    def test_strong_net_upgrades_scores_20(self) -> None:
        assert _score_net_upgrades(3) == 20

    def test_single_net_upgrade_scores_15(self) -> None:
        assert _score_net_upgrades(1) == 15

    def test_flat_scores_10(self) -> None:
        assert _score_net_upgrades(0) == 10

    def test_mild_downgrades_scores_5(self) -> None:
        assert _score_net_upgrades(-2) == 5

    def test_strong_downgrades_scores_0(self) -> None:
        assert _score_net_upgrades(-3) == 0

    def test_none_returns_10(self) -> None:
        # No recent action data → neutral
        assert _score_net_upgrades(None) == 10


# ---------------------------------------------------------------------------
# F3 composite grade
# ---------------------------------------------------------------------------


class TestF3Grade:
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
