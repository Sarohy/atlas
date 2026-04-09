"""Unit tests for MomentumService — pure calculation functions.

All Polygon HTTP calls are mocked; these tests cover only the computation
logic that is deterministic from a known input series.
"""

import math
from decimal import Decimal

import pytest

from atlas.services.momentum_service import (
    _compute_f1_score,
    _compute_ma_alignment,
    _compute_macd,
    _compute_performance,
    _compute_rsi,
    _compute_sector_score,
    _compute_52w_position,
    _score_1m_perf,
    _score_6m_perf,
    _score_rsi,
)

# ---------------------------------------------------------------------------
# Constants mirrored from the service
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000_000  # 2023-11-15 epoch ms
_MS_PER_DAY = 86_400_000


def _bars(closes: list[float], base_ts: int = _BASE_TS) -> list[dict]:  # type: ignore[type-arg]
    """Build minimal Polygon agg bar dicts with sequential daily timestamps."""
    return [{"t": base_ts + i * _MS_PER_DAY, "c": c, "o": c} for i, c in enumerate(closes)]


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


class TestComputeRsi:
    def test_returns_none_on_insufficient_data(self) -> None:
        """Need at least period + 1 bars (15 bars for RSI-14)."""
        result = _compute_rsi(_bars([100.0] * 10), period=14)
        assert result is None

    def test_returns_50_for_flat_series(self) -> None:
        """A flat price series should yield RSI of exactly 50."""
        # Flat → average gain == average loss → RSI = 50
        closes = [100.0] * 30
        result = _compute_rsi(_bars(closes), period=14)
        # With a perfectly flat series RS is undefined (0/0); service returns 50 by convention
        assert result is not None
        assert abs(result - 50.0) < 1.0

    def test_returns_100_for_monotone_up(self) -> None:
        """Strictly rising series → no losses → RSI approaches 100."""
        closes = [100.0 + i for i in range(30)]
        result = _compute_rsi(_bars(closes), period=14)
        assert result is not None
        assert result > 95.0

    def test_returns_0_for_monotone_down(self) -> None:
        """Strictly falling series → no gains → RSI approaches 0."""
        closes = [130.0 - i for i in range(30)]
        result = _compute_rsi(_bars(closes), period=14)
        assert result is not None
        assert result < 5.0

    def test_value_in_valid_range(self) -> None:
        """RSI must always be in [0, 100]."""
        import random

        random.seed(42)
        closes = [100.0 + random.gauss(0, 2) for _ in range(50)]
        result = _compute_rsi(_bars(closes), period=14)
        assert result is not None
        assert 0.0 <= result <= 100.0


# ---------------------------------------------------------------------------
# RSI score
# ---------------------------------------------------------------------------


class TestScoreRsi:
    def test_peak_momentum_scores_20(self) -> None:
        """RSI 60-79 = strong momentum zone → full 20 points."""
        assert _score_rsi(65.0) == 20

    def test_moderate_momentum_scores_15(self) -> None:
        """RSI 50-59 = decent momentum → 15 points."""
        assert _score_rsi(55.0) == 15

    def test_overbought_scores_10(self) -> None:
        """RSI >= 80 is overbought — momentum present but caution → 10 points."""
        assert _score_rsi(82.0) == 10

    def test_below_50_scores_5(self) -> None:
        """RSI 40-49 = weak / below midline → 5 points."""
        assert _score_rsi(45.0) == 5

    def test_oversold_scores_0(self) -> None:
        """RSI < 30 → very weak momentum → 0 points."""
        assert _score_rsi(25.0) == 0

    def test_bearish_zone_scores_2(self) -> None:
        """RSI 30-39 = bearish momentum → 2 points."""
        assert _score_rsi(35.0) == 2


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


