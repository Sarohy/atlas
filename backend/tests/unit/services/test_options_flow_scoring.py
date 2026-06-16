"""Unit tests for F4 v2 pure scoring primitives (TDD red phase).

Functions under test (all pure, no I/O):
  _is_excluded_ticker
  _pick_tier
  _map_net_flow_to_score
  _classify_dark_pool_print
  _classify_options_print
  _combine_f4_scores

These tests MUST fail at first run (stubs return wrong values). Phase 2
implementation turns them green.

Spec references:
  - 3-tier market-cap anchor table (Large / Mid / Small)
  - NBBO-anchored BUY/SELL classification with settlement codes
  - UW side+option_type classification (NEW_BULL / PUT_SELL / NEW_BEAR /
    PROFIT_TAKING / SPREAD_CROSS)
  - 50/50 combination of dark pool + options scores
  - Hard-coded OTC/ADR exclusion list (per locked Q3)
"""

from __future__ import annotations

import pytest

from atlas.services.options_flow_service import (
    _classify_dark_pool_print,
    _classify_options_print,
    _combine_f4_scores,
    _is_excluded_ticker,
    _map_net_flow_to_score,
    _pick_tier,
)

# ---------------------------------------------------------------------------
# Constants used in test cases — keep the spec values in one place.
# ---------------------------------------------------------------------------

_LARGE_CAP_50B_PLUS = 60_000_000_000.0
_MID_CAP_10B = 10_000_000_000.0
_SMALL_CAP_1B = 1_000_000_000.0


# ===========================================================================
# _is_excluded_ticker — hard-coded OTC/ADR exclusion list
# ===========================================================================


class TestIsExcludedTicker:
    """The 10 hard-coded exclusion tickers return F4 = 50 without API calls."""

    @pytest.mark.parametrize(
        "ticker",
        [
            "LSRCF",
            "LPKFF",
            "SLOIF",
            "AIXXF",
            "BESIY",
            "SIVE",
            "TOELY",
            "AJINF",
            "SHECY",
            "ATEYY",
        ],
    )
    def test_excluded_tickers_return_true(self, ticker: str) -> None:
        assert _is_excluded_ticker(ticker) is True

    def test_excluded_lookup_is_case_insensitive(self) -> None:
        assert _is_excluded_ticker("lsrcf") is True
        assert _is_excluded_ticker("Toely") is True

    @pytest.mark.parametrize("ticker", ["AAPL", "MU", "NVDA", "TSLA"])
    def test_non_excluded_tickers_return_false(self, ticker: str) -> None:
        assert _is_excluded_ticker(ticker) is False


# ===========================================================================
# _pick_tier — market-cap → LARGE / MID / SMALL
# ===========================================================================


class TestPickTier:
    """Tiers: MEGA > $500B ; LARGE $50B-$500B ; MID $5B-$50B ; SMALL < $5B."""

    def test_mega_cap_above_500b(self) -> None:
        assert _pick_tier(600_000_000_000.0) == "MEGA"
        assert _pick_tier(5_000_000_000_000.0) == "MEGA"

    def test_large_cap_between_50b_and_500b(self) -> None:
        assert _pick_tier(_LARGE_CAP_50B_PLUS) == "LARGE"
        assert _pick_tier(499_000_000_000.0) == "LARGE"

    def test_mid_cap_at_5b_floor_is_mid(self) -> None:
        # $5B is the MID floor (inclusive).
        assert _pick_tier(5_000_000_000.0) == "MID"

    def test_mid_cap_just_below_50b(self) -> None:
        assert _pick_tier(49_999_000_000.0) == "MID"

    def test_small_cap_below_5b(self) -> None:
        assert _pick_tier(4_999_000_000.0) == "SMALL"

    def test_none_market_cap_defaults_to_small(self) -> None:
        assert _pick_tier(None) == "SMALL"


# ===========================================================================
# _map_net_flow_to_score — anchor-table interpolation + clamping
# ===========================================================================


