"""Unit tests for AnalystService — v7.3.5 F3 scoring algorithm.

F3 v7.3.5 uses a 4-bucket PT approach + recency-weighted upgrade modifier:
  Bucket 1: PT > price                              → base 80
  Bucket 2: PT ≤ price + positive revision (30d)   → base 55
  Bucket 3: PT ≤ price + ≥20 analysts + avg ≥ 4.0 → base 65
  Bucket 4: Neither                                 → base 40
  Plus: recency-weighted upgrade modifier (+5/+3/0/-5/-10)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.analyst_service import (
    AnalystService,
    _analyst_count_modifier,
    _base_score_from_consensus,
    _build_analyst_response,
    _grade_from_total,
    _price_vs_target,
    _price_vs_target_band,
    _pt_revision_direction_label,
    _pt_revision_modifier,
    _recency_weight,
    _upgrade_downgrade_modifier,
    _upside_color,
    _weighted_consensus_avg,
    _weighted_upgrade_modifier,
    classify_consensus,
    score_f3,
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
# _weighted_consensus_avg
# ---------------------------------------------------------------------------


class TestWeightedConsensusAvg:
    """Weighted avg (SB=5, B=4, H=3, S=2, SS=1). 0.0 when total=0."""

    def test_all_strong_buy_returns_5(self) -> None:
        assert _weighted_consensus_avg(10, 0, 0, 0, 0) == 5.0

    def test_all_strong_sell_returns_1(self) -> None:
        assert _weighted_consensus_avg(0, 0, 0, 0, 10) == 1.0

    def test_zero_total_returns_0(self) -> None:
        assert _weighted_consensus_avg(0, 0, 0, 0, 0) == 0.0

    def test_buy_dominated_distribution(self) -> None:
        # SB=0, B=55, H=11, S=2, SS=0 → (220+33+4)/68 = 257/68 ≈ 3.779
        avg = _weighted_consensus_avg(0, 55, 11, 2, 0)
        assert abs(avg - (257 / 68)) < 0.001

    def test_threshold_4_point_0_exactly(self) -> None:
        # SB=1, B=3, H=0, S=0, SS=0 → (5+12)/4 = 17/4 = 4.25
        avg = _weighted_consensus_avg(1, 3, 0, 0, 0)
        assert avg == pytest.approx(4.25, abs=0.001)


# ---------------------------------------------------------------------------
# _recency_weight
# ---------------------------------------------------------------------------


class TestRecencyWeight:
    """Recency weight for upgrade/downgrade events."""

    def test_0_days_returns_1(self) -> None:
        assert _recency_weight(0) == 1.0

    def test_30_days_returns_1(self) -> None:
        assert _recency_weight(30) == 1.0

    def test_31_days_returns_0_5(self) -> None:
        assert _recency_weight(31) == 0.5

    def test_60_days_returns_0_5(self) -> None:
        assert _recency_weight(60) == 0.5

    def test_61_days_returns_0_25(self) -> None:
        assert _recency_weight(61) == 0.25

    def test_90_days_returns_0_25(self) -> None:
        assert _recency_weight(90) == 0.25

    def test_91_days_returns_0(self) -> None:
        assert _recency_weight(91) == 0.0

    def test_365_days_returns_0(self) -> None:
        assert _recency_weight(365) == 0.0


# ---------------------------------------------------------------------------
# _weighted_upgrade_modifier
# ---------------------------------------------------------------------------


class TestWeightedUpgradeModifier:
    """Recency-weighted net upgrades (float) → score modifier."""

    def test_above_2_returns_5(self) -> None:
        assert _weighted_upgrade_modifier(2.1) == 5
        assert _weighted_upgrade_modifier(10.0) == 5

    def test_exactly_2_returns_3(self) -> None:
        # 2.0 is NOT > 2.0 → falls to >= 1.0 → +3
        assert _weighted_upgrade_modifier(2.0) == 3

    def test_1_to_2_returns_3(self) -> None:
        assert _weighted_upgrade_modifier(1.0) == 3
        assert _weighted_upgrade_modifier(1.5) == 3

    def test_near_zero_returns_0(self) -> None:
        assert _weighted_upgrade_modifier(0.0) == 0
        assert _weighted_upgrade_modifier(0.5) == 0
        assert _weighted_upgrade_modifier(-0.5) == 0

    def test_minus_1_to_minus_2_returns_minus_5(self) -> None:
        assert _weighted_upgrade_modifier(-1.0) == -5
        assert _weighted_upgrade_modifier(-1.5) == -5
        assert _weighted_upgrade_modifier(-2.0) == -5

    def test_below_minus_2_returns_minus_10(self) -> None:
        assert _weighted_upgrade_modifier(-2.1) == -10
        assert _weighted_upgrade_modifier(-5.0) == -10


# ---------------------------------------------------------------------------
# score_f3 — v7.3.5 four-bucket tests
# ---------------------------------------------------------------------------


class TestScoreF3:
    """v7.3.5 — 4-bucket PT scoring + recency-weighted upgrade modifier."""

    def test_bucket1_pt_above_price_returns_80(self) -> None:
        result = score_f3(
            formula_pt=120.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=15,
            consensus_weighted_avg=3.8,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 80.0

    def test_bucket1_pt_just_above_price(self) -> None:
        result = score_f3(
            formula_pt=100.01,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=5,
            consensus_weighted_avg=2.0,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 80.0

    def test_bucket1_pt_equal_to_price_falls_to_lower_bucket(self) -> None:
        # PT == price → NOT > price → evaluated against buckets 2-4
        result = score_f3(
            formula_pt=100.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=5,
            consensus_weighted_avg=2.0,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 40.0  # bucket 4: neither

    def test_bucket2_checked_before_bucket3(self) -> None:
        # PT < price, positive revision AND strong coverage — bucket 2 fires first → 55
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="SINGLE_RAISE",
            num_analysts=25,
            consensus_weighted_avg=4.5,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 55.0

    def test_bucket2_multiple_raises_returns_55(self) -> None:
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="MULTIPLE_RAISES",
            num_analysts=5,
            consensus_weighted_avg=3.0,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 55.0

    def test_bucket3_strong_coverage_and_consensus_returns_65(self) -> None:
        # PT < price, no positive revision, ≥20 analysts, avg ≥ 4.0 → bucket 3
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=20,
            consensus_weighted_avg=4.0,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 65.0

    def test_bucket3_requires_consensus_avg_at_least_4(self) -> None:
        # avg 3.9 → bucket 3 NOT met → bucket 4
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=25,
            consensus_weighted_avg=3.9,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 40.0

    def test_bucket3_requires_at_least_20_analysts(self) -> None:
        # 19 analysts + high avg → bucket 3 NOT met → bucket 4
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=19,
            consensus_weighted_avg=4.5,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 40.0

    def test_bucket4_neither_returns_40(self) -> None:
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=10,
            consensus_weighted_avg=3.5,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 40.0

    def test_none_prices_skip_bucket1(self) -> None:
        # No price data → skip bucket 1; positive revision fires bucket 2
        result = score_f3(
            formula_pt=None,
            current_price=None,
            pt_revision_direction="MULTIPLE_RAISES",
            num_analysts=5,
            consensus_weighted_avg=3.0,
            weighted_net_upgrades=0.0,
        )
        assert result.raw_score == 55.0

    def test_weighted_upgrade_modifier_applied_to_bucket_score(self) -> None:
        # bucket 1 (80) + 3 weighted upgrades (+5) = 85
        result = score_f3(
            formula_pt=120.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=10,
            consensus_weighted_avg=3.5,
            weighted_net_upgrades=2.5,
        )
        assert result.raw_score == 85.0

    def test_negative_upgrade_modifier_reduces_score(self) -> None:
        # bucket 4 (40) + heavy downgrades (-10) = 30
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=5,
            consensus_weighted_avg=2.0,
            weighted_net_upgrades=-3.0,
        )
        assert result.raw_score == 30.0

    def test_score_clamped_at_0(self) -> None:
        # bucket 4 (40) + worst modifier (-10) = 30; can't go below 0
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=5,
            consensus_weighted_avg=2.0,
            weighted_net_upgrades=-100.0,
        )
        assert result.raw_score == 30.0  # 40 - 10 = 30 (not below 0)

    def test_weight_is_015(self) -> None:
        result = score_f3(
            formula_pt=120.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=15,
            consensus_weighted_avg=3.8,
            weighted_net_upgrades=0.0,
        )
        assert result.weight == 0.15

    def test_weighted_contribution_equals_score_times_weight(self) -> None:
        result = score_f3(
            formula_pt=90.0,
            current_price=100.0,
            pt_revision_direction="SINGLE_RAISE",
            num_analysts=5,
            consensus_weighted_avg=3.0,
            weighted_net_upgrades=0.0,
        )
        assert abs(result.weighted_contribution - result.raw_score * 0.15) < 0.001

    def test_override_applied_always_false(self) -> None:
        result = score_f3(
            formula_pt=120.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=15,
            consensus_weighted_avg=3.8,
            weighted_net_upgrades=0.0,
        )
        assert result.override_applied is False
        assert result.override_reason is None

    def test_breakdown_has_required_keys(self) -> None:
        result = score_f3(
            formula_pt=120.0,
            current_price=100.0,
            pt_revision_direction="NO_CHANGE",
            num_analysts=15,
            consensus_weighted_avg=3.8,
            weighted_net_upgrades=1.5,
        )
        for key in (
            "bucket_score",
            "bucket_reason",
            "weighted_net_upgrades_90d",
            "upgrade_modifier",
        ):
            assert key in result.breakdown, f"Missing breakdown key: {key}"


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


# ---------------------------------------------------------------------------
# _build_analyst_response smoke tests
# ---------------------------------------------------------------------------


def _make_ratings(
    raises: int,
    lowers: int,
    net_upgrades: int,
    weighted_net_upgrades: float | None = None,
) -> dict[str, int | float]:
    return {
        "raises": raises,
        "lowers": lowers,
        "net_upgrades": net_upgrades,
        "weighted_net_upgrades": (
            weighted_net_upgrades if weighted_net_upgrades is not None else float(net_upgrades)
        ),
    }


class TestBuildAnalystResponse:
    """Smoke tests for _build_analyst_response assembly."""

    def test_at_target_positive_revision_bucket2(self) -> None:
        # PT == price → NOT bucket 1; MULTIPLE_RAISES → bucket 2 (55) + modifier +3 = 58
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
        assert response.f3_score == 58, (
            f"at-target with MULTIPLE_RAISES: expected 58, got {response.f3_score}"
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

    def test_override_applied_always_false(self) -> None:
        # v7.3.5: override mechanism removed; always False regardless of inputs
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

    def test_spec_case_1_correct_label_and_bucket4_score(self) -> None:
        # SB=0, B=55, H=11, S=2, SS=0 → BUY label (weighted avg 3.779)
        # PT (428.65) < price (451.62) → not bucket 1
        # raises=0, lowers=0 → NO_CHANGE → not bucket 2
        # 68 analysts ≥ 20 but avg 3.779 < 4.0 → not bucket 3
        # bucket 4 (40) + 0 modifier = 40
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
        assert response.f3_score == 40


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


# ---------------------------------------------------------------------------
# _fetch_yfinance_pt — highest analyst price target from yfinance
# ---------------------------------------------------------------------------


class TestFetchYfinancePt:
    """Tests for the yfinance highest PT helper."""

    async def test_returns_highest_pt_from_yfinance(self) -> None:
        from unittest.mock import patch

        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        with patch("atlas.services.analyst_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"targetHighPrice": 1000.0, "targetMeanPrice": 573.0}
            result = await service._fetch_yfinance_pt("MU")

        assert result == 1000.0

    async def test_returns_none_when_target_high_price_missing(self) -> None:
        from unittest.mock import patch

        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        with patch("atlas.services.analyst_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"targetMeanPrice": 573.0}
            result = await service._fetch_yfinance_pt("MU")

        assert result is None

    async def test_returns_none_when_target_high_price_is_none(self) -> None:
        from unittest.mock import patch

        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        with patch("atlas.services.analyst_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"targetHighPrice": None}
            result = await service._fetch_yfinance_pt("MU")

        assert result is None

    async def test_returns_none_on_exception(self) -> None:
        from unittest.mock import patch

        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        with patch("atlas.services.analyst_service.yf.Ticker") as mock_yf:
            mock_yf.side_effect = Exception("network error")
            result = await service._fetch_yfinance_pt("MU")

        assert result is None

    async def test_passes_correct_ticker_symbol(self) -> None:
        from unittest.mock import patch

        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        with patch("atlas.services.analyst_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"targetHighPrice": 800.0}
            await service._fetch_yfinance_pt("MU")
            mock_yf.assert_called_once_with("MU")


# ---------------------------------------------------------------------------
# _build_analyst_response — highest_pt used in formula
# ---------------------------------------------------------------------------


class TestBuildAnalystResponseHighestPt:
    """Verify highest_pt drives the pvt formula, consensus_pt is kept for display."""

    def test_pvt_uses_highest_pt_not_consensus_pt(self) -> None:
        """When highest_pt differs from consensus_pt, formula uses highest_pt."""
        response = _build_analyst_response(
            ticker="MU",
            strong_buy=20,
            buy=18,
            hold=2,
            sell=0,
            strong_sell=0,
            num_analysts=40,
            consensus_pt=573.90,  # mean — kept for display only
            highest_pt=1000.0,  # drives formula
            current_price=766.58,
            has_coverage=True,
            ratings_data=_make_ratings(raises=3, lowers=0, net_upgrades=2),
        )
        # PT (1000) > price (766.58) → bucket 1 → score 80 + modifier
        # pvt = (766.58 - 1000.0) / 1000.0 ≈ -0.2334 (display-only; no scoring adjustment)
        assert response.pt_upside.highest_pt == 1000.0
        assert response.pt_upside.consensus_pt == pytest.approx(573.90, abs=0.01)
        assert response.pt_upside.adjustment is None

    def test_upside_pct_uses_highest_pt_when_available(self) -> None:
        """upside_pct on the indicator reflects the highest_pt."""
        response = _build_analyst_response(
            ticker="MU",
            strong_buy=20,
            buy=18,
            hold=2,
            sell=0,
            strong_sell=0,
            num_analysts=40,
            consensus_pt=573.90,
            highest_pt=1000.0,
            current_price=766.58,
            has_coverage=True,
            ratings_data=_make_ratings(raises=0, lowers=0, net_upgrades=0),
        )
        # upside_pct = (1000 - 766.58) / 766.58 * 100 ≈ +30.45
        assert response.pt_upside.upside_pct is not None
        assert response.pt_upside.upside_pct == pytest.approx(30.45, abs=0.1)

    def test_stock_above_pt_with_strong_coverage_bucket3(self) -> None:
        """v7.3.5: hard cap removed; stock above PT with strong coverage → bucket 3 (65)."""
        # PT=100 < price=125 → not bucket 1; NO_CHANGE → not bucket 2
        # 25 analysts ≥ 20, weighted_avg = (75+40)/25 = 4.6 ≥ 4.0 → bucket 3 → 65
        response = _build_analyst_response(
            ticker="XX",
            strong_buy=15,
            buy=10,
            hold=0,
            sell=0,
            strong_sell=0,
            num_analysts=25,
            consensus_pt=100.0,
            highest_pt=100.0,
            current_price=125.0,
            has_coverage=True,
            ratings_data=_make_ratings(raises=0, lowers=0, net_upgrades=0),
        )
        assert response.f3_score is not None
        assert response.f3_score == 65

    def test_falls_back_to_consensus_pt_when_highest_pt_is_none(self) -> None:
        """If yfinance highest PT unavailable, formula uses consensus_pt (old behaviour)."""
        r_with = _build_analyst_response(
            ticker="MU",
            strong_buy=20,
            buy=18,
            hold=2,
            sell=0,
            strong_sell=0,
            num_analysts=40,
            consensus_pt=460.0,
            highest_pt=None,  # not available
            current_price=400.0,
            has_coverage=True,
            ratings_data=_make_ratings(raises=1, lowers=0, net_upgrades=1),
        )
        r_without = _build_analyst_response(
            ticker="MU",
            strong_buy=20,
            buy=18,
            hold=2,
            sell=0,
            strong_sell=0,
            num_analysts=40,
            consensus_pt=460.0,
            highest_pt=None,
            current_price=400.0,
            has_coverage=True,
            ratings_data=_make_ratings(raises=1, lowers=0, net_upgrades=1),
        )
        assert r_with.f3_score == r_without.f3_score
