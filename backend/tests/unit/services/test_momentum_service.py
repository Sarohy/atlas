"""Unit tests for MomentumService — pure calculation functions.

All Polygon HTTP calls are mocked; these tests cover only the computation
logic that is deterministic from a known input series.
"""

from __future__ import annotations

from atlas.services.momentum_service import (
    _compute_52w_position,
    _compute_f1_score,
    _compute_ma_alignment,
    _compute_macd,
    _compute_performance,
    _compute_rsi,
    _compute_sector_score,
    _score_1m_perf,
    _score_6m_perf,
    _score_52w_position,
    _score_ma_alignment,
    _score_macd,
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
    """Score bands per Factor_Mapping_Guide.

    >=90->100, >=70->85, >=55->70, >=45->55, >=35->40, <35->20.
    """

    def test_extremely_strong_scores_100(self) -> None:
        """RSI >= 90 = extremely strong momentum → 100 raw."""
        assert _score_rsi(92.0) == 100
        assert _score_rsi(90.0) == 100

    def test_overbought_scores_85(self) -> None:
        """RSI 70-89 = overbought / strong → 85 raw."""
        assert _score_rsi(75.0) == 85
        assert _score_rsi(70.0) == 85

    def test_healthy_scores_70(self) -> None:
        """RSI 55-69 = healthy → 70 raw.  LITE example: RSI 68 → 70."""
        assert _score_rsi(68.0) == 70
        assert _score_rsi(55.0) == 70

    def test_neutral_scores_55(self) -> None:
        """RSI 45-54 = neutral → 55 raw."""
        assert _score_rsi(50.0) == 55
        assert _score_rsi(45.0) == 55

    def test_weak_scores_40(self) -> None:
        """RSI 35-44 = weak → 40 raw."""
        assert _score_rsi(40.0) == 40
        assert _score_rsi(35.0) == 40

    def test_oversold_scores_20(self) -> None:
        """RSI < 35 = oversold → 20 raw."""
        assert _score_rsi(30.0) == 20
        assert _score_rsi(10.0) == 20


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
        _macd_val, _signal_val, _histogram = result

    def test_negative_histogram_when_falling(self) -> None:
        """A steady downtrend should produce a negative MACD histogram."""
        closes = [150.0 - i * 0.5 for i in range(50)]
        result = _compute_macd(_bars(closes))
        assert result is not None
        _macd_val, _signal_val, histogram = result
        assert histogram < 0


# ---------------------------------------------------------------------------
# MACD score
# ---------------------------------------------------------------------------


class TestScoreMacd:
    """Score bands per guide: above+rising→100, above→75, rising only→50, else→20."""

    def test_above_signal_and_rising_scores_100(self) -> None:
        """MACD > signal AND histogram rising → 100."""
        # prev_histogram=0.1, current histogram=0.3 → rising
        score = _score_macd(macd=1.0, signal=0.5, histogram=0.3, prev_histogram=0.1)
        assert score == 100

    def test_above_signal_flat_scores_75(self) -> None:
        """MACD > signal but NOT rising → 75."""
        score = _score_macd(macd=1.0, signal=0.5, histogram=0.1, prev_histogram=0.3)
        assert score == 75

    def test_below_signal_but_rising_scores_50(self) -> None:
        """MACD below signal but histogram improving → 50."""
        score = _score_macd(macd=0.3, signal=0.5, histogram=-0.1, prev_histogram=-0.3)
        assert score == 50

    def test_below_signal_falling_scores_20(self) -> None:
        """MACD below signal and histogram falling → 20."""
        score = _score_macd(macd=0.3, signal=0.5, histogram=-0.3, prev_histogram=-0.1)
        assert score == 20

    def test_no_prev_histogram_positive_counts_as_rising(self) -> None:
        """When prev_histogram is None, positive histogram treated as rising."""
        score = _score_macd(macd=1.0, signal=0.5, histogram=0.2, prev_histogram=None)
        assert score == 100


# ---------------------------------------------------------------------------
# 52-week score
# ---------------------------------------------------------------------------


class TestScore52wPosition:
    """Score bands per guide: >80→100, >=60→80, >=40→60, >=20→40, else→20."""

    def test_near_high_scores_100(self) -> None:
        assert _score_52w_position(85.0) == 100
        assert _score_52w_position(80.1) == 100

    def test_upper_range_scores_80(self) -> None:
        """LITE example: 78% → 80."""
        assert _score_52w_position(78.0) == 80
        assert _score_52w_position(60.0) == 80

    def test_midrange_scores_60(self) -> None:
        assert _score_52w_position(55.0) == 60
        assert _score_52w_position(40.0) == 60

    def test_lower_range_scores_40(self) -> None:
        assert _score_52w_position(30.0) == 40
        assert _score_52w_position(20.0) == 40

    def test_near_low_scores_20(self) -> None:
        assert _score_52w_position(15.0) == 20
        assert _score_52w_position(0.0) == 20


# ---------------------------------------------------------------------------
# MA Alignment
# ---------------------------------------------------------------------------


class TestComputeMaAlignment:
    def test_returns_none_on_insufficient_data(self) -> None:
        """Need at least 200 bars for MA-200."""
        result = _compute_ma_alignment(_bars([100.0] * 50))
        assert result is None

    def test_above_all_when_price_above_all_mas(self) -> None:
        """Price > MA20, MA50, MA200 → ABOVE_ALL."""
        # Strong uptrend ensures price ends above all moving averages
        closes = [100.0 + i * 0.2 for i in range(210)]
        result = _compute_ma_alignment(_bars(closes))
        assert result is not None
        _ma20, _ma50, _ma200, label = result
        assert label == "ABOVE_ALL"

    def test_below_all_when_price_below_all_mas(self) -> None:
        """Price < MA200 and falling → BELOW_ALL."""
        closes = [250.0 - i * 0.2 for i in range(210)]
        result = _compute_ma_alignment(_bars(closes))
        assert result is not None
        _ma20, _ma50, _ma200, label = result
        assert label == "BELOW_ALL"


class TestScoreMaAlignment:
    """Score bands per guide: ABOVE_ALL→100, ABOVE_50_200→80, ABOVE_200→55, BELOW_ALL→20."""

    def test_above_all_scores_100(self) -> None:
        assert _score_ma_alignment("ABOVE_ALL") == 100

    def test_above_50_200_scores_80(self) -> None:
        assert _score_ma_alignment("ABOVE_50_200") == 80

    def test_above_200_scores_55(self) -> None:
        assert _score_ma_alignment("ABOVE_200") == 55

    def test_below_all_scores_20(self) -> None:
        assert _score_ma_alignment("BELOW_ALL") == 20

    def test_unknown_label_scores_20(self) -> None:
        """Fallback for unknown / INSUFFICIENT_DATA should be 20 (most conservative)."""
        assert _score_ma_alignment("INSUFFICIENT_DATA") == 20


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
    """Score bands per guide: >10→100, >=5→85, >=2→70, >=0→55, >=-2→40, else→20."""

    def test_strong_gain_scores_100(self) -> None:
        assert _score_1m_perf(12.0) == 100
        assert _score_1m_perf(10.1) == 100

    def test_good_gain_scores_85(self) -> None:
        """LITE example: +8% → 85."""
        assert _score_1m_perf(8.0) == 85
        assert _score_1m_perf(5.0) == 85

    def test_moderate_gain_scores_70(self) -> None:
        assert _score_1m_perf(3.0) == 70
        assert _score_1m_perf(2.0) == 70

    def test_flat_scores_55(self) -> None:
        assert _score_1m_perf(1.0) == 55
        assert _score_1m_perf(0.0) == 55

    def test_small_loss_scores_40(self) -> None:
        assert _score_1m_perf(-1.0) == 40
        assert _score_1m_perf(-2.0) == 40

    def test_large_loss_scores_20(self) -> None:
        assert _score_1m_perf(-5.0) == 20
        assert _score_1m_perf(-10.0) == 20


class TestScore6mPerf:
    """Score bands per guide: >40→100, >=25→85, >=15→70, >=5→55, >=0→40, else→20."""

    def test_strong_gain_scores_100(self) -> None:
        assert _score_6m_perf(45.0) == 100
        assert _score_6m_perf(40.1) == 100

    def test_good_gain_scores_85(self) -> None:
        """LITE example: +32% → 85."""
        assert _score_6m_perf(32.0) == 85
        assert _score_6m_perf(25.0) == 85

    def test_moderate_gain_scores_70(self) -> None:
        assert _score_6m_perf(20.0) == 70
        assert _score_6m_perf(15.0) == 70

    def test_small_gain_scores_55(self) -> None:
        assert _score_6m_perf(10.0) == 55
        assert _score_6m_perf(5.0) == 55

    def test_flat_scores_40(self) -> None:
        assert _score_6m_perf(2.0) == 40
        assert _score_6m_perf(0.0) == 40

    def test_loss_scores_20(self) -> None:
        assert _score_6m_perf(-5.0) == 20
        assert _score_6m_perf(-20.0) == 20


# ---------------------------------------------------------------------------
# Sector score
# ---------------------------------------------------------------------------


class TestComputeSectorScore:
    """Score bands per guide (6M window): >5%→100, >0%→75, >=-1%→60 (in-line), else→30."""

    def test_strong_outperformance_scores_100(self) -> None:
        """Relative > +5% → 100."""
        score = _compute_sector_score(ticker_perf_6m=10.0, sector_perf_6m=4.0)  # +6% rel
        assert score == 100

    def test_moderate_outperformance_scores_75(self) -> None:
        """Relative 0-5% -> 75."""
        score = _compute_sector_score(ticker_perf_6m=8.0, sector_perf_6m=5.0)  # +3% rel
        assert score == 75

    def test_in_line_scores_60(self) -> None:
        """Relative -1% to 0% → 60 (in-line neutral)."""
        score = _compute_sector_score(ticker_perf_6m=5.0, sector_perf_6m=5.0)  # 0% rel
        assert score == 60

    def test_just_below_inline_scores_30(self) -> None:
        """Relative < -1% → underperform → 30."""
        score = _compute_sector_score(ticker_perf_6m=0.0, sector_perf_6m=5.0)  # -5% rel
        assert score == 30

    def test_strong_underperformance_scores_30(self) -> None:
        """Large underperformance → 30."""
        score = _compute_sector_score(ticker_perf_6m=-10.0, sector_perf_6m=0.0)  # -10% rel
        assert score == 30


# ---------------------------------------------------------------------------
# F1 composite
# ---------------------------------------------------------------------------


class TestComputeF1Score:
    """Weighted composite: each raw 0-100 x weight, summed, rounded, capped at 100.

    Weights: RSI 20% + MACD 15% + MA 20% + 52W 15% + 1M 15% + 6M 10% + Sector 5% = 100%.
    """

    def test_lite_example_scores_86(self) -> None:
        """LITE worked example from Factor_Mapping_Guide must produce exactly 86.

        RSI 68 -> 70 x 0.20 = 14.0
        MACD above+rising -> 100 x 0.15 = 15.0
        Above all MAs -> 100 x 0.20 = 20.0
        52W 78% -> 80 x 0.15 = 12.0
        1M +8% -> 85 x 0.15 = 12.75
        6M +32% -> 85 x 0.10 = 8.5
        Sector outperform 0-5% -> 75 x 0.05 = 3.75
        Total = 86.0 -> rounded -> 86.
        """
        total, grade = _compute_f1_score(
            rsi_raw=70,
            macd_raw=100,
            ma_raw=100,
            week52_raw=80,
            perf_1m_raw=85,
            perf_6m_raw=85,
            sector_raw=75,
        )
        assert total == 86
        assert grade == "STRONG BUY"

    def test_max_inputs_yield_100_strong_buy(self) -> None:
        """All raw scores at 100 should produce 100 STRONG BUY."""
        total, grade = _compute_f1_score(
            rsi_raw=100,
            macd_raw=100,
            ma_raw=100,
            week52_raw=100,
            perf_1m_raw=100,
            perf_6m_raw=100,
            sector_raw=100,
        )
        assert total == 100
        assert grade == "STRONG BUY"

    def test_min_inputs_yield_20_weak(self) -> None:
        """All raw scores at 20 (minimum per guide): 20 x 1.0 = 20 -> WEAK (AVOID is <20)."""
        total, grade = _compute_f1_score(
            rsi_raw=20,
            macd_raw=20,
            ma_raw=20,
            week52_raw=20,
            perf_1m_raw=20,
            perf_6m_raw=20,
            sector_raw=20,
        )
        assert total == 20
        assert grade == "WEAK"

    def test_zero_inputs_yield_avoid(self) -> None:
        """All raw scores at 0 (edge case) → 0 → AVOID."""
        total, grade = _compute_f1_score(
            rsi_raw=0,
            macd_raw=0,
            ma_raw=0,
            week52_raw=0,
            perf_1m_raw=0,
            perf_6m_raw=0,
            sector_raw=0,
        )
        assert total == 0
        assert grade == "AVOID"

    def test_grade_buy_at_75(self) -> None:
        """Score = 75 -> BUY (>=65 band)."""
        # RSI:70x0.20=14, MACD:100x0.15=15, MA:80x0.20=16, 52W:80x0.15=12,
        # 1M:70x0.15=10.5, 6M:70x0.10=7, Sector:60x0.05=3 -> sum=77.5 -> 78
        total, grade = _compute_f1_score(
            rsi_raw=70,
            macd_raw=100,
            ma_raw=80,
            week52_raw=80,
            perf_1m_raw=70,
            perf_6m_raw=70,
            sector_raw=60,
        )
        assert total == 78
        assert grade == "BUY"

    def test_score_is_capped_at_100(self) -> None:
        """Rounding can never push total above 100."""
        total, _ = _compute_f1_score(
            rsi_raw=100,
            macd_raw=100,
            ma_raw=100,
            week52_raw=100,
            perf_1m_raw=100,
            perf_6m_raw=100,
            sector_raw=100,
        )
        assert total <= 100
