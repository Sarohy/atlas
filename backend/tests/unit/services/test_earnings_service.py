"""Unit tests for EarningsService — F2 Earnings Quality scoring, v7.3.4 spec.

F2 v7.3.4 uses a weighted sub-factor approach (not equal max-20 sum):
  Sub-Factor 1: Revenue Growth YoY       30%  — scored 0-100 (decimal: 0.29 = 29%)
  Sub-Factor 2: Gross Margin Trend       20%  — scored 0-100, bps change YoY
  Sub-Factor 3: EPS Beat Consistency     20%  — scored 0-100, 4Q window; excluded if pre-profit
  Sub-Factor 4: Guidance Reliability     15%  — scored 0-100, 4Q track record
                                               DATA_GAP default: 10 (Bloomberg not V1)
  Sub-Factor 5: Forward Visibility       15%  — scored 0/30/60/80/100 from transcript NLP

  f2_raw = weighted sum (max 100)
  f2_contribution = f2_raw * 0.25

Pre-profitability: when net_income_ttm < 0
  → exclude sf3_eps_consistency
  → re-weight remaining 4: sf1=37.5%, sf2=25%, sf4=18.75%, sf5=18.75%
"""

from __future__ import annotations

import pytest

from atlas.services.earnings_service import (
    _classify_forward_visibility_from_transcript,
    _grade_from_total,
    _score_eps_consistency_4q,
    _score_forward_visibility,
    _score_gross_margin_trend_v2,
    _score_guidance_reliability,
    _score_revenue_growth_v2,
    score_f2,
)


# ---------------------------------------------------------------------------
# Revenue Growth YoY — v7.3.4 bands (input as decimal fraction)
# ---------------------------------------------------------------------------


class TestScoreRevenueGrowthV2:
    """v7.3.4 bands: >40%→100, 30-40%→92, 20-30%→85, 15-20%→78, 10-15%→70,
    5-10%→60, 0-5%→45, negative→20.  Input is decimal: 0.29 = 29%.
    """

    def test_above_40pct_scores_100(self) -> None:
        assert _score_revenue_growth_v2(0.41) == 100.0

    def test_exactly_40pct_scores_92(self) -> None:
        # "Above 40%" is strictly >40%; exactly 40% falls in 30-40% band.
        assert _score_revenue_growth_v2(0.40) == 92.0

    def test_30_to_40pct_scores_92(self) -> None:
        assert _score_revenue_growth_v2(0.35) == 92.0

    def test_20_to_30pct_scores_85(self) -> None:
        # Test-1 bug case: +29% YoY → 85
        assert _score_revenue_growth_v2(0.29) == 85.0

    def test_15_to_20pct_scores_78(self) -> None:
        assert _score_revenue_growth_v2(0.17) == 78.0

    def test_exactly_15pct_scores_78(self) -> None:
        assert _score_revenue_growth_v2(0.15) == 78.0

    def test_10_to_15pct_scores_70(self) -> None:
        assert _score_revenue_growth_v2(0.12) == 70.0

    def test_5_to_10pct_scores_60(self) -> None:
        assert _score_revenue_growth_v2(0.07) == 60.0

    def test_0_to_5pct_scores_45(self) -> None:
        assert _score_revenue_growth_v2(0.03) == 45.0

    def test_exactly_0pct_scores_45(self) -> None:
        assert _score_revenue_growth_v2(0.0) == 45.0

    def test_negative_scores_20(self) -> None:
        # Test-3 case: -8% → 20
        assert _score_revenue_growth_v2(-0.08) == 20.0


# ---------------------------------------------------------------------------
# Gross Margin Trend — v7.3.4 bps bands
# ---------------------------------------------------------------------------


