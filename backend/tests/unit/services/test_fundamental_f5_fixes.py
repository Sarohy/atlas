"""TDD — RED tests for three F5 fundamental scoring fixes.

Fix 1 — Insider selling penalty:
  Heavy C-suite selling should reduce the score below the NO_ACTIVITY
  baseline of 70, not match it. The current implementation ignores all selling.

Fix 2 — FCF magnitude-aware scoring:
  NEGATIVE_IMPROVING now earns a bonus when the improvement is large
  (≥ 50% reduction in the absolute loss), reflecting a structured
  investment-cycle burn rather than uncontrolled cash drain.

Fix 3 — Gross margin sub-indicator:
  A new gross_margin sub-indicator (weight 0.10) is added to F5.
  To keep the formula summing to 100%, FCF weight drops from 0.20 → 0.15
  and Debt/Equity from 0.15 → 0.10.
  Gross margin scoring:
    ≥ 70%       → 100
    50–70%      →  80
    30–50%      →  60
    10–30%      →  40
    < 10%       →  20
    Unknown     →  60

Fix 4 — Gross margin uses most recent quarter only (not TTM):
  For hyper-growth companies, TTM gross margin is dragged down by legacy
  low-revenue quarters.  F5 now uses the most recent quarterly gross margin
  so the current business profitability is reflected accurately.

Fix 5 — MULTIPLE_SALES recalibrated from 30 → 45:
  The original 30 was too severe for board/legacy-shareholder distribution
  in restructured companies where the CEO/CFO component is small (< $10M).
  The signal is real but the magnitude of the penalty was over-stated.

Fix 6 — Routine diversification: CEO_MEGA_SALE moderated when sell < 3% of FCF:
  For large-cap companies with strong FCF, CEO selling a "mega" amount in absolute
  terms can still be trivially small relative to the company's cash generation.
  When ceo_cfo_sell / fcf_current < 3% and FCF is positive, the label is upgraded
  to ROUTINE_DIVERSIFICATION and scored at baseline 70 (no conviction-loss signal).
  MU pattern: $59.9M CEO sell / $6.5B FCF = 0.92% → score 70 → f5_score 96 → 24/25.

All tests below fail against the current code.
"""

from __future__ import annotations

import pytest

from atlas.services.fundamental_service import (
    _apply_fcf_routine_modifier,  # does not yet exist → ImportError
    _score_fcf,
    _score_gross_margin,   # does not yet exist → ImportError
    _score_insider_activity,
)


# ===========================================================================
# Fix 1 — Insider selling penalty
# ===========================================================================


class TestInsiderSellingPenalty:
    def test_officer_sell_above_1m_scores_below_70(self) -> None:
        """C-suite sale > $1M must score below the NO_ACTIVITY baseline of 70."""
        score, label = _score_insider_activity(0.0, 1_500_000.0, 1, 0.0)
        assert score < 70, f"expected score < 70 for officer sell, got {score}"
        assert label == "SMALL_SALE"

    def test_multiple_officer_sales_score_below_small_sale(self) -> None:
        """≥ 2 separate sale events must score lower than a single small sale."""
        score_single, _ = _score_insider_activity(0.0, 1_500_000.0, 1, 0.0)
        score_multi, label = _score_insider_activity(0.0, 5_000_000.0, 3, 0.0)
        assert score_multi < score_single, (
            f"multiple sales ({score_multi}) should score below single small sale ({score_single})"
        )
        assert label == "MULTIPLE_SALES"

    def test_ceo_cfo_mega_sale_above_10m_scores_20(self) -> None:
        """CEO/CFO sale > $10M must score 20 (CEO_MEGA_SALE)."""
        score, label = _score_insider_activity(0.0, 60_000_000.0, 1, 60_000_000.0)
        assert score == 20
        assert label == "CEO_MEGA_SALE"

    def test_no_buying_no_selling_stays_70(self) -> None:
        """Zero activity still returns 70 NO_ACTIVITY."""
        score, label = _score_insider_activity(0.0, 0.0, 0, 0.0)
        assert score == 70
        assert label == "NO_ACTIVITY"

    def test_net_buying_still_100(self) -> None:
        """Net buying (buys > 0) must still return 100 NET_BUYING."""
        score, label = _score_insider_activity(500_000.0, 0.0, 0, 0.0)
        assert score == 100
        assert label == "NET_BUYING"

    def test_small_sale_below_1m_threshold_stays_70(self) -> None:
        """Sale below the $1M threshold does not trigger a penalty — remains NO_ACTIVITY."""
        score, label = _score_insider_activity(0.0, 800_000.0, 1, 0.0)
        assert score == 70
        assert label == "NO_ACTIVITY"

    def test_exact_1m_threshold_triggers_penalty(self) -> None:
        """Sale of exactly $1M triggers the SMALL_SALE penalty."""
        score, label = _score_insider_activity(0.0, 1_000_000.0, 1, 0.0)
        assert score < 70
        assert label == "SMALL_SALE"

    def test_buying_plus_large_selling_still_returns_net_buying(self) -> None:
        """If there is any net buying the score is NET_BUYING regardless of selling."""
        score, label = _score_insider_activity(2_000_000.0, 15_000_000.0, 3, 10_000_000.0)
        assert score == 100
        assert label == "NET_BUYING"


