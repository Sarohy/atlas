"""Unit tests for EarningsService — pure calculation functions.

All Alpha Vantage HTTP calls are mocked; these tests cover only the
computation logic that is deterministic from known inputs.

F2 Earnings Quality — Factor_Mapping_Guide weights:
  Revenue Growth YoY      30%   max 30 pts
  EPS Beat History (3Q)   20%   max 20 pts
  Guidance Direction      20%   max 20 pts
  Gross Margin Trend      15%   max 15 pts
  Backlog / Visibility    15%   max 15 pts
  TOTAL                  100%   max 100 pts

LITE Example (from guide):
  Revenue +65% YoY          -> raw 90  -> contrib 27.0
  EPS 3 consecutive beats   -> raw 100 -> contrib 20.0
  Guidance raised full year -> raw 100 -> contrib 20.0
  Margins expanding (+2pt)  -> raw 80  -> contrib 12.0
  Backlog $400M+ explicit   -> raw 100 -> contrib 15.0
  TOTAL = 94 pts (guide shows 93 due to slightly different rounding)
"""

from __future__ import annotations

import pytest

from atlas.services.earnings_service import (
    _classify_backlog_from_transcript,
    _classify_guidance_from_transcript,
    _compute_f2_total,
    _grade_from_total,
    _score_backlog_visibility,
    _score_eps_beat_history,
    _score_gross_margin_trend,
    _score_guidance_direction,
    _score_revenue_growth_yoy,
)

# ---------------------------------------------------------------------------
# Revenue Growth YoY
# ---------------------------------------------------------------------------


class TestScoreRevenueGrowthYoy:
    """Factor Guide bands: >100->100, >=50->90, >=25->75, >=10->60, >=0->45, <0->20."""

    def test_above_100_pct_scores_100(self) -> None:
        assert _score_revenue_growth_yoy(150.0) == 100

    def test_exactly_100_pct_scores_90(self) -> None:
        # boundary: exactly 100 is NOT >100 so it falls to >=50 band
        assert _score_revenue_growth_yoy(100.0) == 90

    def test_65_pct_scores_90_lite_example(self) -> None:
        # LITE: Revenue +65% YoY -> 90 pts
        assert _score_revenue_growth_yoy(65.0) == 90

    def test_50_pct_scores_90(self) -> None:
        assert _score_revenue_growth_yoy(50.0) == 90

    def test_just_below_50_scores_75(self) -> None:
        assert _score_revenue_growth_yoy(49.9) == 75

    def test_25_pct_scores_75(self) -> None:
        assert _score_revenue_growth_yoy(25.0) == 75

    def test_10_pct_scores_60(self) -> None:
        assert _score_revenue_growth_yoy(10.0) == 60

    def test_5_pct_scores_45(self) -> None:
        assert _score_revenue_growth_yoy(5.0) == 45

    def test_zero_scores_45(self) -> None:
        assert _score_revenue_growth_yoy(0.0) == 45

    def test_negative_scores_20(self) -> None:
        assert _score_revenue_growth_yoy(-10.0) == 20

    def test_none_scores_0(self) -> None:
        assert _score_revenue_growth_yoy(None) == 0


# ---------------------------------------------------------------------------
# EPS Beat History (rolling 3-quarter window)
# ---------------------------------------------------------------------------


class TestScoreEpsBeatHistory:
    """Factor Guide: 3 consecutive->100, 2 of 3->80, 1 of 3->55, 0 of 3->20."""

    def test_3_beats_scores_100_lite_example(self) -> None:
        # LITE: 3 consecutive EPS beats -> 100 pts
        assert _score_eps_beat_history(3) == 100

    def test_2_beats_scores_80(self) -> None:
        assert _score_eps_beat_history(2) == 80

    def test_1_beat_scores_55(self) -> None:
        assert _score_eps_beat_history(1) == 55

    def test_0_beats_scores_20(self) -> None:
        assert _score_eps_beat_history(0) == 20


# ---------------------------------------------------------------------------
# Guidance Direction (from transcript label)
# ---------------------------------------------------------------------------


