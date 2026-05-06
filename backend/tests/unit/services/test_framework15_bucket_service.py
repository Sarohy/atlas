"""Unit tests for Framework 15 Three-Bucket Allocation pure functions.

Tests are organised by class — one class per pure function.
All tests are deterministic and side-effect-free (no I/O, no DB).

TDD RED phase: all tests reference symbols that do not yet exist in the service.
"""

from __future__ import annotations

import pytest

from atlas.services.framework15_service import (
    check_bucket1_add_conditions,
    check_bucket3_satellite_eligible,
    classify_position_bucket,
    compute_aggregate_gtc_exposure,
    compute_bucket_weights,
    get_regime_floor_pct,
)


# ---------------------------------------------------------------------------
# TestClassifyPositionBucket
# ---------------------------------------------------------------------------


class TestClassifyPositionBucket:
    def test_leaps_classified_b2_regardless_of_high_score(self) -> None:
        assert classify_position_bucket(90, is_leaps=True) == "B2"

    def test_leaps_classified_b2_when_score_none(self) -> None:
        assert classify_position_bucket(None, is_leaps=True) == "B2"

    def test_leaps_classified_b2_when_score_low(self) -> None:
        assert classify_position_bucket(30, is_leaps=True) == "B2"

    def test_score_70_is_b1(self) -> None:
        assert classify_position_bucket(70, is_leaps=False) == "B1"

    def test_score_above_70_is_b1(self) -> None:
        assert classify_position_bucket(85, is_leaps=False) == "B1"

    def test_score_100_is_b1(self) -> None:
        assert classify_position_bucket(100, is_leaps=False) == "B1"

    def test_score_69_is_b3(self) -> None:
        assert classify_position_bucket(69, is_leaps=False) == "B3"

    def test_score_below_70_is_b3(self) -> None:
        assert classify_position_bucket(55, is_leaps=False) == "B3"

    def test_score_zero_is_b3(self) -> None:
        assert classify_position_bucket(0, is_leaps=False) == "B3"

    def test_score_none_non_leaps_is_unclassified(self) -> None:
        assert classify_position_bucket(None, is_leaps=False) is None

    def test_score_exactly_70_boundary_is_b1(self) -> None:
        assert classify_position_bucket(70, is_leaps=False) == "B1"


# ---------------------------------------------------------------------------
# TestComputeBucketWeights
# ---------------------------------------------------------------------------


class TestComputeBucketWeights:
    def test_basic_three_bucket_allocation(self) -> None:
        positions = [
            {"bucket": "B1", "position_value": 75_000.0},
            {"bucket": "B2", "position_value": 3_500.0},
            {"bucket": "B3", "position_value": 4_000.0},
        ]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b1_weight_pct == pytest.approx(75.0)
        assert result.b2_weight_pct == pytest.approx(3.5)
        assert result.b3_weight_pct == pytest.approx(4.0)
        assert result.unclassified_weight_pct == pytest.approx(0.0)

    def test_unclassified_positions_tracked(self) -> None:
        positions = [
            {"bucket": "B1", "position_value": 70_000.0},
            {"bucket": None, "position_value": 10_000.0},
        ]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b1_weight_pct == pytest.approx(70.0)
        assert result.unclassified_weight_pct == pytest.approx(10.0)

    def test_empty_positions_returns_zeros(self) -> None:
        result = compute_bucket_weights([], total_nav=100_000.0)
        assert result.b1_weight_pct == 0.0
        assert result.b2_weight_pct == 0.0
        assert result.b3_weight_pct == 0.0
        assert result.unclassified_weight_pct == 0.0

    def test_zero_nav_returns_zeros(self) -> None:
        positions = [{"bucket": "B1", "position_value": 5_000.0}]
        result = compute_bucket_weights(positions, total_nav=0.0)
        assert result.b1_weight_pct == 0.0

    def test_b2_at_cap_flag_when_exactly_4_pct(self) -> None:
        positions = [{"bucket": "B2", "position_value": 4_000.0}]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b2_at_cap is True

    def test_b2_not_at_cap_just_below_4_pct(self) -> None:
        # 3999 / 100000 = 3.999 % — raw check must not fire the cap
        positions = [{"bucket": "B2", "position_value": 3_999.0}]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b2_at_cap is False

    def test_b3_at_cap_flag_when_exactly_5_pct(self) -> None:
        positions = [{"bucket": "B3", "position_value": 5_000.0}]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b3_at_cap is True

    def test_b1_at_target_flag_when_in_range(self) -> None:
        positions = [{"bucket": "B1", "position_value": 78_000.0}]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b1_at_target is True

    def test_b1_below_target_flag_when_under_75_pct(self) -> None:
        positions = [{"bucket": "B1", "position_value": 70_000.0}]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b1_below_target is True

    def test_b1_above_82_pct_not_at_target(self) -> None:
        positions = [{"bucket": "B1", "position_value": 85_000.0}]
        result = compute_bucket_weights(positions, total_nav=100_000.0)
        assert result.b1_below_target is False
        assert result.b1_at_target is False