# ===========================================================================
# Fix 2 — FCF magnitude-aware scoring
# ===========================================================================

# Named constant for the improvement threshold used in the new scoring logic.
# A ≥ 50% reduction in absolute FCF loss qualifies as a "large improvement".
LARGE_FCF_IMPROVEMENT_THRESHOLD = 0.50

# Named constant: expected score for NEGATIVE_IMPROVING with large improvement.
EXPECTED_LARGE_FCF_IMPROVEMENT_SCORE = 50


class TestFcfMagnitudeScoring:
    def test_negative_large_improvement_scores_50(self) -> None:
        """Negative FCF improving ≥ 50% in abs terms → score 50 (NEGATIVE_LARGE_IMPROVEMENT)."""
        # -$214.9M from -$1,221.7M is an 82% improvement in absolute magnitude.
        score, trend = _score_fcf(-214_900_000.0, -1_221_700_000.0)
        assert score == EXPECTED_LARGE_FCF_IMPROVEMENT_SCORE
        assert trend == "NEGATIVE_LARGE_IMPROVEMENT"

    def test_negative_small_improvement_stays_40(self) -> None:
        """Negative FCF improving < 50% still returns 40 NEGATIVE_IMPROVING."""
        # -$900K from -$1.1M is a 18% improvement — below the 50% threshold.
        score, trend = _score_fcf(-900_000.0, -1_100_000.0)
        assert score == 40
        assert trend == "NEGATIVE_IMPROVING"

    def test_negative_exact_50pct_improvement_scores_50(self) -> None:
        """Exactly 50% improvement in absolute loss qualifies for the bonus."""
        score, trend = _score_fcf(-500_000.0, -1_000_000.0)
        assert score == EXPECTED_LARGE_FCF_IMPROVEMENT_SCORE
        assert trend == "NEGATIVE_LARGE_IMPROVEMENT"

    def test_negative_worsening_unchanged(self) -> None:
        """Worsening FCF is unaffected."""
        score, trend = _score_fcf(-900_000.0, -500_000.0)
        assert score == 20
        assert trend == "NEGATIVE_WORSENING"

    def test_positive_scores_unchanged(self) -> None:
        """All positive FCF scoring paths are unaffected."""
        assert _score_fcf(1_200_000, 1_000_000) == (100, "POSITIVE_GROWING")
        assert _score_fcf(1_050_000, 1_000_000) == (80, "POSITIVE_FLAT")
        assert _score_fcf(800_000, 1_000_000) == (60, "POSITIVE_DECLINING")


# ===========================================================================
# Fix 3 — Gross margin sub-indicator
# ===========================================================================


