"""Unit tests for the INTL-3F data service pure scoring helpers."""

from __future__ import annotations

from atlas.services.intl_data_service import (
    score_intl_confirmation,
    score_intl_fundamentals,
    score_intl_market,
)


class TestScoreIntlMarket:
    def test_gap_on_insufficient_history(self) -> None:
        bars = [{"c": 10.0, "v": 1000} for _ in range(10)]
        assert score_intl_market(bars) == (None, "DATA_GAP")

    def test_uptrend_liquid_scores_high(self) -> None:
        bars = [{"c": 10.0 + i * 0.2, "v": 500_000} for i in range(120)]
        score, source = score_intl_market(bars)
        assert source == "polygon"
        assert score is not None and score >= 70

    def test_downtrend_thin_scores_low_but_not_gap(self) -> None:
        bars = [{"c": 30.0 - i * 0.2, "v": 1_000} for i in range(120)]
        score, source = score_intl_market(bars)
        assert source == "polygon"
        assert score is not None and score < 40


class TestScoreIntlFundamentals:
    def test_gap_on_empty(self) -> None:
        assert score_intl_fundamentals([]) == (None, "DATA_GAP")

    def test_growing_profitable_high_margin_scores_high(self) -> None:
        reports = [
            {"revenue": 1500, "netIncome": 300, "grossProfit": 800},
            {"revenue": 1000, "netIncome": 150, "grossProfit": 500},
        ]
        score, source = score_intl_fundamentals(reports)
        assert source == "fmp-financials"
        assert score is not None and score >= 80

    def test_loss_making_shrinking_scores_low(self) -> None:
        reports = [
            {"revenue": 800, "netIncome": -100, "grossProfit": 80},
            {"revenue": 1000, "netIncome": -50, "grossProfit": 120},
        ]
        score, _ = score_intl_fundamentals(reports)
        assert score is not None and score < 35


class TestScoreIntlConfirmation:
    def test_gap_on_none(self) -> None:
        assert score_intl_confirmation(None) == (None, "DATA_GAP")

    def test_numeric_overall_score(self) -> None:
        assert score_intl_confirmation([{"overallScore": 5}]) == (100, "fmp-ratings")

    def test_letter_rating(self) -> None:
        assert score_intl_confirmation({"rating": "B+"}) == (72, "fmp-ratings")

    def test_unknown_rating_is_gap(self) -> None:
        assert score_intl_confirmation({"rating": "???"}) == (None, "DATA_GAP")
