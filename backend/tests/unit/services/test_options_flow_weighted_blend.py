"""TDD — RED tests for F4 weighted DP/options blend and new response fields.

These tests describe the desired behaviour BEFORE implementation:
  1. When dark_pool_score ≥ 80 AND options_flow_score is in the neutral
     band [45, 55], _combine_f4_scores should use a 65/35 (DP/options)
     weighted blend instead of the current 50/50 average.
  2. OptionsFlowResponse must expose dark_pool_settlement_ratio and
     options_strategy_type.
  3. _detect_covered_call_posture must identify the three-leg pattern
     (protective puts + covered-call overwriting + LEAP accumulation).

All tests below fail against the current code.
"""

from __future__ import annotations

from atlas.services.options_flow_service import (
    _build_response_v2,
    _combine_f4_scores,
    _detect_covered_call_posture,  # does not yet exist → ImportError
)

# ---------------------------------------------------------------------------
# _combine_f4_scores — weighted blend when DP is strong and options neutral
# ---------------------------------------------------------------------------


def test_combine_scores_weighted_when_dp_strong_and_options_neutral() -> None:
    """dp=100, opt=50: should use 65/35 blend → round(65+17.5)=82 (banker's), not 75."""
    score, source = _combine_f4_scores(100, 50)
    assert score == 82, f"expected 82 (weighted, banker's rounding), got {score}"
    assert source == "BOTH"


def test_combine_scores_weighted_at_exact_dp_threshold() -> None:
    """dp=80 (exact threshold), opt=50: 65/35 → round(52+17.5)=70, not 65."""
    score, _ = _combine_f4_scores(80, 50)
    assert score == 70, f"expected 70 (weighted), got {score}"


def test_combine_scores_weighted_at_lower_neutral_band_edge() -> None:
    """dp=100, opt=45 (lower edge of neutral band): still weighted → round(65+15.75)=81."""
    score, _ = _combine_f4_scores(100, 45)
    assert score == 81, f"expected 81 (weighted), got {score}"


def test_combine_scores_weighted_at_upper_neutral_band_edge() -> None:
    """dp=100, opt=55 (upper edge of neutral band): still weighted → round(65+19.25)=84."""
    score, _ = _combine_f4_scores(100, 55)
    assert score == 84, f"expected 84 (weighted), got {score}"


# ---------------------------------------------------------------------------
# _combine_f4_scores — 50/50 preserved when conditions NOT met (regression)
# ---------------------------------------------------------------------------


def test_combine_scores_50_50_when_dp_just_below_threshold() -> None:
    """dp=79 (below threshold), opt=50: 50/50 → 64 (banker's rounding of 64.5), not weighted."""
    score, _ = _combine_f4_scores(79, 50)
    assert score == 64, f"expected 64 (50/50, banker's rounding), got {score}"


def test_combine_scores_50_50_when_options_below_neutral_band() -> None:
    """dp=100, opt=44 (below neutral band): 50/50 → 72."""
    score, _ = _combine_f4_scores(100, 44)
    assert score == 72, f"expected 72 (50/50), got {score}"


def test_combine_scores_50_50_when_options_above_neutral_band() -> None:
    """dp=100, opt=56 (above neutral band, directionally bullish): 50/50 → 78."""
    score, _ = _combine_f4_scores(100, 56)
    assert score == 78, f"expected 78 (50/50), got {score}"


def test_combine_scores_50_50_single_dp_source_unchanged() -> None:
    """Single DP source: score pass-through, no blend change."""
    score, source = _combine_f4_scores(100, None)
    assert score == 100
    assert source == "DARK_POOL_ONLY"


def test_combine_scores_50_50_data_gap_unchanged() -> None:
    """Both None → neutral fallback unchanged."""
    score, source = _combine_f4_scores(None, None)
    assert score == 50
    assert source == "DATA_GAP"


# ---------------------------------------------------------------------------
# _detect_covered_call_posture — new pure helper
# ---------------------------------------------------------------------------


def test_detect_covered_call_posture_true_for_classic_three_leg_pattern() -> None:
    """All three legs present → True."""
    alerts = [
        # Leg 1 & 2: protective put spread (2 puts, both ask+bid present)
        {
            "type": "put",
            "expiry": "2026-09-19",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 1_600_000.0,
            "total_premium": 2_500_000.0,
        },
        {
            "type": "put",
            "expiry": "2026-11-20",
            "total_ask_side_prem": 1_000_000.0,
            "total_bid_side_prem": 850_000.0,
            "total_premium": 1_200_000.0,
        },
        # Leg 3: covered-call overwrite (near-dated call sold on bid-dominance)
        {
            "type": "call",
            "expiry": "2026-08-21",
            "total_ask_side_prem": 500_000.0,
            "total_bid_side_prem": 1_500_000.0,  # bid >> ask → overwriting
            "total_premium": 1_600_000.0,
        },
        # Leg 4: LEAP call accumulation (ask dominance, DTE >> 180)
        {
            "type": "call",
            "expiry": "2028-01-21",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 200_000.0,  # ask >> bid → accumulation
            "total_premium": 2_100_000.0,
        },
    ]
    assert _detect_covered_call_posture(alerts) is True


def test_detect_covered_call_posture_false_without_overwrite_leg() -> None:
    """Only puts + LEAP, no covered-call overwrite → False."""
    alerts = [
        {
            "type": "put",
            "expiry": "2026-09-19",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 1_600_000.0,
            "total_premium": 2_500_000.0,
        },
        {
            "type": "put",
            "expiry": "2026-11-20",
            "total_ask_side_prem": 1_000_000.0,
            "total_bid_side_prem": 850_000.0,
            "total_premium": 1_200_000.0,
        },
        {
            "type": "call",
            "expiry": "2028-01-21",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 200_000.0,
            "total_premium": 2_100_000.0,
        },
    ]
    assert _detect_covered_call_posture(alerts) is False