class TestScoreGrossMargin:
    def test_above_70pct_returns_100(self) -> None:
        assert _score_gross_margin(0.74) == 100

    def test_exact_70pct_returns_100(self) -> None:
        assert _score_gross_margin(0.70) == 100

    def test_50_to_70pct_returns_80(self) -> None:
        assert _score_gross_margin(0.60) == 80

    def test_exact_50pct_returns_80(self) -> None:
        assert _score_gross_margin(0.50) == 80

    def test_30_to_50pct_returns_60(self) -> None:
        assert _score_gross_margin(0.40) == 60

    def test_10_to_30pct_returns_40(self) -> None:
        assert _score_gross_margin(0.20) == 40

    def test_below_10pct_returns_20(self) -> None:
        assert _score_gross_margin(0.05) == 20

    def test_zero_margin_returns_20(self) -> None:
        assert _score_gross_margin(0.0) == 20

    def test_none_returns_60_unknown(self) -> None:
        assert _score_gross_margin(None) == 60

    def test_negative_margin_returns_20(self) -> None:
        """Negative gross margin (COGS > revenue) gets the floor score."""
        assert _score_gross_margin(-0.05) == 20


# ===========================================================================
# Integration — composite score reflects all three fixes (NBIS pattern)
# ===========================================================================

# Named constants for the NBIS F5 pattern used in the integration test.
# These mirror the live API values from the session.
NBIS_INSIDER_SELL = 125_917_992.0
NBIS_CEO_CFO_SELL = 3_877_058.0   # below $10M → MULTIPLE_SALES not CEO_MEGA_SALE
NBIS_CSUITE_SELL = 117_656_667.0
NBIS_FCF_CURRENT = -214_900_000.0
NBIS_FCF_PRIOR = -1_221_700_000.0
NBIS_GROSS_MARGIN = 0.74  # 74% gross margin from Q1 filing

# Minimum expected insider score after applying the selling penalty
# ($117.7M C-suite sell, 13 transactions → MULTIPLE_SALES → 45 recalibrated).
EXPECTED_INSIDER_SCORE_NBIS = 45

# FCF score for NBIS pattern (large improvement ≥ 50%).
EXPECTED_FCF_SCORE_NBIS = 50

# Gross margin score for 74% margin.
EXPECTED_GM_SCORE_NBIS = 100


def test_nbis_insider_score_reflects_selling_penalty() -> None:
    """$117.7M C-suite sells, 13 transactions, CEO/CFO $3.87M → MULTIPLE_SALES → score 45 (recalibrated)."""
    score, label = _score_insider_activity(
        0.0, NBIS_INSIDER_SELL, 13, NBIS_CEO_CFO_SELL
    )
    assert score == EXPECTED_INSIDER_SCORE_NBIS
    assert label == "MULTIPLE_SALES"


def test_nbis_fcf_scores_50_for_large_improvement() -> None:
    """NBIS FCF improved 82% in abs magnitude → NEGATIVE_LARGE_IMPROVEMENT → 50."""
    score, trend = _score_fcf(NBIS_FCF_CURRENT, NBIS_FCF_PRIOR)
    assert score == EXPECTED_FCF_SCORE_NBIS
    assert trend == "NEGATIVE_LARGE_IMPROVEMENT"


def test_nbis_gross_margin_scores_100() -> None:
    """NBIS 74% gross margin → 100."""
    assert _score_gross_margin(NBIS_GROSS_MARGIN) == EXPECTED_GM_SCORE_NBIS


# ===========================================================================
# Fix 4 — Gross margin uses most recent quarter only (not TTM)
# ===========================================================================

from atlas.services.fundamental_service import FundamentalService  # noqa: E402