class TestScoreGuidanceDirection:
    """Factor Guide: Raise full year->100, Maintain->70, Narrow range->55, Lower->20."""

    def test_raise_full_year_scores_100_lite_example(self) -> None:
        # LITE: guidance raised full year -> 100 pts
        assert _score_guidance_direction("RAISE_FULL_YEAR") == 100

    def test_maintain_scores_70(self) -> None:
        assert _score_guidance_direction("MAINTAIN") == 70

    def test_narrow_range_scores_55(self) -> None:
        assert _score_guidance_direction("NARROW_RANGE") == 55

    def test_lower_scores_20(self) -> None:
        assert _score_guidance_direction("LOWER") == 20

    def test_unknown_label_scores_55(self) -> None:
        # Unknown / no_commentary defaults to NARROW_RANGE (55)
        assert _score_guidance_direction("UNKNOWN") == 55


# ---------------------------------------------------------------------------
# Gross Margin Trend (ppt change)
# ---------------------------------------------------------------------------


class TestScoreGrossMarginTrend:
    """Factor Guide: Expanding >3pts->100, 1-3pts->80, Flat->60, Contracting->30."""

    def test_expanding_more_than_3_pts_scores_100(self) -> None:
        assert _score_gross_margin_trend(4.0) == 100

    def test_expanding_exactly_3_pts_scores_80(self) -> None:
        # exactly 3 is NOT >3, falls into 1-3 band
        assert _score_gross_margin_trend(3.0) == 80

    def test_expanding_2_pts_scores_80_lite_example(self) -> None:
        # LITE: margins expanding -> 80 pts (1-3 pt range)
        assert _score_gross_margin_trend(2.0) == 80

    def test_expanding_1_pt_scores_80(self) -> None:
        assert _score_gross_margin_trend(1.0) == 80

    def test_flat_near_zero_scores_60(self) -> None:
        assert _score_gross_margin_trend(0.0) == 60

    def test_flat_slightly_negative_scores_60(self) -> None:
        assert _score_gross_margin_trend(-0.5) == 60

    def test_contracting_more_than_1_scores_30(self) -> None:
        assert _score_gross_margin_trend(-2.0) == 30

    def test_none_scores_neutral_60(self) -> None:
        # When no data, neutral (flat) score
        assert _score_gross_margin_trend(None) == 60


# ---------------------------------------------------------------------------
# Backlog / Visibility (from transcript label)
# ---------------------------------------------------------------------------


class TestScoreBacklogVisibility:
    """Factor Guide: Explicit multi-quarter->100, Strong->80, Limited->50, No commentary->30."""

    def test_explicit_multi_quarter_scores_100_lite_example(self) -> None:
        # LITE: OCS backlog $400M+ -> 100 pts
        assert _score_backlog_visibility("EXPLICIT_MULTI_QUARTER") == 100

    def test_strong_scores_80(self) -> None:
        assert _score_backlog_visibility("STRONG") == 80

    def test_limited_scores_50(self) -> None:
        assert _score_backlog_visibility("LIMITED") == 50

    def test_no_commentary_scores_30(self) -> None:
        assert _score_backlog_visibility("NO_COMMENTARY") == 30

    def test_unknown_label_defaults_to_30(self) -> None:
        assert _score_backlog_visibility("UNKNOWN") == 30


# ---------------------------------------------------------------------------
# Guidance transcript classifier
# ---------------------------------------------------------------------------


class TestClassifyGuidanceFromTranscript:
    def test_raise_full_year_pattern(self) -> None:
        text = (
            "We are pleased to raise our full-year guidance for fiscal 2024 "
            "to reflect the strong performance across all segments."
        )
        assert _classify_guidance_from_transcript(text) == "RAISE_FULL_YEAR"

    def test_raised_guidance_pattern(self) -> None:
        text = "Management raised guidance for the full year to $5.20-$5.40 EPS."
        assert _classify_guidance_from_transcript(text) == "RAISE_FULL_YEAR"

    def test_lowered_guidance_pattern(self) -> None:
        text = "We lowered our full-year guidance due to macro headwinds."
        assert _classify_guidance_from_transcript(text) == "LOWER"

    def test_maintain_guidance_pattern(self) -> None:
        text = "We are reaffirming and maintaining guidance for the full year."
        assert _classify_guidance_from_transcript(text) == "MAINTAIN"

    def test_narrow_range_pattern(self) -> None:
        text = "We have narrowed our guidance range given improved visibility."
        assert _classify_guidance_from_transcript(text) == "NARROW_RANGE"

    def test_empty_transcript_returns_maintain(self) -> None:
        assert _classify_guidance_from_transcript("") == "MAINTAIN"

    def test_case_insensitive(self) -> None:
        text = "RAISED OUR FULL-YEAR GUIDANCE RANGE."
        assert _classify_guidance_from_transcript(text) == "RAISE_FULL_YEAR"