class TestMapNetFlowToScoreMegaCap:
    """MEGA anchors: 100→±$100M / 75→+$25M / 50→±$5M / 25→-$25M / 0→-$100M."""

    def test_at_plus_100m_anchor_returns_100(self) -> None:
        assert _map_net_flow_to_score(100_000_000.0, "MEGA") == 100

    def test_above_plus_100m_clamps_at_100(self) -> None:
        assert _map_net_flow_to_score(500_000_000.0, "MEGA") == 100

    def test_at_plus_25m_anchor_returns_75(self) -> None:
        assert _map_net_flow_to_score(25_000_000.0, "MEGA") == 75

    def test_inside_neutral_band_returns_50(self) -> None:
        # ±$5M is the neutral band — both anchors are 50.
        assert _map_net_flow_to_score(0.0, "MEGA") == 50
        assert _map_net_flow_to_score(2_500_000.0, "MEGA") == 50
        assert _map_net_flow_to_score(-3_000_000.0, "MEGA") == 50

    def test_at_minus_25m_anchor_returns_25(self) -> None:
        assert _map_net_flow_to_score(-25_000_000.0, "MEGA") == 25

    def test_at_minus_100m_anchor_returns_0(self) -> None:
        assert _map_net_flow_to_score(-100_000_000.0, "MEGA") == 0

    def test_below_minus_100m_clamps_at_0(self) -> None:
        assert _map_net_flow_to_score(-500_000_000.0, "MEGA") == 0

    def test_linear_interpolation_between_25m_and_100m(self) -> None:
        # Midpoint between +$25M (75) and +$100M (100) ≈ +$62.5M → ~87 (87 or 88).
        score = _map_net_flow_to_score(62_500_000.0, "MEGA")
        assert 86 <= score <= 89


class TestMapNetFlowToScoreLargeCap:
    """LARGE ($50-500B) anchors: 100→±$30M / 75→+$10M / 50→±$2M / 25→-$10M / 0→-$30M."""

    def test_at_plus_30m_anchor_returns_100(self) -> None:
        assert _map_net_flow_to_score(30_000_000.0, "LARGE") == 100

    def test_at_plus_10m_anchor_returns_75(self) -> None:
        assert _map_net_flow_to_score(10_000_000.0, "LARGE") == 75

    def test_tighter_neutral_band(self) -> None:
        # ±$2M neutral band (vs ±$5M for MEGA).
        assert _map_net_flow_to_score(0.0, "LARGE") == 50
        assert _map_net_flow_to_score(1_500_000.0, "LARGE") == 50

    def test_few_million_registers_above_neutral(self) -> None:
        # The point of the split: ~$3M on a $50-500B name is no longer flat 50.
        assert _map_net_flow_to_score(3_000_000.0, "LARGE") > 50

    def test_at_minus_30m_anchor_returns_0(self) -> None:
        assert _map_net_flow_to_score(-30_000_000.0, "LARGE") == 0


class TestMapNetFlowToScoreMidCap:
    """MID anchors: 100→+$20M / 75→+$5M / 50→±$1M / 25→-$5M / 0→-$20M."""

    def test_at_plus_20m_anchor_returns_100(self) -> None:
        assert _map_net_flow_to_score(20_000_000.0, "MID") == 100

    def test_at_plus_5m_anchor_returns_75(self) -> None:
        assert _map_net_flow_to_score(5_000_000.0, "MID") == 75

    def test_at_minus_20m_anchor_returns_0(self) -> None:
        assert _map_net_flow_to_score(-20_000_000.0, "MID") == 0

    def test_inside_mid_neutral_band(self) -> None:
        assert _map_net_flow_to_score(500_000.0, "MID") == 50


class TestMapNetFlowToScoreSmallCap:
    """SMALL anchors: 100→+$3M / 75→+$750K / 50→±$150K / 25→-$750K / 0→-$3M."""

    def test_at_plus_3m_anchor_returns_100(self) -> None:
        assert _map_net_flow_to_score(3_000_000.0, "SMALL") == 100

    def test_at_minus_750k_anchor_returns_25(self) -> None:
        assert _map_net_flow_to_score(-750_000.0, "SMALL") == 25

    def test_below_minus_3m_clamps_at_0(self) -> None:
        assert _map_net_flow_to_score(-10_000_000.0, "SMALL") == 0


# ===========================================================================
# _classify_dark_pool_print — NBBO-anchored BUY/SELL with settlement codes
# ===========================================================================


class TestClassifyDarkPoolPrint:
    """Print classification: BUY / SELL / SETTLEMENT."""

    def test_at_ask_is_buy(self) -> None:
        # price = ask → BUY
        assert _classify_dark_pool_print(100.0, bid=99.0, ask=100.0) == "BUY"

    def test_slightly_below_ask_within_tolerance_is_buy(self) -> None:
        # ask * 0.999 = 99.9; price 99.95 >= 99.9 -> BUY
        assert _classify_dark_pool_print(99.95, bid=99.0, ask=100.0) == "BUY"

    def test_at_bid_is_sell(self) -> None:
        assert _classify_dark_pool_print(99.0, bid=99.0, ask=100.0) == "SELL"

    def test_slightly_above_bid_within_tolerance_is_sell(self) -> None:
        # bid * 1.001 = 99.099; price 99.05 <= 99.099 -> SELL
        assert _classify_dark_pool_print(99.05, bid=99.0, ask=100.0) == "SELL"

    def test_midpoint_or_above_is_buy(self) -> None:
        # midpoint = 99.5; price 99.6 → BUY
        assert _classify_dark_pool_print(99.6, bid=99.0, ask=100.0) == "BUY"

    def test_below_midpoint_is_sell(self) -> None:
        assert _classify_dark_pool_print(99.3, bid=99.0, ask=100.0) == "SELL"

    def test_settlement_code_overrides_price(self) -> None:
        # Even at the ask, an average_price code marks it as SETTLEMENT.
        assert (
            _classify_dark_pool_print(
                100.0,
                bid=99.0,
                ask=100.0,
                sale_cond_codes=("average_price",),
            )
            == "SETTLEMENT"
        )

    def test_qualified_contingent_is_settlement(self) -> None:
        assert (
            _classify_dark_pool_print(
                99.5,
                bid=99.0,
                ask=100.0,
                sale_cond_codes=("qualified_contingent",),
            )
            == "SETTLEMENT"
        )

    def test_unrelated_code_does_not_trigger_settlement(self) -> None:
        # 'regular' (or any non-settlement code) must NOT be SETTLEMENT.
        result = _classify_dark_pool_print(
            99.6,
            bid=99.0,
            ask=100.0,
            sale_cond_codes=("regular",),
        )
        assert result in {"BUY", "SELL"}