class TestGrossMarginRecentQuarterOnly:
    """_extract_income_ttm must use only reports[0] for gross margin, not TTM sum.

    Rationale: for hyper-growth companies, legacy quarters have vastly different
    revenue bases, causing TTM gross margin to understate current profitability.
    """

    def test_gross_margin_uses_most_recent_quarter(self) -> None:
        """Single recent quarter with 74% GM → gross_margin = 0.74."""
        data = {
            "quarterlyReports": [
                {"totalRevenue": "399000000", "grossProfit": "295260000", "ebit": "50000000"},
                {"totalRevenue": "50000000",  "grossProfit": "10000000",  "ebit": "5000000"},
                {"totalRevenue": "30000000",  "grossProfit": "5000000",   "ebit": "2000000"},
                {"totalRevenue": "20000000",  "grossProfit": "2000000",   "ebit": "1000000"},
            ]
        }
        result = FundamentalService._extract_income_ttm(data)
        # TTM would give (295.26+10+5+2)/(399+50+30+20) = 312.26/499 = 62.6%
        # Most-recent-quarter gives 295.26/399 = 74.0%
        assert result["gross_margin"] is not None
        assert abs(result["gross_margin"] - 0.74) < 0.01, (
            f"expected ~0.74, got {result['gross_margin']:.4f} — TTM is being used instead of Q1"
        )

    def test_gross_margin_falls_back_to_none_when_revenue_missing(self) -> None:
        """Missing totalRevenue in most recent report → gross_margin is None."""
        data = {
            "quarterlyReports": [
                {"grossProfit": "100000000", "ebit": "50000000"},
            ]
        }
        result = FundamentalService._extract_income_ttm(data)
        assert result["gross_margin"] is None

    def test_gross_margin_anomaly_guard_uses_prior_median(self) -> None:
        """If Q1 GM is >20pp below prior 3-quarter median, use prior median instead.

        Mirrors the SF2 anomaly correction in the earnings service.
        NBIS pattern: AV reports Q1=20%, but prior quarters show ~70% median.
        """
        data = {
            "quarterlyReports": [
                # Q1 (most recent): 20% GM — anomalously low (AV data error)
                {"totalRevenue": "100000000", "grossProfit": "20000000", "ebit": "10000000"},
                # Q0-2 (prior 3): ~70% GM each
                {"totalRevenue": "100000000", "grossProfit": "70000000", "ebit": "30000000"},
                {"totalRevenue": "100000000", "grossProfit": "72000000", "ebit": "32000000"},
                {"totalRevenue": "100000000", "grossProfit": "68000000", "ebit": "28000000"},
            ]
        }
        result = FundamentalService._extract_income_ttm(data)
        assert result["gross_margin"] is not None
        # Median of [0.70, 0.72, 0.68] = 0.70; Q1 20% is >20pp below → use 70%
        assert abs(result["gross_margin"] - 0.70) < 0.01, (
            f"expected ~0.70 (prior median), got {result['gross_margin']:.4f}"
        )

    def test_gross_margin_no_anomaly_when_within_20pp(self) -> None:
        """If Q1 GM is within 20pp of prior median, use Q1 value as-is."""
        data = {
            "quarterlyReports": [
                # Q1: 60% GM — within 20pp of ~70% median
                {"totalRevenue": "100000000", "grossProfit": "60000000", "ebit": "10000000"},
                {"totalRevenue": "100000000", "grossProfit": "70000000", "ebit": "30000000"},
                {"totalRevenue": "100000000", "grossProfit": "72000000", "ebit": "32000000"},
                {"totalRevenue": "100000000", "grossProfit": "68000000", "ebit": "28000000"},
            ]
        }
        result = FundamentalService._extract_income_ttm(data)
        assert result["gross_margin"] is not None
        assert abs(result["gross_margin"] - 0.60) < 0.01

    def test_gross_margin_falls_back_to_none_when_gross_profit_missing(self) -> None:
        """Missing grossProfit → gross_margin is None."""
        data = {
            "quarterlyReports": [
                {"totalRevenue": "399000000", "ebit": "50000000"},
            ]
        }
        result = FundamentalService._extract_income_ttm(data)
        assert result["gross_margin"] is None

    def test_ttm_revenue_and_operating_income_still_use_4_quarters(self) -> None:
        """TTM revenue and operating income are still the 4-quarter sum (unchanged)."""
        data = {
            "quarterlyReports": [
                {"totalRevenue": "100000000", "grossProfit": "70000000", "ebit": "20000000"},
                {"totalRevenue": "80000000",  "grossProfit": "50000000", "ebit": "15000000"},
                {"totalRevenue": "60000000",  "grossProfit": "35000000", "ebit": "10000000"},
                {"totalRevenue": "40000000",  "grossProfit": "20000000", "ebit": "5000000"},
            ]
        }
        result = FundamentalService._extract_income_ttm(data)
        assert result["ttm_revenue"] == pytest.approx(280_000_000.0)
        assert result["ttm_operating_income"] == pytest.approx(50_000_000.0)