class TestComputeMacd:
    def test_returns_none_on_insufficient_data(self) -> None:
        """Need at least slow_period + signal_period bars (26 + 9 = 35)."""
        result = _compute_macd(_bars([100.0] * 30))
        assert result is None

    def test_positive_histogram_when_rising(self) -> None:
        """A steady uptrend should produce a positive MACD histogram."""
        closes = [50.0 + i * 0.5 for i in range(50)]
        result = _compute_macd(_bars(closes))
        assert result is not None
        macd_val, signal_val, histogram = result
        assert histogram > 0

    def test_negative_histogram_when_falling(self) -> None:
        """A steady downtrend should produce a negative MACD histogram."""
        closes = [150.0 - i * 0.5 for i in range(50)]
        result = _compute_macd(_bars(closes))
        assert result is not None
        _macd_val, _signal_val, histogram = result
        assert histogram < 0


# ---------------------------------------------------------------------------
# MA Alignment
# ---------------------------------------------------------------------------


class TestComputeMaAlignment:
    def test_returns_none_on_insufficient_data(self) -> None:
        """Need at least 200 bars for MA-200."""
        result = _compute_ma_alignment(_bars([100.0] * 50))
        assert result is None

    def test_full_bull_when_price_above_all_mas(self) -> None:
        """Price > MA20 > MA50 > MA200 should return FULL_BULL label."""
        # Build 210 bars with a strong uptrend so price ends well above all MAs
        closes = [100.0 + i * 0.2 for i in range(210)]
        result = _compute_ma_alignment(_bars(closes))
        assert result is not None
        _ma20, _ma50, _ma200, label = result
        assert label == "FULL_BULL"

    def test_full_bear_when_price_below_all_mas(self) -> None:
        """Price < MA200 and falling should return FULL_BEAR label."""
        # Steadily declining series — price always below all MAs
        closes = [250.0 - i * 0.2 for i in range(210)]
        result = _compute_ma_alignment(_bars(closes))
        assert result is not None
        _ma20, _ma50, _ma200, label = result
        assert label == "FULL_BEAR"


# ---------------------------------------------------------------------------
# 52-week position
# ---------------------------------------------------------------------------


class TestCompute52wPosition:
    def test_returns_none_on_insufficient_data(self) -> None:
        """Need at least 252 bars (one trading year)."""
        result = _compute_52w_position(_bars([100.0] * 100))
        assert result is None

    def test_at_high_returns_100_pct(self) -> None:
        """When current price == 52w high, position should be 100%."""
        closes = [100.0] * 251 + [110.0]  # last bar is the new high
        result = _compute_52w_position(_bars(closes))
        assert result is not None
        _high, _low, pct = result
        assert abs(pct - 100.0) < 0.01

    def test_at_low_returns_0_pct(self) -> None:
        """When current price == 52w low, position should be 0%."""
        closes = [100.0] * 251 + [90.0]  # last bar is the new low
        result = _compute_52w_position(_bars(closes))
        assert result is not None
        _high, _low, pct = result
        assert abs(pct - 0.0) < 0.01

    def test_midpoint_returns_50_pct(self) -> None:
        """Price at exact midpoint should yield ~50%."""
        closes = [90.0] + [100.0] * 250 + [95.0]  # low=90, high=100, current=95
        result = _compute_52w_position(_bars(closes))
        assert result is not None
        _high, _low, pct = result
        assert abs(pct - 50.0) < 0.01


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestComputePerformance:
    def test_returns_none_when_not_enough_bars_for_6m(self) -> None:
        """Needs 126 bars minimum for 6-month lookback."""
        result = _compute_performance(_bars([100.0] * 20))
        assert result is None

    def test_positive_performance_on_rising_series(self) -> None:
        """A rising series should give positive 1M and 6M returns."""
        closes = [50.0 + i * 0.5 for i in range(130)]
        result = _compute_performance(_bars(closes))
        assert result is not None
        perf_1m, perf_6m = result
        assert perf_1m > 0
        assert perf_6m > 0

    def test_negative_performance_on_falling_series(self) -> None:
        """A falling series should give negative 1M and 6M returns."""
        closes = [130.0 - i * 0.5 for i in range(130)]
        result = _compute_performance(_bars(closes))
        assert result is not None
        perf_1m, perf_6m = result
        assert perf_1m < 0
        assert perf_6m < 0


# ---------------------------------------------------------------------------
# 1M / 6M score functions
# ---------------------------------------------------------------------------


