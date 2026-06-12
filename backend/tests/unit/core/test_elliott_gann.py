"""Unit tests for the deterministic Elliott Wave + Gann engines (and ZigZag)."""

from __future__ import annotations

from itertools import pairwise

from atlas.core import gann
from atlas.core.elliott import label_impulse
from atlas.core.gann import analyze_gann, average_true_range, square_of_9_levels
from atlas.core.swings import zigzag_pivots


def _path(waypoints: list[float], steps: int = 6) -> list[float]:
    """Linear path through waypoints (one value per bar)."""
    prices: list[float] = []
    for a, b in pairwise(waypoints):
        prices.extend(a + (b - a) * s / steps for s in range(steps))
    prices.append(waypoints[-1])
    return prices


# ---------------------------------------------------------------------------
# ZigZag pivots
# ---------------------------------------------------------------------------


class TestZigZag:
    def test_alternating_pivots_on_clean_swings(self) -> None:
        p = _path([100, 120, 110, 150])
        pivots = zigzag_pivots(p, p, threshold_pct=5)
        kinds = [pv.kind for pv in pivots]
        # strictly alternating
        assert all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))
        assert kinds[0] == "L" and kinds[-1] == "H"

    def test_deterministic(self) -> None:
        p = _path([100, 120, 110, 150, 135, 160])
        assert zigzag_pivots(p, p, threshold_pct=5) == zigzag_pivots(p, p, threshold_pct=5)

    def test_too_short_returns_empty(self) -> None:
        assert zigzag_pivots([100.0], [100.0]) == []


# ---------------------------------------------------------------------------
# Elliott Wave
# ---------------------------------------------------------------------------


class TestElliott:
    def test_valid_up_impulse_signals_top_sell(self) -> None:
        # W1 +20, W2 -10 (50%), W3 +40 (ext), W4 -15 (no overlap), W5 +25.
        p = _path([100, 120, 110, 150, 135, 160])
        r = label_impulse(p, p, threshold_pct=5)
        assert r.direction == "UP"
        assert r.current_wave == "5"
        assert r.rules_valid is True
        assert r.impulse_complete is True
        assert r.signal == "IMPULSE_TOP_SELL"
        assert r.confidence > 0

    def test_wave4_overlap_invalidates(self) -> None:
        # P4 (115) below P1 (120) -> wave 4 overlaps wave 1 -> rule R3 fails.
        p = _path([100, 120, 110, 150, 115, 160])
        r = label_impulse(p, p, threshold_pct=5)
        assert r.rules_valid is False
        assert r.impulse_complete is False
        assert r.signal is None

    def test_valid_down_impulse_signals_bottom_buy(self) -> None:
        p = _path([160, 140, 150, 110, 125, 100])
        r = label_impulse(p, p, threshold_pct=5)
        assert r.direction == "DOWN"
        assert r.signal == "IMPULSE_BOTTOM_BUY"

    def test_insufficient_data_returns_none(self) -> None:
        r = label_impulse([100.0, 101.0], [100.0, 101.0])
        assert r.current_wave is None and r.signal is None


# ---------------------------------------------------------------------------
# Gann
# ---------------------------------------------------------------------------


class TestGann:
    def test_square_of_9_straddles_price(self) -> None:
        levels = square_of_9_levels(100.0)
        assert levels == sorted(levels)
        res = min(lv for lv in levels if lv > 100)
        sup = max(lv for lv in levels if lv < 100)
        assert sup < 100 < res

    def test_average_true_range(self) -> None:
        highs = [11.0, 12.0, 13.0]
        lows = [10.0, 11.0, 12.0]
        closes = [10.5, 11.5, 12.5]
        atr = average_true_range(highs, lows, closes, period=14)
        assert atr is not None and atr > 0

    def test_cycle_due_logic(self) -> None:
        cycles = (90, 144, 180, 360)
        assert gann._cycle_due(90, cycles, 3) == 90
        assert gann._cycle_due(145, cycles, 3) == 144  # within tolerance of 144
        # 178 is 2 away from 180 == 2*90, so the first matching cycle (90) wins.
        assert gann._cycle_due(178, cycles, 3) == 90
        assert gann._cycle_due(50, cycles, 3) is None

    def test_analyze_gann_shape_and_below_1x1(self) -> None:
        # Rally sets a confirmed swing low at 100, then a sustained decline so the
        # latest price sits below the 1x1 support projected from that low.
        p = _path([100, 150, 140, 120, 105], steps=8)
        r = analyze_gann(p, p, p, threshold_pct=5)
        assert r.nearest_resistance is not None and r.nearest_support is not None
        assert r.nearest_support < p[-1] < r.nearest_resistance
        assert r.below_1x1 is True
        assert r.signal == "BELOW_1X1_BEARISH"

    def test_analyze_gann_empty_on_short_series(self) -> None:
        r = analyze_gann([100.0], [100.0], [100.0])
        assert r.signal is None and r.nearest_resistance is None