# ===========================================================================
# Fix 5 — MULTIPLE_SALES recalibrated from 30 → 45
# ===========================================================================

# New expected score for MULTIPLE_SALES (recalibrated from 30 to 45).
RECALIBRATED_MULTIPLE_SALES_SCORE = 45


class TestMultipleSalesRecalibration:
    def test_multiple_sales_scores_45_not_30(self) -> None:
        """MULTIPLE_SALES recalibrated to 45 — signal is real but less severe."""
        score, label = _score_insider_activity(0.0, 5_000_000.0, 3, 0.0)
        assert score == RECALIBRATED_MULTIPLE_SALES_SCORE
        assert label == "MULTIPLE_SALES"

    def test_ceo_mega_sale_still_scores_20(self) -> None:
        """CEO/CFO mega-sale (>$10M) is unchanged at 20."""
        score, label = _score_insider_activity(0.0, 60_000_000.0, 1, 60_000_000.0)
        assert score == 20
        assert label == "CEO_MEGA_SALE"

    def test_small_sale_still_scores_55(self) -> None:
        """Single officer sale >= $1M is unchanged at 55."""
        score, label = _score_insider_activity(0.0, 1_500_000.0, 1, 0.0)
        assert score == 55
        assert label == "SMALL_SALE"

    def test_no_activity_still_scores_70(self) -> None:
        score, label = _score_insider_activity(0.0, 0.0, 0, 0.0)
        assert score == 70
        assert label == "NO_ACTIVITY"

    def test_net_buying_still_scores_100(self) -> None:
        score, label = _score_insider_activity(500_000.0, 0.0, 0, 0.0)
        assert score == 100
        assert label == "NET_BUYING"

    def test_nbis_pattern_multiple_sales_scores_45(self) -> None:
        """NBIS: 13 transactions, $125.9M total sell, CEO/CFO $3.87M → MULTIPLE_SALES → 45."""
        score, label = _score_insider_activity(0.0, NBIS_INSIDER_SELL, 13, NBIS_CEO_CFO_SELL)
        assert score == RECALIBRATED_MULTIPLE_SALES_SCORE
        assert label == "MULTIPLE_SALES"


# ===========================================================================
# Fix 6 — Routine diversification: CEO_MEGA_SALE moderated when sell < 3% FCF
# ===========================================================================

# MU pattern constants (from live API).
MU_CEO_CFO_SELL = 59_904_671.0    # $59.9M CEO sell
MU_FCF_CURRENT = 6_514_000_000.0  # $6.5B FCF (POSITIVE_GROWING)
# ratio = 0.0092 < 0.03 → should trigger ROUTINE_DIVERSIFICATION