class TestScore1mPerf:
    def test_large_gain_scores_10(self) -> None:
        assert _score_1m_perf(12.0) == 10

    def test_moderate_gain_scores_8(self) -> None:
        assert _score_1m_perf(7.0) == 8

    def test_small_gain_scores_5(self) -> None:
        assert _score_1m_perf(2.0) == 5

    def test_small_loss_scores_2(self) -> None:
        assert _score_1m_perf(-3.0) == 2

    def test_large_loss_scores_0(self) -> None:
        assert _score_1m_perf(-10.0) == 0


class TestScore6mPerf:
    def test_large_gain_scores_10(self) -> None:
        assert _score_6m_perf(25.0) == 10

    def test_moderate_gain_scores_8(self) -> None:
        assert _score_6m_perf(15.0) == 8

    def test_small_gain_scores_5(self) -> None:
        assert _score_6m_perf(5.0) == 5

    def test_small_loss_scores_2(self) -> None:
        assert _score_6m_perf(-5.0) == 2

    def test_large_loss_scores_0(self) -> None:
        assert _score_6m_perf(-15.0) == 0


# ---------------------------------------------------------------------------
# Sector score
# ---------------------------------------------------------------------------


class TestComputeSectorScore:
    def test_strong_outperformance_scores_20(self) -> None:
        """Ticker +8% vs sector +2% → relative +6% → 20 points."""
        score = _compute_sector_score(ticker_perf_3m=8.0, sector_perf_3m=2.0)
        assert score == 20

    def test_moderate_outperformance_scores_15(self) -> None:
        """Ticker +5% vs sector +3% → relative +2% → 15 points."""
        score = _compute_sector_score(ticker_perf_3m=5.0, sector_perf_3m=3.0)
        assert score == 15

    def test_in_line_scores_10(self) -> None:
        """Ticker same as sector → 10 points."""
        score = _compute_sector_score(ticker_perf_3m=5.0, sector_perf_3m=5.0)
        assert score == 10

    def test_moderate_underperformance_scores_5(self) -> None:
        """Ticker -3% vs sector 0% → relative -3% → 5 points."""
        score = _compute_sector_score(ticker_perf_3m=-3.0, sector_perf_3m=0.0)
        assert score == 5

    def test_strong_underperformance_scores_0(self) -> None:
        """Ticker -10% vs sector 0% → relative -10% → 0 points."""
        score = _compute_sector_score(ticker_perf_3m=-10.0, sector_perf_3m=0.0)
        assert score == 0


# ---------------------------------------------------------------------------
# F1 composite
# ---------------------------------------------------------------------------


class TestComputeF1Score:
    def test_max_score_yields_strong_buy(self) -> None:
        """100/100 → STRONG BUY."""
        total, grade = _compute_f1_score(
            rsi_score=20,
            macd_score=20,
            ma_score=20,
            week52_score=20,
            perf_score=20,
            sector_score=0,  # only 5 sub-scores needed; sector added separately
        )
        # 20+20+20+20+20+0 = 100
        assert total == 100
        assert grade == "STRONG BUY"

    def test_zero_score_yields_avoid(self) -> None:
        """0/100 → AVOID."""
        total, grade = _compute_f1_score(
            rsi_score=0,
            macd_score=0,
            ma_score=0,
            week52_score=0,
            perf_score=0,
            sector_score=0,
        )
        assert total == 0
        assert grade == "AVOID"

    def test_grade_boundaries(self) -> None:
        """Verify each grade boundary threshold."""
        _, g80 = _compute_f1_score(20, 20, 20, 10, 10, 0)  # 80
        _, g60 = _compute_f1_score(20, 20, 10, 5, 5, 0)    # 60
        _, g40 = _compute_f1_score(20, 10, 5, 5, 0, 0)     # 40
        _, g20 = _compute_f1_score(10, 5, 0, 5, 0, 0)      # 20
        assert g80 == "STRONG BUY"
        assert g60 == "BUY"
        assert g40 == "NEUTRAL"
        assert g20 == "WEAK"

    def test_total_capped_at_100(self) -> None:
        """Even if input scores sum over 100, total must never exceed 100."""
        total, _ = _compute_f1_score(20, 20, 20, 20, 20, 20)
        assert total == 100