# ---------------------------------------------------------------------------
# TestCheckBucket3SatelliteEligible
# ---------------------------------------------------------------------------


class TestCheckBucket3SatelliteEligible:
    def test_score_60_eligible_after_caution_modifier(self) -> None:
        # 60 - 5 = 55 → exactly at threshold → eligible
        assert check_bucket3_satellite_eligible(60) is True

    def test_score_59_not_eligible(self) -> None:
        # 59 - 5 = 54 → below threshold
        assert check_bucket3_satellite_eligible(59) is False

    def test_score_55_not_eligible(self) -> None:
        # 55 - 5 = 50 → below threshold
        assert check_bucket3_satellite_eligible(55) is False

    def test_score_100_eligible(self) -> None:
        assert check_bucket3_satellite_eligible(100) is True

    def test_score_61_eligible(self) -> None:
        # 61 - 5 = 56 → above threshold
        assert check_bucket3_satellite_eligible(61) is True


# ---------------------------------------------------------------------------
# TestGetRegimeFloorPct
# ---------------------------------------------------------------------------


class TestGetRegimeFloorPct:
    def test_clear_regime(self) -> None:
        assert get_regime_floor_pct("CLEAR") == pytest.approx(0.08)

    def test_soft_caution_regime(self) -> None:
        assert get_regime_floor_pct("SOFT_CAUTION") == pytest.approx(0.15)

    def test_caution_regime(self) -> None:
        assert get_regime_floor_pct("CAUTION") == pytest.approx(0.20)

    def test_crisis_regime(self) -> None:
        assert get_regime_floor_pct("CRISIS") == pytest.approx(0.30)

    def test_crisis_halt_regime(self) -> None:
        assert get_regime_floor_pct("CRISIS_HALT") == pytest.approx(0.30)

    def test_none_regime_returns_conservative(self) -> None:
        assert get_regime_floor_pct(None) == pytest.approx(0.30)

    def test_unknown_string_returns_conservative(self) -> None:
        assert get_regime_floor_pct("UNKNOWN_REGIME") == pytest.approx(0.30)

    def test_lowercase_normalised(self) -> None:
        assert get_regime_floor_pct("clear") == pytest.approx(0.08)


# ---------------------------------------------------------------------------
# TestComputeAggregateGtcExposure
# ---------------------------------------------------------------------------