class TestScoreGrossMarginTrendV2:
    """bps bands: >300→100, 100-300→85, 50-100→70, flat ±50→60,
    contracting 50-100→45, 100-300→30, >300→15.
    """

    def test_expanding_more_than_300bps_scores_100(self) -> None:
        assert _score_gross_margin_trend_v2(350.0) == 100.0

    def test_expanding_exactly_300bps_scores_85(self) -> None:
        # "more than 300bps" is strictly >300; 300bps falls in 100-300 band.
        assert _score_gross_margin_trend_v2(300.0) == 85.0

    def test_expanding_200bps_scores_85(self) -> None:
        # Test-1: +200bps → 85
        assert _score_gross_margin_trend_v2(200.0) == 85.0

    def test_expanding_150bps_scores_85(self) -> None:
        # Test-2: +150bps → 85
        assert _score_gross_margin_trend_v2(150.0) == 85.0

    def test_expanding_exactly_100bps_scores_85(self) -> None:
        assert _score_gross_margin_trend_v2(100.0) == 85.0

    def test_expanding_75bps_scores_70(self) -> None:
        assert _score_gross_margin_trend_v2(75.0) == 70.0

    def test_flat_zone_plus_50bps_scores_60(self) -> None:
        # Exactly ±50 is the flat zone boundary (inclusive).
        assert _score_gross_margin_trend_v2(50.0) == 60.0

    def test_flat_zone_zero_scores_60(self) -> None:
        assert _score_gross_margin_trend_v2(0.0) == 60.0

    def test_flat_zone_minus_50bps_scores_60(self) -> None:
        assert _score_gross_margin_trend_v2(-50.0) == 60.0

    def test_contracting_50_to_100bps_scores_45(self) -> None:
        assert _score_gross_margin_trend_v2(-75.0) == 45.0

    def test_contracting_100_to_300bps_scores_30(self) -> None:
        assert _score_gross_margin_trend_v2(-200.0) == 30.0

    def test_contracting_more_than_300bps_scores_15(self) -> None:
        # Test-6: -600bps → 15
        assert _score_gross_margin_trend_v2(-600.0) == 15.0


# ---------------------------------------------------------------------------
# EPS Beat Consistency — 4Q window with limited history support
# ---------------------------------------------------------------------------


class TestScoreEpsConsistency4Q:
    """4/4→100, 3/4→80, 2/4→55, 1/4→30, 0/4→0.
    Limited history (<4Q): score by beat_rate mapped to same bands.
    """

    def test_4_of_4_beats_scores_100(self) -> None:
        assert _score_eps_consistency_4q(4, 4) == 100.0

    def test_3_of_4_beats_scores_80(self) -> None:
        assert _score_eps_consistency_4q(3, 4) == 80.0

    def test_2_of_4_beats_scores_55(self) -> None:
        assert _score_eps_consistency_4q(2, 4) == 55.0

    def test_1_of_4_beats_scores_30(self) -> None:
        assert _score_eps_consistency_4q(1, 4) == 30.0

    def test_0_of_4_beats_scores_0(self) -> None:
        assert _score_eps_consistency_4q(0, 4) == 0.0

    # IPO / limited history — proportional scoring
    def test_2_of_2_beats_ipo_scores_100(self) -> None:
        # beat_rate = 1.0 → equivalent to 4/4 → 100.  Test-5.
        assert _score_eps_consistency_4q(2, 2) == 100.0

    def test_1_of_2_beats_ipo_scores_55(self) -> None:
        # beat_rate = 0.5 → equivalent to 2/4 → 55.
        assert _score_eps_consistency_4q(1, 2) == 55.0

    def test_0_of_2_beats_ipo_scores_0(self) -> None:
        assert _score_eps_consistency_4q(0, 2) == 0.0

    def test_1_of_1_beats_ipo_scores_100(self) -> None:
        assert _score_eps_consistency_4q(1, 1) == 100.0


# ---------------------------------------------------------------------------
# Guidance Reliability — 4Q track record
# ---------------------------------------------------------------------------


class TestScoreGuidanceReliability:
    """4/4→100, 3/4→80, 2/4→55, 1/4→30, 0/4→0.
    DATA_GAP default (10) is applied by score_f2(), not here.
    """

    def test_4_of_4_delivered_scores_100(self) -> None:
        assert _score_guidance_reliability(4) == 100.0

    def test_3_of_4_delivered_scores_80(self) -> None:
        assert _score_guidance_reliability(3) == 80.0

    def test_2_of_4_delivered_scores_55(self) -> None:
        assert _score_guidance_reliability(2) == 55.0

    def test_1_of_4_delivered_scores_30(self) -> None:
        assert _score_guidance_reliability(1) == 30.0

    def test_0_of_4_delivered_scores_0(self) -> None:
        assert _score_guidance_reliability(0) == 0.0