# ---------------------------------------------------------------------------
# Backlog transcript classifier
# ---------------------------------------------------------------------------


class TestClassifyBacklogFromTranscript:
    def test_explicit_dollar_backlog(self) -> None:
        text = (
            "Our backlog stands at $1.2 billion, providing visibility "
            "into the next several quarters."
        )
        assert _classify_backlog_from_transcript(text) == "EXPLICIT_MULTI_QUARTER"

    def test_record_backlog(self) -> None:
        text = "We ended the quarter with a record backlog of 18 months."
        assert _classify_backlog_from_transcript(text) == "EXPLICIT_MULTI_QUARTER"

    def test_strong_demand_commentary(self) -> None:
        text = "We continue to see strong demand and a growing pipeline across all verticals."
        assert _classify_backlog_from_transcript(text) == "STRONG"

    def test_limited_visibility(self) -> None:
        text = "Visibility into Q4 remains limited given uncertain demand environment."
        assert _classify_backlog_from_transcript(text) == "LIMITED"

    def test_no_backlog_commentary(self) -> None:
        text = "Revenue came in at $500M, slightly above consensus."
        assert _classify_backlog_from_transcript(text) == "NO_COMMENTARY"

    def test_case_insensitive(self) -> None:
        text = "BACKLOG IS NOW $400 MILLION, COVERING MULTIPLE QUARTERS."
        assert _classify_backlog_from_transcript(text) == "EXPLICIT_MULTI_QUARTER"


# ---------------------------------------------------------------------------
# Weighted composite F2 total
# ---------------------------------------------------------------------------


class TestComputeF2Total:
    def test_lite_example_scores_94(self) -> None:
        """LITE: Rev 90x0.30 + EPS 100x0.20 + Guid 100x0.20 + Margin 80x0.15 + Backlog 100x0.15 = 94."""
        total = _compute_f2_total(
            rev_raw=90,
            eps_raw=100,
            guidance_raw=100,
            margin_raw=80,
            backlog_raw=100,
        )
        assert total == 94

    def test_perfect_score_is_100(self) -> None:
        total = _compute_f2_total(100, 100, 100, 100, 100)
        assert total == 100

    def test_all_raw_zero_is_0(self) -> None:
        total = _compute_f2_total(0, 0, 0, 0, 0)
        assert total == 0

    def test_capped_at_100(self) -> None:
        # Even if raw scores somehow exceed 100, total is capped.
        total = _compute_f2_total(200, 200, 200, 200, 200)
        assert total == 100


# ---------------------------------------------------------------------------
# F2 grade boundaries
# ---------------------------------------------------------------------------


class TestF2GradeBoundaries:
    """Factor Guide (same as F1):
    >=80 STRONG BUY | >=65 BUY | >=40 NEUTRAL | >=20 WEAK | <20 AVOID.
    """

    def test_strong_buy_at_80(self) -> None:
        assert _grade_from_total(80) == "STRONG BUY"

    def test_strong_buy_at_100(self) -> None:
        assert _grade_from_total(100) == "STRONG BUY"

    def test_buy_at_65(self) -> None:
        assert _grade_from_total(65) == "BUY"

    def test_buy_at_79(self) -> None:
        assert _grade_from_total(79) == "BUY"

    def test_neutral_at_40(self) -> None:
        assert _grade_from_total(40) == "NEUTRAL"

    def test_neutral_at_64(self) -> None:
        assert _grade_from_total(64) == "NEUTRAL"

    def test_weak_at_20(self) -> None:
        assert _grade_from_total(20) == "WEAK"

    def test_weak_at_39(self) -> None:
        assert _grade_from_total(39) == "WEAK"

    def test_avoid_at_19(self) -> None:
        assert _grade_from_total(19) == "AVOID"

    def test_avoid_at_0(self) -> None:
        assert _grade_from_total(0) == "AVOID"

    def test_lite_example_94_is_strong_buy(self) -> None:
        assert _grade_from_total(94) == "STRONG BUY"
