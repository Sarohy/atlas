"""Unit tests for strategy-aware adjustments in F4 options flow scoring."""

from __future__ import annotations

from atlas.services.options_flow_service import (
    _alert_dte_days,
    _apply_dark_pool_quality_boost,
    _apply_strategy_aware_adjustment,
    _build_response_v2,
    _dark_pool_settlement_ratio,
)


def test_build_response_v2_applies_strategy_adjustment_for_complex_bullish_structure() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 8_000_000.0,
                "total_bid_side_prem": 6_400_000.0,
                "total_premium": 9_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_200_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_200_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "strike": 65,
                "underlying_price": 50,
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 500_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )

    assert response.market_cap_tier == "MID"
    assert response.data_source == "OPTIONS_ONLY"
    assert response.options_net_flow_usd == 0.0
    assert response.options_flow_score == 50
    assert response.f4_score == 50
    assert response.flow_direction == "NEUTRAL"
    assert response.f4_grade == "NEUTRAL"


def test_build_response_v2_does_not_adjust_when_any_bullish_leg_is_missing() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 8_000_000.0,
                "total_bid_side_prem": 6_400_000.0,
                "total_premium": 9_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_200_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_200_000.0,
            },
        ],
    )

    assert response.options_net_flow_usd == -10_000_000.0
    assert response.options_flow_score == 17
    assert response.f4_score == 17
    assert response.flow_direction == "BEARISH"
    assert response.f4_grade == "AVOID"


def test_build_response_v2_caps_adjustment_at_neutral_not_bullish_flip() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 7_000_000.0,
                "total_bid_side_prem": 5_500_000.0,
                "total_premium": 7_500_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_000_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 3_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "strike": 65,
                "underlying_price": 50,
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 300_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )

    assert response.options_net_flow_usd == 0.0
    assert response.options_flow_score == 50
    assert response.flow_direction == "NEUTRAL"


def test_build_response_v2_applies_strategy_adjustment_when_overwrite_leg_is_one_year_dte() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 8_000_000.0,
                "total_bid_side_prem": 6_400_000.0,
                "total_premium": 9_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_200_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2027-06-18",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_200_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "strike": 65,
                "underlying_price": 50,
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 500_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )

    assert response.options_net_flow_usd == 0.0
    assert response.options_flow_score == 50
    assert response.f4_score == 50
    assert response.flow_direction == "NEUTRAL"
    assert response.f4_grade == "NEUTRAL"


def test_build_response_v2_boosts_clean_dark_pool_accumulation_when_options_neutral() -> None:
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-03T20:01:00Z",
                "price": 250.0,
                "nbbo_bid": 249.4,
                "nbbo_ask": 249.8,
                "premium": 2_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:02:00Z",
                "price": 250.1,
                "nbbo_bid": 249.5,
                "nbbo_ask": 249.9,
                "premium": 2_100_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:03:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_200_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:04:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_300_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:05:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_400_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:06:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 1_000_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ],
        opt_trades=[
            {
                "type": "call",
                "created_at": "2026-06-03T15:00:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
        ],
    )

    assert response.dark_pool_net_flow_usd == 11_000_000.0
    assert response.dark_pool_large_buy_count == 5
    assert response.options_net_flow_usd == 0.0
    assert response.dark_pool_score >= 60
    assert response.f4_score >= 55


def test_build_response_v2_does_not_boost_when_settlement_is_too_high() -> None:
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-03T20:01:00Z",
                "price": 250.0,
                "nbbo_bid": 249.4,
                "nbbo_ask": 249.8,
                "premium": 2_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:02:00Z",
                "price": 250.1,
                "nbbo_bid": 249.5,
                "nbbo_ask": 249.9,
                "premium": 2_100_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:03:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_200_000.0,
                "sale_cond_codes": ["average_price"],
            },
            {
                "executed_at": "2026-06-03T20:04:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_300_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ],
        opt_trades=[
            {
                "type": "call",
                "created_at": "2026-06-03T15:00:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
        ],
    )

    assert response.dark_pool_net_flow_usd == 4_100_000.0
    assert response.dark_pool_large_buy_count == 2
    assert response.dark_pool_score <= 50


def test_alert_dte_days_handles_missing_and_invalid_expiry() -> None:
    assert _alert_dte_days({}) is None
    assert _alert_dte_days({"expiry": "not-a-date"}) is None


def test_apply_strategy_aware_adjustment_returns_raw_when_legs_missing() -> None:
    raw_net = -4_000_000.0
    alerts = [
        {
            "type": "put",
            "expiry": "2026-09-19",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 1_000_000.0,
        },
        {
            "type": "call",
            "expiry": "2099-01-21",
            "total_ask_side_prem": 3_000_000.0,
            "total_bid_side_prem": 100_000.0,
        },
    ]
    assert _apply_strategy_aware_adjustment(alerts, raw_net) == raw_net


def test_dark_pool_settlement_ratio_returns_expected_fraction() -> None:
    ratio = _dark_pool_settlement_ratio(
        [
            {
                "price": 100.0,
                "nbbo_bid": 99.5,
                "nbbo_ask": 100.5,
                "premium": 1_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "price": 100.0,
                "nbbo_bid": 99.5,
                "nbbo_ask": 100.5,
                "premium": 1_000_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ]
    )
    assert ratio == 0.5


def test_apply_dark_pool_quality_boost_applies_only_when_all_gates_pass() -> None:
    dp_prints = [
        {
            "price": 100.0,
            "nbbo_bid": 99.5,
            "nbbo_ask": 100.5,
            "premium": 1_000_000.0,
            "sale_cond_codes": [],
        },
        {
            "price": 100.1,
            "nbbo_bid": 99.6,
            "nbbo_ask": 100.6,
            "premium": 1_000_000.0,
            "sale_cond_codes": [],
        },
        {
            "price": 100.2,
            "nbbo_bid": 99.7,
            "nbbo_ask": 100.7,
            "premium": 1_000_000.0,
            "sale_cond_codes": [],
        },
    ]

    boosted = _apply_dark_pool_quality_boost(
        dp_score=58,
        dp_net_flow=11_000_000.0,
        dp_large_buys=4,
        dp_prints=dp_prints,
        opt_net_flow=0.0,
    )
    not_boosted = _apply_dark_pool_quality_boost(
        dp_score=58,
        dp_net_flow=11_000_000.0,
        dp_large_buys=2,
        dp_prints=dp_prints,
        opt_net_flow=0.0,
    )

    assert boosted == 68
    assert not_boosted == 58