# ===========================================================================
# _classify_options_print — UW side + option_type → classification
# ===========================================================================


class TestClassifyOptionsPrint:
    """Bullish: NEW_BULL, PUT_SELL. Bearish: NEW_BEAR. Stripped: PROFIT_TAKING, SPREAD_CROSS."""

    def test_call_on_ask_is_new_bull(self) -> None:
        assert (
            _classify_options_print(
                side="ASK",
                option_type="call",
                dte=30,
                delta=0.4,
            )
            == "NEW_BULL"
        )

    def test_put_on_bid_is_put_sell(self) -> None:
        assert (
            _classify_options_print(
                side="BID",
                option_type="put",
                dte=30,
                delta=-0.3,
            )
            == "PUT_SELL"
        )

    def test_put_on_ask_is_new_bear(self) -> None:
        assert (
            _classify_options_print(
                side="ASK",
                option_type="put",
                dte=30,
                delta=-0.3,
            )
            == "NEW_BEAR"
        )

    def test_call_on_bid_near_dated_is_profit_taking(self) -> None:
        # DTE = 7 ≤ 14 → PROFIT_TAKING
        assert (
            _classify_options_print(
                side="BID",
                option_type="call",
                dte=7,
                delta=0.3,
            )
            == "PROFIT_TAKING"
        )

    def test_call_on_bid_deep_itm_is_profit_taking(self) -> None:
        # |delta| = 0.85 ≥ 0.8 → PROFIT_TAKING
        assert (
            _classify_options_print(
                side="BID",
                option_type="call",
                dte=60,
                delta=0.85,
            )
            == "PROFIT_TAKING"
        )

    def test_call_on_bid_long_dated_otm_is_profit_taking(self) -> None:
        # Long-dated (DTE > 14) + OTM (|delta| < 0.5) call sold on BID → strip.
        assert (
            _classify_options_print(
                side="BID",
                option_type="call",
                dte=90,
                delta=0.2,
            )
            == "PROFIT_TAKING"
        )

    def test_side_none_is_spread_cross(self) -> None:
        assert (
            _classify_options_print(
                side="NONE",
                option_type="call",
                dte=30,
                delta=0.5,
            )
            == "SPREAD_CROSS"
        )

    def test_missing_side_is_spread_cross(self) -> None:
        assert (
            _classify_options_print(
                side=None,
                option_type="call",
                dte=30,
                delta=0.5,
            )
            == "SPREAD_CROSS"
        )


# ===========================================================================
# _combine_f4_scores — 50/50 average + source label
# ===========================================================================


class TestCombineF4Scores:
    """Combine dark-pool + options scores, returning (f4_raw, source_label)."""

    def test_both_scores_present_averages_them(self) -> None:
        result = _combine_f4_scores(dp_score=80, opt_score=60)
        assert result == (70, "BOTH")

    def test_dark_pool_only(self) -> None:
        result = _combine_f4_scores(dp_score=70, opt_score=None)
        assert result == (70, "DARK_POOL_ONLY")

    def test_options_only(self) -> None:
        result = _combine_f4_scores(dp_score=None, opt_score=40)
        assert result == (40, "OPTIONS_ONLY")

    def test_neither_returns_neutral_with_data_gap(self) -> None:
        result = _combine_f4_scores(dp_score=None, opt_score=None)
        assert result == (50, "DATA_GAP")

    def test_average_rounds_to_int(self) -> None:
        # (75 + 80) / 2 = 77.5 → round to 78 (banker's rounding picks even ⇒ 78).
        f4_raw, _ = _combine_f4_scores(dp_score=75, opt_score=80)
        assert f4_raw in {77, 78}