# ---------------------------------------------------------------------------
# Forward Visibility — label to score mapping
# ---------------------------------------------------------------------------


class TestScoreForwardVisibility:
    """SPECIFIC_RAISED→100, SPECIFIC_MAINTAINED→80, DIRECTIONAL→60,
    VAGUE_NONE→30, WITHDRAWN_REDUCED→0.
    """

    def test_specific_raised_scores_100(self) -> None:
        assert _score_forward_visibility("SPECIFIC_RAISED") == 100

    def test_specific_maintained_scores_80(self) -> None:
        assert _score_forward_visibility("SPECIFIC_MAINTAINED") == 80

    def test_directional_scores_60(self) -> None:
        assert _score_forward_visibility("DIRECTIONAL") == 60

    def test_vague_none_scores_30(self) -> None:
        assert _score_forward_visibility("VAGUE_NONE") == 30

    def test_withdrawn_reduced_scores_0(self) -> None:
        assert _score_forward_visibility("WITHDRAWN_REDUCED") == 0

    def test_unknown_label_defaults_to_vague_none_score_30(self) -> None:
        assert _score_forward_visibility("UNKNOWN") == 30


# ---------------------------------------------------------------------------
# Forward Visibility Transcript Classifier
# ---------------------------------------------------------------------------


class TestClassifyForwardVisibilityFromTranscript:
    def test_raised_guidance_classified_specific_raised(self) -> None:
        text = "We are raising our full-year revenue guidance to $5.2 billion."
        assert _classify_forward_visibility_from_transcript(text) == "SPECIFIC_RAISED"

    def test_reiterated_guidance_classified_specific_maintained(self) -> None:
        text = "We are reiterating our full-year guidance of $4.5 to $4.7 billion."
        assert _classify_forward_visibility_from_transcript(text) == "SPECIFIC_MAINTAINED"

    def test_withdrawn_guidance_classified_withdrawn_reduced(self) -> None:
        text = "We are withdrawing our guidance given macro uncertainty."
        assert _classify_forward_visibility_from_transcript(text) == "WITHDRAWN_REDUCED"

    def test_general_growth_expectation_classified_directional(self) -> None:
        text = "We expect revenue to grow sequentially in the next quarter."
        assert _classify_forward_visibility_from_transcript(text) == "DIRECTIONAL"

    def test_empty_transcript_classified_vague_none(self) -> None:
        assert _classify_forward_visibility_from_transcript("") == "VAGUE_NONE"

    def test_no_guidance_language_classified_vague_none(self) -> None:
        text = "Revenue came in at $1.2 billion, slightly above consensus."
        assert _classify_forward_visibility_from_transcript(text) == "VAGUE_NONE"


# ---------------------------------------------------------------------------
# F2 grade thresholds — unchanged
# ---------------------------------------------------------------------------


class TestGradeFromTotal:
    """≥80 STRONG BUY | ≥65 BUY | ≥40 NEUTRAL | ≥20 WEAK | <20 AVOID."""

    def test_strong_buy_at_80(self) -> None:
        assert _grade_from_total(80) == "STRONG BUY"

    def test_strong_buy_at_100(self) -> None:
        assert _grade_from_total(100) == "STRONG BUY"

    def test_buy_at_79(self) -> None:
        assert _grade_from_total(79) == "BUY"

    def test_buy_at_65(self) -> None:
        assert _grade_from_total(65) == "BUY"

    def test_neutral_at_64(self) -> None:
        assert _grade_from_total(64) == "NEUTRAL"

    def test_neutral_at_40(self) -> None:
        assert _grade_from_total(40) == "NEUTRAL"

    def test_weak_at_39(self) -> None:
        assert _grade_from_total(39) == "WEAK"

    def test_weak_at_20(self) -> None:
        assert _grade_from_total(20) == "WEAK"

    def test_avoid_at_19(self) -> None:
        assert _grade_from_total(19) == "AVOID"

    def test_avoid_at_0(self) -> None:
        assert _grade_from_total(0) == "AVOID"