class TestFcfRoutineDiversificationModifier:
    """_apply_fcf_routine_modifier() upgrades CEO_MEGA_SALE → ROUTINE_DIVERSIFICATION
    when the CEO/CFO sell is trivially small relative to positive FCF (< 3%).
    """

    def _make_insider_indicator(
        self,
        *,
        score: int,
        label: str,
        ceo_cfo_sell: float | None = None,
    ) -> object:
        from atlas.schemas.fundamental import InsiderActivityIndicator
        return InsiderActivityIndicator(
            net_buy_value=None,
            net_sell_value=ceo_cfo_sell,
            transaction_count=1,
            c_suite_sell_value=ceo_cfo_sell,
            ceo_cfo_sell_value=ceo_cfo_sell,
            activity_label=label,
            score=score,
            weight=0.3,
        )

    def test_mu_pattern_upgraded_to_routine_diversification(self) -> None:
        """MU: CEO sells $59.9M, FCF $6.5B → ratio 0.92% < 3% → ROUTINE_DIVERSIFICATION → 70."""
        ind = self._make_insider_indicator(score=20, label="CEO_MEGA_SALE", ceo_cfo_sell=MU_CEO_CFO_SELL)
        result = _apply_fcf_routine_modifier(ind, MU_FCF_CURRENT)
        assert result.score == 70
        assert result.activity_label == "ROUTINE_DIVERSIFICATION"

    def test_ceo_mega_sale_preserved_when_ratio_above_threshold(self) -> None:
        """CEO sells $60M but FCF is only $200M → 30% of FCF → NOT routine → stays CEO_MEGA_SALE (20)."""
        ind = self._make_insider_indicator(score=20, label="CEO_MEGA_SALE", ceo_cfo_sell=60_000_000.0)
        result = _apply_fcf_routine_modifier(ind, 200_000_000.0)
        assert result.score == 20
        assert result.activity_label == "CEO_MEGA_SALE"

    def test_no_modification_when_fcf_negative(self) -> None:
        """CEO_MEGA_SALE when FCF is negative → selling while burning cash, keep penalty."""
        ind = self._make_insider_indicator(score=20, label="CEO_MEGA_SALE", ceo_cfo_sell=MU_CEO_CFO_SELL)
        result = _apply_fcf_routine_modifier(ind, -500_000_000.0)
        assert result.score == 20
        assert result.activity_label == "CEO_MEGA_SALE"

    def test_no_modification_when_fcf_none(self) -> None:
        """No FCF data → cannot assess routine → keep penalty."""
        ind = self._make_insider_indicator(score=20, label="CEO_MEGA_SALE", ceo_cfo_sell=MU_CEO_CFO_SELL)
        result = _apply_fcf_routine_modifier(ind, None)
        assert result.score == 20
        assert result.activity_label == "CEO_MEGA_SALE"

    def test_multiple_sales_upgraded_when_small_vs_ttm_fcf(self) -> None:
        """AMAT pattern: 4 officer sales net $27.1M, TTM FCF $5.34B → 0.51% < 3%
        → routine multi-officer diversification → ROUTINE_DIVERSIFICATION → 70."""
        ind = self._make_insider_indicator(
            score=45, label="MULTIPLE_SALES", ceo_cfo_sell=27_100_000.0
        )
        result = _apply_fcf_routine_modifier(ind, 5_340_000_000.0)
        assert result.score == 70
        assert result.activity_label == "ROUTINE_DIVERSIFICATION"

    def test_multiple_sales_preserved_when_large_vs_ttm_fcf(self) -> None:
        """MULTIPLE_SALES net $27.1M vs only $200M TTM FCF → 13.5% > 3% → stays 45."""
        ind = self._make_insider_indicator(
            score=45, label="MULTIPLE_SALES", ceo_cfo_sell=27_100_000.0
        )
        result = _apply_fcf_routine_modifier(ind, 200_000_000.0)
        assert result.score == 45
        assert result.activity_label == "MULTIPLE_SALES"

    def test_multiple_sales_preserved_when_fcf_negative(self) -> None:
        """Selling while burning cash (negative FCF) stays penalised even for MULTIPLE_SALES."""
        ind = self._make_insider_indicator(
            score=45, label="MULTIPLE_SALES", ceo_cfo_sell=5_000_000.0
        )
        result = _apply_fcf_routine_modifier(ind, -500_000_000.0)
        assert result.score == 45
        assert result.activity_label == "MULTIPLE_SALES"

    def test_no_modification_when_ceo_cfo_sell_none(self) -> None:
        """No ceo_cfo_sell_value recorded → can't compute ratio → keep penalty."""
        from atlas.schemas.fundamental import InsiderActivityIndicator
        ind = InsiderActivityIndicator(
            net_buy_value=None,
            net_sell_value=50_000_000.0,
            transaction_count=1,
            c_suite_sell_value=50_000_000.0,
            ceo_cfo_sell_value=None,  # explicitly missing
            activity_label="CEO_MEGA_SALE",
            score=20,
            weight=0.3,
        )
        result = _apply_fcf_routine_modifier(ind, MU_FCF_CURRENT)
        assert result.score == 20

    def test_mu_f5_composite_reaches_91(self) -> None:
        """After ROUTINE_DIVERSIFICATION upgrade, insider contrib = 21.0 → f5 composite = 91."""
        ind = self._make_insider_indicator(score=20, label="CEO_MEGA_SALE", ceo_cfo_sell=MU_CEO_CFO_SELL)
        upgraded = _apply_fcf_routine_modifier(ind, MU_FCF_CURRENT)
        assert upgraded.score == 70
        # All other sub-scores are 100 for MU (from live API).
        f5_raw = (
            upgraded.score * 0.30   # insider  = 21.0
            + 100 * 0.25            # altman_z = 25.0
            + 100 * 0.15            # fcf      = 15.0
            + 100 * 0.10            # gross_margin = 10.0
            + 100 * 0.10            # debt_equity  = 10.0
            + 100 * 0.10            # institutional = 10.0
        )
        # max with ROUTINE_DIVERSIFICATION insider = 91 → 23/25 in framework
        # (client scored 24/25 by rounding generously for near-perfect fundamentals)
        assert round(f5_raw) == 91