class TestComputeAggregateGtcExposure:
    def test_near_money_order_counts_toward_aggregate(self) -> None:
        # limit 95 vs market 100 → 5 % below → near-money
        orders = [{"ticker": "MU", "limit_price": 95.0, "quantity": 100}]
        prices = {"MU": 100.0}
        result = compute_aggregate_gtc_exposure(
            orders, prices, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.near_gtc_usd == pytest.approx(9_500.0)
        assert result.deep_otm_gtc_usd == pytest.approx(0.0)

    def test_deep_otm_order_exempt_from_aggregate(self) -> None:
        # limit 80 vs market 100 → 20 % below → deep-OTM, exempt
        orders = [{"ticker": "NVDA", "limit_price": 80.0, "quantity": 10}]
        prices = {"NVDA": 100.0}
        result = compute_aggregate_gtc_exposure(
            orders, prices, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.near_gtc_usd == pytest.approx(0.0)
        assert result.deep_otm_gtc_usd == pytest.approx(800.0)

    def test_exactly_8_pct_below_is_near_money(self) -> None:
        # 92 / 100 = 8 % below — spec says "> 8 %" is deep-OTM, so 8 % is near-money
        orders = [{"ticker": "AAPL", "limit_price": 92.0, "quantity": 100}]
        prices = {"AAPL": 100.0}
        result = compute_aggregate_gtc_exposure(
            orders, prices, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.near_gtc_usd == pytest.approx(9_200.0)

    def test_just_over_8_pct_below_is_deep_otm(self) -> None:
        # 91 / 100 = 9 % below → deep-OTM
        orders = [{"ticker": "AAPL", "limit_price": 91.0, "quantity": 100}]
        prices = {"AAPL": 100.0}
        result = compute_aggregate_gtc_exposure(
            orders, prices, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.near_gtc_usd == pytest.approx(0.0)
        assert result.deep_otm_gtc_usd == pytest.approx(9_100.0)

    def test_max_aggregate_formula_soft_caution(self) -> None:
        # SOFT_CAUTION floor = 0.15
        # max = 50000 - (1.1 × 0.15 × 200000) = 50000 - 33000 = 17000
        result = compute_aggregate_gtc_exposure(
            [], {}, cash_usd=50_000.0, total_nav=200_000.0, regime="SOFT_CAUTION"
        )
        assert result.max_aggregate_usd == pytest.approx(17_000.0)
        assert result.regime_floor_pct == pytest.approx(0.15)

    def test_max_aggregate_formula_clear(self) -> None:
        # CLEAR floor = 0.08
        # max = 50000 - (1.1 × 0.08 × 200000) = 50000 - 17600 = 32400
        result = compute_aggregate_gtc_exposure(
            [], {}, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.max_aggregate_usd == pytest.approx(32_400.0)

    def test_window_negative_and_not_ok_when_over_max(self) -> None:
        # near = 95000, max = 32400 → window = -62600
        orders = [{"ticker": "MU", "limit_price": 95.0, "quantity": 1000}]
        prices = {"MU": 100.0}
        result = compute_aggregate_gtc_exposure(
            orders, prices, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.window_usd < 0
        assert result.window_ok is False

    def test_order_with_unknown_price_excluded(self) -> None:
        orders = [{"ticker": "XYZ", "limit_price": 50.0, "quantity": 100}]
        prices: dict[str, float | None] = {}
        result = compute_aggregate_gtc_exposure(
            orders, prices, cash_usd=50_000.0, total_nav=200_000.0, regime="CLEAR"
        )
        assert result.near_gtc_usd == pytest.approx(0.0)
        assert result.deep_otm_gtc_usd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestCheckBucket1AddConditions
# ---------------------------------------------------------------------------


class TestCheckBucket1AddConditions:
    def test_all_conditions_met_returns_eligible(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="SOFT_CAUTION",
            dark_pool_total_usd=600_000.0,
        )
        assert result.eligible is True
        assert result.regime_ok is True
        assert result.dark_pool_ok is True
        assert result.underweight_ok is True
        assert result.soft_cap_ok is True
        assert result.reasons_blocked == []

    def test_crisis_regime_blocks(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="CRISIS",
            dark_pool_total_usd=600_000.0,
        )
        assert result.eligible is False
        assert result.regime_ok is False
        assert any("regime" in r.lower() for r in result.reasons_blocked)

    def test_caution_regime_blocks(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="CAUTION",
            dark_pool_total_usd=600_000.0,
        )
        assert result.eligible is False
        assert result.regime_ok is False

    def test_dark_pool_below_500k_blocks(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=400_000.0,
        )
        assert result.eligible is False
        assert result.dark_pool_ok is False

    def test_dark_pool_none_blocks(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=None,
        )
        assert result.eligible is False
        assert result.dark_pool_ok is False

    def test_dark_pool_exactly_500k_does_not_qualify(self) -> None:
        # Must be STRICTLY GREATER than $500K
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=500_000.0,
        )
        assert result.dark_pool_ok is False

    def test_not_underweight_enough_blocks(self) -> None:
        # gap = 5.0 - 4.8 = 0.2 % < 0.5 %
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=4.8,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=600_000.0,
        )
        assert result.eligible is False
        assert result.underweight_ok is False

    def test_exactly_0_5_pct_underweight_qualifies(self) -> None:
        # gap = 5.0 - 4.5 = 0.5 % → exactly at threshold → qualifies
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=4.5,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=600_000.0,
        )
        assert result.underweight_ok is True

    def test_weight_at_soft_cap_blocks(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=8.0,
            target_min_pct=10.0,
            regime="CLEAR",
            dark_pool_total_usd=600_000.0,
        )
        assert result.eligible is False
        assert result.soft_cap_ok is False

    def test_weight_none_blocks_underweight_check(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=None,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=600_000.0,
        )
        assert result.eligible is False
        assert result.underweight_ok is False

    def test_multiple_failures_reported(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=None,
            target_min_pct=5.0,
            regime="CRISIS",
            dark_pool_total_usd=None,
        )
        assert result.eligible is False
        assert len(result.reasons_blocked) >= 2

    def test_clear_regime_ok(self) -> None:
        result = check_bucket1_add_conditions(
            ticker="AAPL",
            current_weight_pct=3.0,
            target_min_pct=5.0,
            regime="CLEAR",
            dark_pool_total_usd=600_000.0,
        )
        assert result.regime_ok is True