# ---------------------------------------------------------------------------
# score_f2 — 7 spec test cases (v7.3.4)
# ---------------------------------------------------------------------------


class TestScoreF2:
    """Spec test cases 1-7 per v7.3.4 F2 specification."""

    def test_1_bug_report_fn_case_scores_76(self) -> None:
        """Test 1 — the originally reported bug.

        Input: +29% revenue, +200bps margin, 4/4 EPS, DATA_GAP guidance, fwd_vis=80.
        Old system scored ~74 due to wrong sub-factor inputs.
        New spec with DATA_GAP: f2_raw = 76.0
        """
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=0.29,
            gross_margin_current=0.45,
            gross_margin_prior_year=0.43,
            eps_beats_last_4q=4,
            eps_quarters_available=4,
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=80,
            net_income_ttm=1_000_000,
        )
        assert result.sf1_score == 85.0   # 20-30% band
        assert result.sf2_score == 85.0   # 200bps, 100-300 band
        assert result.sf3_score == 100.0  # 4/4 beats
        assert result.sf3_excluded is False
        assert result.sf4_score == 10.0   # DATA_GAP default
        assert result.sf4_data_gap is True
        assert result.sf5_score == 80.0
        # f2_raw = 85*0.30 + 85*0.20 + 100*0.20 + 10*0.15 + 80*0.15
        #        = 25.5 + 17.0 + 20.0 + 1.5 + 12.0 = 76.0
        assert abs(result.f2_raw - 76.0) < 0.01
        assert abs(result.f2_contribution - 19.0) < 0.01
        assert result.pre_profit_status is False
        assert result.pre_profit_reweighted is False
        assert result.data_gap_applied is True
        assert result.exit_flag is False

    def test_2_pre_profitability_excludes_sf3_and_reweights(self) -> None:
        """Test 2 — pre-profit: sf3 excluded, remaining sub-factors re-weighted.

        Re-weighted: sf1=37.5%, sf2=25%, sf4=18.75%, sf5=18.75%.
        f2_raw = 100*0.375 + 85*0.250 + 10*0.1875 + 60*0.1875 = 71.875
        """
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=0.45,
            gross_margin_current=0.515,
            gross_margin_prior_year=0.500,   # (0.515-0.500)*10000 = 150 bps
            eps_beats_last_4q=0,
            eps_quarters_available=4,
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=60,
            net_income_ttm=-50_000_000,      # negative → pre-profit
        )
        assert result.sf1_score == 100.0   # >40%
        assert result.sf2_score == 85.0    # 150bps, 100-300 band
        assert result.sf3_excluded is True
        assert result.sf3_score is None
        assert result.sf4_score == 10.0    # DATA_GAP
        assert result.sf5_score == 60.0
        assert abs(result.f2_raw - 71.875) < 0.01
        assert result.pre_profit_status is True
        assert result.pre_profit_reweighted is True
        assert result.data_gap_applied is True

    def test_3_declining_revenue_above_pt_triggers_exit_flag(self) -> None:
        """Test 3 — declining revenue + price >20% above PT → exit_flag = True.

        pvt = (120 - 95) / 95 = 0.263 → >20% above PT.
        sf1 = 20 (negative growth).
        """
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=-0.08,
            gross_margin_current=0.38,
            gross_margin_prior_year=0.40,   # -200bps
            eps_beats_last_4q=1,
            eps_quarters_available=4,
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=30,
            net_income_ttm=1_000_000,
            current_price=120.0,
            analyst_target=95.0,
        )
        assert result.sf1_score == 20.0
        assert result.exit_flag is True

    def test_3_exit_flag_not_set_when_price_below_target(self) -> None:
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=-0.08,
            gross_margin_current=0.38,
            gross_margin_prior_year=0.40,
            eps_beats_last_4q=1,
            eps_quarters_available=4,
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=30,
            net_income_ttm=1_000_000,
            current_price=85.0,
            analyst_target=95.0,
        )
        assert result.exit_flag is False

    def test_4_all_guidance_withdrawn_sets_guidance_concern(self) -> None:
        """Test 4 — sf4=0 AND sf5=0 → guidance_concern = True."""
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=0.15,
            gross_margin_current=0.505,
            gross_margin_prior_year=0.500,   # +50bps → flat → 60
            eps_beats_last_4q=2,
            eps_quarters_available=4,
            guidance_reliability_4q=0,
            guidance_data_available=True,
            forward_visibility_score=0,
            net_income_ttm=1_000_000,
        )
        assert result.sf4_score == 0.0
        assert result.sf5_score == 0.0
        assert result.guidance_concern is True
        assert result.sf4_data_gap is False   # data IS available, just zero

    def test_5_ipo_limited_history_scored_proportionally(self) -> None:
        """Test 5 — eps_quarters_available=2, eps_beats=2 → 100 (2/2 = 100% beat rate)."""
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=0.25,
            gross_margin_current=0.45,
            gross_margin_prior_year=0.43,    # +200bps → 85
            eps_beats_last_4q=2,
            eps_quarters_available=2,        # only 2Q available
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=60,
            net_income_ttm=1_000_000,
        )
        assert result.sf3_score == 100.0   # 2/2 → proportional → 100
        assert result.ipo_limited_history is True
        assert result.limited_history is True
        assert result.sf4_data_gap is True

    def test_6_exceptional_revenue_contracting_margins_scored_independently(self) -> None:
        """Test 6 — +42% revenue offset by -600bps margin; no special adjustment.

        f2_raw = 100*0.30 + 15*0.20 + 80*0.20 + 80*0.15 + 80*0.15
               = 30 + 3 + 16 + 12 + 12 = 73.0
        """
        result = score_f2(
            ticker="TEST",
            revenue_growth_yoy=0.42,
            gross_margin_current=0.38,
            gross_margin_prior_year=0.44,   # -600bps → 15
            eps_beats_last_4q=3,
            eps_quarters_available=4,
            guidance_reliability_4q=3,
            guidance_data_available=True,
            forward_visibility_score=80,
            net_income_ttm=1_000_000,
        )
        assert result.sf1_score == 100.0
        assert result.sf2_score == 15.0
        assert result.sf3_score == 80.0
        assert result.sf4_score == 80.0
        assert result.sf5_score == 80.0
        assert abs(result.f2_raw - 73.0) < 0.01
        assert result.guidance_concern is False
        assert result.sf4_data_gap is False

    def test_7_different_tickers_produce_different_results(self) -> None:
        """Test 7 — score_f2 is pure; same function, different inputs → different results.

        MU: sf1=70(12%), sf2=100(+400bps), sf3=80(3/4), sf4=10(DATA_GAP), sf5=60
        f2_raw = 70*0.30 + 100*0.20 + 80*0.20 + 10*0.15 + 60*0.15
               = 21 + 20 + 16 + 1.5 + 9 = 67.5
        """
        result_fn = score_f2(
            ticker="FN",
            revenue_growth_yoy=0.29,
            gross_margin_current=0.45,
            gross_margin_prior_year=0.43,
            eps_beats_last_4q=4,
            eps_quarters_available=4,
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=80,
            net_income_ttm=1_000_000,
        )
        result_mu = score_f2(
            ticker="MU",
            revenue_growth_yoy=0.12,
            gross_margin_current=0.46,
            gross_margin_prior_year=0.42,   # +400bps → 100
            eps_beats_last_4q=3,
            eps_quarters_available=4,
            guidance_reliability_4q=None,
            guidance_data_available=False,
            forward_visibility_score=60,
            net_income_ttm=5_000_000_000,
        )
        assert result_fn.ticker == "FN"
        assert result_mu.ticker == "MU"
        assert abs(result_mu.f2_raw - 67.5) < 0.01
        assert result_fn.f2_raw != result_mu.f2_raw