def test_detect_covered_call_posture_false_without_leap_leg() -> None:
    """Puts + near-dated covered call, no LEAP → False."""
    alerts = [
        {
            "type": "put",
            "expiry": "2026-09-19",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 1_600_000.0,
            "total_premium": 2_500_000.0,
        },
        {
            "type": "put",
            "expiry": "2026-11-20",
            "total_ask_side_prem": 1_000_000.0,
            "total_bid_side_prem": 850_000.0,
            "total_premium": 1_200_000.0,
        },
        {
            "type": "call",
            "expiry": "2026-08-21",
            "total_ask_side_prem": 500_000.0,
            "total_bid_side_prem": 1_500_000.0,
            "total_premium": 1_600_000.0,
        },
    ]
    assert _detect_covered_call_posture(alerts) is False


def test_detect_covered_call_posture_false_with_only_one_put_leg() -> None:
    """Only one put leg — does not satisfy the 2-leg protective spread."""
    alerts = [
        {
            "type": "put",
            "expiry": "2026-09-19",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 1_600_000.0,
            "total_premium": 2_500_000.0,
        },
        {
            "type": "call",
            "expiry": "2026-08-21",
            "total_ask_side_prem": 500_000.0,
            "total_bid_side_prem": 1_500_000.0,
            "total_premium": 1_600_000.0,
        },
        {
            "type": "call",
            "expiry": "2028-01-21",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 200_000.0,
            "total_premium": 2_100_000.0,
        },
    ]
    assert _detect_covered_call_posture(alerts) is False


def test_detect_covered_call_posture_false_for_empty_alerts() -> None:
    assert _detect_covered_call_posture([]) is False


# ---------------------------------------------------------------------------
# OptionsFlowResponse — new fields: dark_pool_settlement_ratio, options_strategy_type
# ---------------------------------------------------------------------------

# Named constant: settlement ratio for a 1-settlement-in-2-prints data set.
EXPECTED_SETTLEMENT_RATIO_HALF = 0.5


def test_response_exposes_dark_pool_settlement_ratio() -> None:
    """dark_pool_settlement_ratio must be present and correctly computed."""
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
                "price": 250.0,
                "nbbo_bid": 249.4,
                "nbbo_ask": 249.8,
                "premium": 1_000_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ],
        opt_trades=None,
    )
    assert response.dark_pool_settlement_ratio is not None
    assert abs(response.dark_pool_settlement_ratio - EXPECTED_SETTLEMENT_RATIO_HALF) < 0.01


def test_response_settlement_ratio_is_none_when_no_dp_prints() -> None:
    """No DP data → settlement ratio must be None."""
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=None,
        opt_trades=None,
    )
    assert response.dark_pool_settlement_ratio is None


def test_response_options_strategy_tag_is_removed() -> None:
    """The broken covered-call display tag was removed → options_strategy_type is always None."""
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 1_600_000.0,
                "total_premium": 2_500_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-11-20",
                "total_ask_side_prem": 1_000_000.0,
                "total_bid_side_prem": 850_000.0,
                "total_premium": 1_200_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "total_ask_side_prem": 500_000.0,
                "total_bid_side_prem": 1_500_000.0,
                "total_premium": 1_600_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 200_000.0,
                "total_premium": 2_100_000.0,
            },
        ],
    )
    assert response.options_strategy_type is None


def test_response_options_strategy_type_is_none_for_directional_flow() -> None:
    """Pure directional call buying (no three-leg pattern) → strategy_type is None."""
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "call",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 200_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )
    assert response.options_strategy_type is None


def test_response_options_strategy_type_is_none_when_no_opt_trades() -> None:
    """No options data → strategy_type must be None."""
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=None,
        opt_trades=None,
    )
    assert response.options_strategy_type is None


# ---------------------------------------------------------------------------
# Integration — F4 is options-only; dark pool drives the chip, not the score
# ---------------------------------------------------------------------------


def test_build_response_v2_dark_pool_not_scored_into_f4b() -> None:
    """Final scoring rule: F4a equity/dark-pool is NOT scored into F4b. A strong
    dark-pool buy-lean does not move the options-only F4b score."""
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-03T20:01:00Z",
                "price": 250.0,
                "nbbo_bid": 249.4,
                "nbbo_ask": 249.8,
                "premium": 25_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:02:00Z",
                "price": 250.1,
                "nbbo_bid": 249.5,
                "nbbo_ask": 249.9,
                "premium": 25_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:03:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 25_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:04:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 25_000_000.0,
                "sale_cond_codes": [],
            },
        ],
        opt_trades=[
            {
                "type": "call",
                "created_at": "2026-06-03T15:00:00Z",
                "total_ask_side_prem": 2_000_000.0,
                "total_premium": 2_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "total_ask_side_prem": 2_000_000.0,
                "total_premium": 2_000_000.0,
            },
        ],
    )
    # Options balanced (call_ask 2M vs put_ask 2M) → bullish_share 0.5 → 50.
    # dp_net_flow = $100M buy-lean, but F4a is NOT scored → F4b stays 50.
    assert response.options_flow_score == 50
    assert response.f4_score == 50
    assert response.data_source == "OPTIONS_ONLY"
    assert response.dark_pool_score == 100  # computed for the overlay, not scored
