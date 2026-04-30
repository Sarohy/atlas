"""Unit tests for AnalystService — v7.3.4 F3 scoring algorithm.

F3 v7.3.4 uses a base-score + modifier approach:
  Priority 1: Consensus label → base score (90/78/55/30)
  Priority 2: Analyst count   → modifier (+8/+5/+3/0/-5)
  Priority 3: PT revision     → modifier (+5/+3/0/-5/-10)
  Priority 4: Net upgrades    → modifier (+5/+3/0/-5/-10)
  Priority 5: Price vs target adjustment (with override rules)

High consensus override: Buy/SB + ≥9 analysts + 0 sells + raised/maintained PT → min 78
Hard cap: when pvt > +20%, f3_final = min(f3_before, 45)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.analyst_service import (
    _HARD_CAP_ABOVE_20,
    _analyst_count_modifier,
    _base_score_from_consensus,
    _build_analyst_response,
    _grade_from_total,
    _price_vs_target,
    _price_vs_target_band,
    _pt_revision_direction_label,
    _pt_revision_modifier,
    _upgrade_downgrade_modifier,
    _upside_color,
    classify_consensus,
    score_f3,
    AnalystService,
)

# ---------------------------------------------------------------------------
# _base_score_from_consensus
# ---------------------------------------------------------------------------


class TestBaseScoreFromConsensus:
    """Consensus rating string -> base score (90 / 78 / 55 / 30)."""

    def test_strong_buy_returns_90(self) -> None:
        assert _base_score_from_consensus("Strong Buy") == 90

    def test_strong_buy_case_insensitive(self) -> None:
        assert _base_score_from_consensus("STRONG BUY") == 90
        assert _base_score_from_consensus("strong buy") == 90

    def test_buy_returns_78(self) -> None:
        assert _base_score_from_consensus("Buy") == 78
        assert _base_score_from_consensus("BUY") == 78

    def test_hold_returns_55(self) -> None:
        assert _base_score_from_consensus("Hold") == 55
        assert _base_score_from_consensus("HOLD") == 55

    def test_sell_returns_30(self) -> None:
        assert _base_score_from_consensus("Sell") == 30
        assert _base_score_from_consensus("SELL") == 30

    def test_unknown_label_returns_sell_score(self) -> None:
        assert _base_score_from_consensus("Unknown") == 30


# ---------------------------------------------------------------------------
# _analyst_count_modifier
# ---------------------------------------------------------------------------


class TestAnalystCountModifier:
    """Analyst count -> modifier (+8/+5/+3/0/-5)."""

    def test_above_30_returns_8(self) -> None:
        assert _analyst_count_modifier(31) == 8
        assert _analyst_count_modifier(50) == 8

    def test_exactly_30_returns_5(self) -> None:
        assert _analyst_count_modifier(30) == 5

    def test_20_to_30_returns_5(self) -> None:
        assert _analyst_count_modifier(20) == 5
        assert _analyst_count_modifier(25) == 5

    def test_10_to_19_returns_3(self) -> None:
        assert _analyst_count_modifier(10) == 3
        assert _analyst_count_modifier(15) == 3
        assert _analyst_count_modifier(19) == 3

    def test_5_to_9_returns_0(self) -> None:
        assert _analyst_count_modifier(5) == 0
        assert _analyst_count_modifier(9) == 0

    def test_below_5_returns_minus_5(self) -> None:
        assert _analyst_count_modifier(4) == -5
        assert _analyst_count_modifier(0) == -5


# ---------------------------------------------------------------------------
# _pt_revision_direction_label
# ---------------------------------------------------------------------------


class TestPtRevisionDirectionLabel:
    """(raises, lowers) -> direction label string."""

    def test_two_net_raises_gives_multiple_raises(self) -> None:
        assert _pt_revision_direction_label(2, 0) == "MULTIPLE_RAISES"
        assert _pt_revision_direction_label(3, 1) == "MULTIPLE_RAISES"

    def test_one_net_raise_gives_single_raise(self) -> None:
        assert _pt_revision_direction_label(1, 0) == "SINGLE_RAISE"
        assert _pt_revision_direction_label(2, 1) == "SINGLE_RAISE"

    def test_no_change_gives_no_change(self) -> None:
        assert _pt_revision_direction_label(0, 0) == "NO_CHANGE"
        assert _pt_revision_direction_label(1, 1) == "NO_CHANGE"

    def test_one_net_lower_gives_single_cut(self) -> None:
        assert _pt_revision_direction_label(0, 1) == "SINGLE_CUT"
        assert _pt_revision_direction_label(1, 2) == "SINGLE_CUT"

    def test_two_net_lowers_gives_multiple_cuts(self) -> None:
        assert _pt_revision_direction_label(0, 2) == "MULTIPLE_CUTS"
        assert _pt_revision_direction_label(0, 5) == "MULTIPLE_CUTS"


# ---------------------------------------------------------------------------
# _pt_revision_modifier
# ---------------------------------------------------------------------------


class TestPtRevisionModifier:
    """PT direction label -> modifier (+5/+3/0/-5/-10)."""

    def test_multiple_raises_returns_5(self) -> None:
        assert _pt_revision_modifier("MULTIPLE_RAISES") == 5

    def test_single_raise_returns_3(self) -> None:
        assert _pt_revision_modifier("SINGLE_RAISE") == 3

    def test_no_change_returns_0(self) -> None:
        assert _pt_revision_modifier("NO_CHANGE") == 0

    def test_single_cut_returns_minus_5(self) -> None:
        assert _pt_revision_modifier("SINGLE_CUT") == -5

    def test_multiple_cuts_returns_minus_10(self) -> None:
        assert _pt_revision_modifier("MULTIPLE_CUTS") == -10

    def test_case_insensitive(self) -> None:
        assert _pt_revision_modifier("multiple_raises") == 5
        assert _pt_revision_modifier("single_cut") == -5


# ---------------------------------------------------------------------------
# _upgrade_downgrade_modifier
# ---------------------------------------------------------------------------


class TestUpgradeDowngradeModifier:
    """Net upgrades/downgrades integer -> modifier (+5/+3/0/-5/-10)."""

    def test_more_than_2_returns_5(self) -> None:
        assert _upgrade_downgrade_modifier(3) == 5
        assert _upgrade_downgrade_modifier(10) == 5

    def test_1_or_2_returns_3(self) -> None:
        assert _upgrade_downgrade_modifier(1) == 3
        assert _upgrade_downgrade_modifier(2) == 3

    def test_zero_returns_0(self) -> None:
        assert _upgrade_downgrade_modifier(0) == 0

    def test_minus_1_or_minus_2_returns_minus_5(self) -> None:
        assert _upgrade_downgrade_modifier(-1) == -5
        assert _upgrade_downgrade_modifier(-2) == -5

    def test_less_than_minus_2_returns_minus_10(self) -> None:
        assert _upgrade_downgrade_modifier(-3) == -10
        assert _upgrade_downgrade_modifier(-10) == -10


# ---------------------------------------------------------------------------
# _price_vs_target
# ---------------------------------------------------------------------------


class TestPriceVsTarget:
    """price_vs_target = round((current - target) / target, 4)."""

    def test_at_target_gives_zero(self) -> None:
        assert _price_vs_target(100.0, 100.0) == 0.0

    def test_above_target_gives_positive(self) -> None:
        assert _price_vs_target(110.0, 100.0) == 0.10

    def test_below_target_gives_negative(self) -> None:
        assert _price_vs_target(90.0, 100.0) == -0.10

    def test_result_is_rounded_to_4_decimals(self) -> None:
        # (400-460)/460 = -0.130434... -> -0.1304
        result = _price_vs_target(400.0, 460.0)
        assert result == -0.1304

    def test_mu_at_target_is_zero(self) -> None:
        assert _price_vs_target(458.25, 458.25) == 0.0


# ---------------------------------------------------------------------------
# _price_vs_target_band
# ---------------------------------------------------------------------------


class TestPriceVsTargetBand:
    """pvt float -> band label string."""

    def test_more_than_20_below_gives_below_20_band(self) -> None:
        band = _price_vs_target_band(-0.21)
        assert "20%+" in band and "below" in band

    def test_exactly_minus_20_is_below_10_band(self) -> None:
        # -0.20 is NOT < -0.20, falls into 10-20% below
        band = _price_vs_target_band(-0.20)
        assert "10-20%" in band and "below" in band

    def test_between_10_and_20_below_gives_below_10_band(self) -> None:
        band = _price_vs_target_band(-0.15)
        assert "10-20%" in band and "below" in band

    def test_zero_gives_neutral(self) -> None:
        band = _price_vs_target_band(0.0)
        assert "neutral" in band.lower() or "target" in band.lower()

    def test_between_10_and_20_above_gives_above_10_band(self) -> None:
        band = _price_vs_target_band(0.15)
        assert "10-20%" in band and "above" in band

    def test_more_than_20_above_gives_above_20_band(self) -> None:
        band = _price_vs_target_band(0.25)
        assert "20%+" in band and "above" in band


# ---------------------------------------------------------------------------
# _grade_from_total — UNCHANGED
# ---------------------------------------------------------------------------


class TestGradeFromTotal:
    """F3 score -> STRONG BUY / BUY / NEUTRAL / WEAK / AVOID label."""

    def test_80_is_strong_buy(self) -> None:
        assert _grade_from_total(80) == "STRONG BUY"

    def test_100_is_strong_buy(self) -> None:
        assert _grade_from_total(100) == "STRONG BUY"

    def test_79_is_buy(self) -> None:
        assert _grade_from_total(79) == "BUY"

    def test_60_is_buy(self) -> None:
        assert _grade_from_total(60) == "BUY"

    def test_59_is_neutral(self) -> None:
        assert _grade_from_total(59) == "NEUTRAL"

    def test_40_is_neutral(self) -> None:
        assert _grade_from_total(40) == "NEUTRAL"

    def test_39_is_weak(self) -> None:
        assert _grade_from_total(39) == "WEAK"

    def test_20_is_weak(self) -> None:
        assert _grade_from_total(20) == "WEAK"

    def test_19_is_avoid(self) -> None:
        assert _grade_from_total(19) == "AVOID"

    def test_0_is_avoid(self) -> None:
        assert _grade_from_total(0) == "AVOID"


# ---------------------------------------------------------------------------
# score_f3 — six spec test cases + edge cases
# ---------------------------------------------------------------------------


class TestHighConsensusOverride:
    """Min 78 fires when Buy/SB + >=9 analysts + 0 sells + raised/maintained PT."""

    def test_override_lifts_score_to_78(self) -> None:
        # Buy(78) + count=9(0) + NO_CHANGE(0) + 0 upgrades(0) = 78,
        # pvt ~+0.1387 (14% above) -> flat -15 -> 63 < 78.
        # Override: Buy + 9 + 0 sells + NO_CHANGE (maintained) -> min 78.
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=9,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=521.95,
            analyst_target=458.25,
            sell_count=0,
        )
        assert result.raw_score == 78
        assert result.override_applied is True

    def test_override_does_not_fire_with_sell_count_nonzero(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=9,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=521.95,
            analyst_target=458.25,
            sell_count=1,
        )
        assert result.override_applied is False

    def test_override_does_not_fire_with_hold_consensus(self) -> None:
        result = score_f3(
            consensus_rating="Hold",
            analyst_count=15,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        assert result.override_applied is False

    def test_override_does_not_fire_when_count_below_9(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=8,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        assert result.override_applied is False

    def test_override_does_not_fire_with_multiple_cuts(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=10,
            pt_revision_direction="MULTIPLE_CUTS",
            net_upgrades_30d=0,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        assert result.override_applied is False


# ---------------------------------------------------------------------------
# classify_consensus
# ---------------------------------------------------------------------------


class TestClassifyConsensus:
    """Spec test cases: weighted-average consensus classifier.

    Weights: SB=5, B=4, H=3, S=2, SS=1
    Thresholds: >=4.5 → STRONG BUY/90 | >=3.5 → BUY/78 | >=2.5 → HOLD/55 | else → SELL/30
    """

    def test_zero_total_returns_no_coverage(self) -> None:
        label, score = classify_consensus(0, 0, 0, 0, 0)
        assert label == "NO COVERAGE"
        assert score == 55

    def test_spec_case_1_buy_not_strong_buy(self) -> None:
        # SB=0, B=55, H=11, S=2, SS=0 — buy_pct=80.9% but weighted=3.779 → BUY
        # This is the primary bug-fix test: old code returned "STRONG BUY" for this data
        label, score = classify_consensus(0, 55, 11, 2, 0)
        weighted = (0 * 5 + 55 * 4 + 11 * 3 + 2 * 2 + 0 * 1) / 68
        assert weighted < 4.5, "Precondition: weighted avg must be < 4.5 for BUY"
        assert weighted >= 3.5, "Precondition: weighted avg must be >= 3.5 for BUY"
        assert label == "BUY"
        assert score == 78

    def test_spec_case_2_strong_buy(self) -> None:
        # SB=40, B=15, H=3, S=0, SS=0 — weighted = (200+60+9)/58 = 4.638 → STRONG BUY
        label, score = classify_consensus(40, 15, 3, 0, 0)
        assert label == "STRONG BUY"
        assert score == 90

    def test_spec_case_3_sell_overextended(self) -> None:
        # SB=5, B=20, H=10, S=3, SS=0 — weighted=(25+80+30+6)/38=141/38=3.711 → BUY
        # (Price is above target so F3 gets hard-capped, but consensus is BUY)
        label, score = classify_consensus(5, 20, 10, 3, 0)
        assert label == "BUY"
        assert score == 78

    def test_spec_case_4_hold(self) -> None:
        # SB=0, B=5, H=20, S=5, SS=0 — weighted=(0+20+60+10)/30=90/30=3.0 → HOLD
        label, score = classify_consensus(0, 5, 20, 5, 0)
        assert label == "HOLD"
        assert score == 55

    def test_strong_buy_at_threshold(self) -> None:
        # All Strong Buy: weighted = 5.0 >= 4.5 → STRONG BUY
        label, score = classify_consensus(10, 0, 0, 0, 0)
        assert label == "STRONG BUY"
        assert score == 90

    def test_sell_below_threshold(self) -> None:
        # Mostly Sell/SS: weighted = (0+0+0+4+1)/5 = 1.0 → SELL
        label, score = classify_consensus(0, 0, 0, 4, 1)
        assert label == "SELL"
        assert score == 30


# ---------------------------------------------------------------------------
# _upside_color
# ---------------------------------------------------------------------------


class TestUpsideColor:
    """Price-vs-target ratio → colour token."""

    def test_below_20_pct_returns_green(self) -> None:
        assert _upside_color(-0.25) == "GREEN"
        assert _upside_color(-0.30) == "GREEN"

    def test_at_negative_20_boundary_returns_light_green(self) -> None:
        # -0.20 is NOT < -0.20, so it falls to LIGHT_GREEN
        assert _upside_color(-0.20) == "LIGHT_GREEN"

    def test_10_to_20_below_returns_light_green(self) -> None:
        assert _upside_color(-0.15) == "LIGHT_GREEN"
        assert _upside_color(-0.10001) == "LIGHT_GREEN"

    def test_neutral_zone_returns_neutral(self) -> None:
        # pvt in (-0.10, +0.10]
        assert _upside_color(-0.10) == "NEUTRAL"
        assert _upside_color(0.0) == "NEUTRAL"
        assert _upside_color(0.0536) == "NEUTRAL"  # spec case 1 bug data
        assert _upside_color(0.10) == "NEUTRAL"

    def test_10_to_20_above_returns_amber(self) -> None:
        assert _upside_color(0.15) == "AMBER"
        assert _upside_color(0.20) == "AMBER"

    def test_above_20_pct_returns_red(self) -> None:
        assert _upside_color(0.25) == "RED"
        assert _upside_color(0.50) == "RED"


class TestScoreF3:
    """spec test cases 1-6 plus edge cases."""

    def test_1_price_at_target_neutral_not_penalized(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=38,
            pt_revision_direction="MULTIPLE_RAISES",
            net_upgrades_30d=2,
            current_price=458.25,
            analyst_target=458.25,
            sell_count=0,
        )
        # f3_before = 78+8+5+3 = 94; pvt=0 neutral; no adjustment
        assert result.raw_score == 94
        assert result.raw_score > 59, "Bug: price-at-target must not penalize F3"
        assert result.breakdown["price_vs_target_adjustment"] == 0

    def test_2_ten_to_twenty_pct_below_adds_5(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=15,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=400.0,
            analyst_target=460.0,
            sell_count=0,
        )
        assert result.breakdown["f3_before_price_adjustment"] == 81
        assert result.breakdown["price_vs_target_adjustment"] == 5
        assert result.raw_score == 86

    def test_3_twenty_plus_pct_above_hard_cap_45(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=10,
            pt_revision_direction="SINGLE_RAISE",
            net_upgrades_30d=1,
            current_price=580.0,
            analyst_target=460.0,
            sell_count=0,
        )
        assert result.breakdown["f3_before_price_adjustment"] == 87
        assert result.raw_score == _HARD_CAP_ABOVE_20

    def test_4_high_consensus_override_minimum_78(self) -> None:
        result = score_f3(
            consensus_rating="Strong Buy",
            analyst_count=9,
            pt_revision_direction="SINGLE_RAISE",
            net_upgrades_30d=3,
            current_price=470.0,
            analyst_target=458.25,
            sell_count=0,
        )
        assert result.raw_score >= 78
        assert result.raw_score == 98  # already above 78

    def test_5_hold_above_target_full_penalty_capped(self) -> None:
        result = score_f3(
            consensus_rating="Hold",
            analyst_count=8,
            pt_revision_direction="SINGLE_CUT",
            net_upgrades_30d=-3,
            current_price=560.0,
            analyst_target=458.25,
            sell_count=2,
        )
        # f3_before=55+0-5-10=40; pvt>20% above; min(40,45)=40
        assert result.breakdown["f3_before_price_adjustment"] == 40
        assert result.raw_score == 40
        assert result.override_applied is False

    def test_6_ten_to_twenty_above_flat_penalty(self) -> None:
        # Buy(78) + count=20(+5) + SINGLE_RAISE(+3) + net=2(+3) = 89
        # pvt ~11.3% above target → flat -15 → 74 < 78
        # Override fires: Buy + 20 analysts + 0 sells + SINGLE_RAISE → min 78
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=20,
            pt_revision_direction="SINGLE_RAISE",
            net_upgrades_30d=2,
            current_price=510.0,
            analyst_target=458.25,
            sell_count=0,
        )
        assert result.breakdown["f3_before_price_adjustment"] == 89
        assert result.breakdown["price_vs_target_adjustment"] == -15
        assert result.raw_score == 78
        assert result.override_applied is True

    def test_score_clamped_at_100(self) -> None:
        # Strong Buy(90) + >30(+8) + multiple_raises(+5) + >2 upgrades(+5) = 108 -> 100
        result = score_f3(
            consensus_rating="Strong Buy",
            analyst_count=35,
            pt_revision_direction="MULTIPLE_RAISES",
            net_upgrades_30d=5,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        assert result.raw_score == 100

    def test_weight_is_0_15(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=15,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        assert result.weight == 0.15

    def test_weighted_contribution_equals_score_times_weight(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=15,
            pt_revision_direction="NO_CHANGE",
            net_upgrades_30d=0,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        assert abs(result.weighted_contribution - result.raw_score * 0.15) < 0.001

    def test_breakdown_has_all_required_keys(self) -> None:
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=15,
            pt_revision_direction="SINGLE_RAISE",
            net_upgrades_30d=1,
            current_price=100.0,
            analyst_target=100.0,
            sell_count=0,
        )
        for key in (
            "base_score",
            "analyst_count_modifier",
            "pt_revision_modifier",
            "upgrade_downgrade_modifier",
            "f3_before_price_adjustment",
            "price_vs_target",
            "price_vs_target_band_label",
            "price_vs_target_adjustment",
        ):
            assert key in result.breakdown, f"Missing breakdown key: {key}"

    def test_full_penalty_when_deteriorating(self) -> None:
        # Price ~15% above AND deteriorating (net_upgrades=-1, single_cut) -> -15
        result = score_f3(
            consensus_rating="Buy",
            analyst_count=10,
            pt_revision_direction="SINGLE_CUT",
            net_upgrades_30d=-1,
            current_price=529.0,
            analyst_target=458.25,
            sell_count=0,
        )
        assert result.breakdown["price_vs_target_adjustment"] == -15


# ---------------------------------------------------------------------------
# _build_analyst_response smoke tests
# ---------------------------------------------------------------------------


def _make_ratings(raises: int, lowers: int, net_upgrades: int) -> dict[str, int]:
    return {"raises": raises, "lowers": lowers, "net_upgrades": net_upgrades}


class TestBuildAnalystResponse:
    """Smoke tests for _build_analyst_response assembly."""

    def test_at_target_no_penalty(self) -> None:
        response = _build_analyst_response(
            ticker="MU",
            strong_buy=20,
            buy=18,
            hold=0,
            sell=0,
            strong_sell=0,
            num_analysts=38,
            consensus_pt=458.25,
            current_price=458.25,
            has_coverage=True,
            ratings_data=_make_ratings(raises=3, lowers=0, net_upgrades=2),
        )
        assert response.f3_score is not None
        assert response.f3_score > 59, (
            f"Bug regression: price-at-target returned {response.f3_score}"
        )

    def test_no_coverage_returns_none_score(self) -> None:
        response = _build_analyst_response(
            ticker="TINY",
            strong_buy=0,
            buy=0,
            hold=0,
            sell=0,
            strong_sell=0,
            num_analysts=None,
            consensus_pt=None,
            current_price=None,
            has_coverage=False,
            ratings_data=None,
        )
        assert response.f3_score is None

    def test_override_flag_propagated(self) -> None:
        # Buy + 9 analysts + 0 sells + no cut PT, pvt neutral -> f3=78, override present but no change
        response = _build_analyst_response(
            ticker="TST",
            strong_buy=0,
            buy=9,
            hold=0,
            sell=0,
            strong_sell=0,
            num_analysts=9,
            consensus_pt=100.0,
            current_price=100.0,
            has_coverage=True,
            ratings_data=_make_ratings(raises=0, lowers=0, net_upgrades=0),
        )
        assert response.f3_score is not None
        # score=78 already, override min 78 met but no actual lift needed
        assert response.override_applied is False

    def test_grade_matches_score(self) -> None:
        response = _build_analyst_response(
            ticker="MU",
            strong_buy=10,
            buy=5,
            hold=3,
            sell=0,
            strong_sell=0,
            num_analysts=18,
            consensus_pt=460.0,
            current_price=400.0,
            has_coverage=True,
            ratings_data=_make_ratings(raises=1, lowers=0, net_upgrades=1),
        )
        if response.f3_score is not None:
            score = response.f3_score
            grade = response.f3_grade
            if score >= 80:
                assert grade == "STRONG BUY"
            elif score >= 60:
                assert grade == "BUY"
            elif score >= 40:
                assert grade == "NEUTRAL"

    def test_upside_color_present_when_price_data_available(self) -> None:
        # pvt = (451.62 - 428.65) / 428.65 = +0.0536 → NEUTRAL zone → upside_color = NEUTRAL
        response = _build_analyst_response(
            ticker="BUGFIX",
            strong_buy=0,
            buy=55,
            hold=11,
            sell=2,
            strong_sell=0,
            num_analysts=68,
            consensus_pt=428.65,
            current_price=451.62,
            has_coverage=True,
            ratings_data=_make_ratings(raises=0, lowers=0, net_upgrades=0),
        )
        assert response.pt_upside.upside_color == "NEUTRAL"

    def test_spec_case_1_correct_score_and_label(self) -> None:
        # Bug 1 + Bug 2 fix: SB=0, B=55, H=11, S=2, SS=0 → BUY (not STRONG BUY)
        # f3 = 78 (BUY base) + 8 (>30 analysts) + 0 + 0 + 0 (neutral adj) = 86
        response = _build_analyst_response(
            ticker="BUGFIX",
            strong_buy=0,
            buy=55,
            hold=11,
            sell=2,
            strong_sell=0,
            num_analysts=68,
            consensus_pt=428.65,
            current_price=451.62,
            has_coverage=True,
            ratings_data=_make_ratings(raises=0, lowers=0, net_upgrades=0),
        )
        assert response.consensus_rating.label == "BUY"
        assert response.consensus_rating.base_score == 78
        assert response.f3_score == 86


# ---------------------------------------------------------------------------
# _fetch_current_price — prevDay.c fallback (UNCHANGED)
# ---------------------------------------------------------------------------


def _polygon_snapshot(day_close: float | None, prev_close: float | None) -> dict:
    day: dict = {}
    if day_close is not None:
        day["c"] = day_close
    prev_day: dict = {}
    if prev_close is not None:
        prev_day["c"] = prev_close
    return {"ticker": {"day": day, "prevDay": prev_day}}


def _mock_http_client(payload: dict) -> AsyncMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    return client


class TestFetchCurrentPrice:
    """_fetch_current_price must return prevDay.c when day.c is 0 or absent."""

    async def test_returns_day_close_when_positive(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=150.0, prev_close=140.0))
        result = await service._fetch_current_price(client, "AAOI")
        assert result == 150.0

    async def test_falls_back_to_prevday_when_day_close_is_zero(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=0, prev_close=136.50))
        result = await service._fetch_current_price(client, "AAOI")
        assert result == 136.50

    async def test_falls_back_to_prevday_when_day_close_absent(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=None, prev_close=136.50))
        result = await service._fetch_current_price(client, "AAOI")
        assert result == 136.50

    async def test_returns_none_when_both_prices_are_zero(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=0, prev_close=0))
        result = await service._fetch_current_price(client, "AAOI")
        assert result is None

    async def test_returns_none_when_both_prices_absent(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=None, prev_close=None))
        result = await service._fetch_current_price(client, "AAOI")
        assert result is None

    async def test_returns_none_when_no_polygon_key(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="")
        client = _mock_http_client(_polygon_snapshot(day_close=150.0, prev_close=140.0))
        result = await service._fetch_current_price(client, "AAOI")
        assert result is None
        client.get.assert_not_called()