# ===========================================================================
# Fix 6 — Free Cash Flow uses TTM-over-TTM, not single-quarter QoQ
# ===========================================================================


class TestCashFlowTtm:
    """_extract_cash_flows must sum 4 quarters (TTM) and compare to the prior
    TTM, so a single capex-heavy quarter cannot masquerade as a trend.

    AMAT pattern: the most recent quarter FCF ($208M, capex spike) vs the prior
    quarter ($1040M) reads as -80% QoQ, while the TTM ($5.34B vs $5.86B) is only
    -9% — essentially flat.
    """

    @staticmethod
    def _q(op: float, capex: float) -> dict[str, str]:
        return {"operatingCashflow": str(op), "capitalExpenditures": str(capex)}

    def test_ttm_sums_four_quarters(self) -> None:
        # AMAT-like: 8 quarters of (op, capex). FCF = op - |capex|.
        data = {
            "quarterlyReports": [
                self._q(843_000_000, 635_000_000),    # 208M
                self._q(1_686_000_000, 646_000_000),  # 1040M
                self._q(2_828_000_000, 785_000_000),  # 2043M
                self._q(2_634_000_000, 584_000_000),  # 2050M
                self._q(1_571_000_000, 510_000_000),  # 1061M
                self._q(925_000_000, 381_000_000),    # 544M
                self._q(2_575_000_000, 407_000_000),  # 2168M
                self._q(2_385_000_000, 297_000_000),  # 2088M
            ]
        }
        result = FundamentalService._extract_cash_flows(data)
        # Current TTM = 208+1040+2043+2050 = 5341M; prior TTM = 1061+544+2168+2088 = 5861M
        assert result["fcf_current"] == pytest.approx(5_341_000_000.0)
        assert result["fcf_prior"] == pytest.approx(5_861_000_000.0)

    def test_amat_ttm_scores_positive_flat_not_declining(self) -> None:
        """The TTM trend (-9%) is POSITIVE_FLAT (80), not the QoQ POSITIVE_DECLINING (60)."""
        cur, prior = 5_341_000_000.0, 5_861_000_000.0
        score, trend = _score_fcf(cur, prior)
        assert score == 80
        assert trend == "POSITIVE_FLAT"

    def test_prior_ttm_none_when_fewer_than_8_quarters(self) -> None:
        data = {"quarterlyReports": [self._q(1_000_000, 100_000)] * 4}
        result = FundamentalService._extract_cash_flows(data)
        assert result["fcf_current"] == pytest.approx(3_600_000.0)  # (1.0M-0.1M)*4
        assert result["fcf_prior"] is None

    def test_current_ttm_none_when_fewer_than_4_quarters(self) -> None:
        data = {"quarterlyReports": [self._q(1_000_000, 100_000)] * 3}
        result = FundamentalService._extract_cash_flows(data)
        assert result["fcf_current"] is None
        assert result["fcf_prior"] is None

    def test_ttm_none_when_a_quarter_is_missing_operating_cashflow(self) -> None:
        data = {
            "quarterlyReports": [
                self._q(1_000_000, 100_000),
                {"capitalExpenditures": "100000"},  # missing operatingCashflow
                self._q(1_000_000, 100_000),
                self._q(1_000_000, 100_000),
            ]
        }
        result = FundamentalService._extract_cash_flows(data)
        assert result["fcf_current"] is None
