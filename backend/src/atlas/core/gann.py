"""Rule-based Gann analysis — the reproducible subset, made deterministic.

The classic objection to Gann is real: angles need a price/time scaling and a
pivot, and time cycles can drift into numerology. This module removes the
arbitrariness:

  * Square-of-9 levels are pure arithmetic on sqrt(price) at 90-degree (0.25)
    increments — no judgement involved.
  * The 1x1 angle is anchored to the most recent deterministic ZigZag swing low
    (``atlas.core.swings``) and scaled by ATR-per-bar — a measured quantity, not
    a hand-drawn slope. Price below the 1x1 = trend support broken.
  * Time cycles are fixed Gann counts (90/144/180/360) measured from the last
    detected pivot, flagged only within a small tolerance.

Same bars + same threshold -> same output. Contextual/timing only — never feeds
the calibrated extension risk score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from atlas.core.swings import zigzag_pivots

_SQ9_RINGS: Final[int] = 3
_SQ9_STEP: Final[float] = 0.25  # 90 degrees on the Square of 9
_GANN_CYCLES: Final[tuple[int, ...]] = (90, 144, 180, 360)
_TIME_TOLERANCE_BARS: Final[int] = 3
_RESISTANCE_PROXIMITY: Final[float] = 0.01  # within 1% of a Sq9 resistance


@dataclass(frozen=True)
class GannResult:
    """Deterministic Gann read at the latest bar."""

    nearest_resistance: float | None
    nearest_support: float | None
    below_1x1: bool  # price below the 1x1 support line from the last swing low
    time_cycle_due: bool  # near a 90/144/180/360-bar count from the last pivot
    nearest_cycle: int | None
    bars_since_pivot: int | None
    signal: str | None  # "BELOW_1X1_BEARISH" | "AT_GANN_RESISTANCE" | "TIME_TURN_DUE" | None


def square_of_9_levels(price: float, *, rings: int = _SQ9_RINGS) -> list[float]:
    """Square-of-9 support/resistance ladder around *price* (sorted ascending)."""
    if price <= 0:
        return []
    root = math.sqrt(price)
    levels = []
    for k in range(-rings, rings + 1):
        if k == 0:
            continue
        v = (root + k * _SQ9_STEP) ** 2
        if v > 0:
            levels.append(round(v, 4))
    return sorted(levels)


def average_true_range(
    highs: list[float], lows: list[float], closes: list[float], *, period: int = 14
) -> float | None:
    """Wilder-style ATR (simple mean of true ranges over *period*)."""
    n = min(len(highs), len(lows), len(closes))
    if n < 2:
        return None
    trs = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, n)
    ]
    if not trs:
        return None
    p = min(period, len(trs))
    return sum(trs[-p:]) / p


def _cycle_due(bars_since: int, cycles: tuple[int, ...], tol: int) -> int | None:
    """Return the cycle length whose multiple ``bars_since`` is within *tol* of."""
    for c in cycles:
        rem = bars_since % c
        if min(rem, c - rem) <= tol:
            return c
    return None


def analyze_gann(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    threshold_pct: float = 5.0,
    atr_period: int = 14,
) -> GannResult:
    """Compute Square-of-9 levels, 1x1-angle status, and time-cycle proximity."""
    n = min(len(highs), len(lows), len(closes))
    if n < 2:
        return GannResult(None, None, False, False, None, None, None)

    price = closes[-1]
    cur_idx = n - 1
    levels = square_of_9_levels(price)
    nearest_res = min((lv for lv in levels if lv > price), default=None)
    nearest_sup = max((lv for lv in levels if lv < price), default=None)

    pivots = zigzag_pivots(highs, lows, threshold_pct=threshold_pct)
    unit = average_true_range(highs, lows, closes, period=atr_period)

    below_1x1 = False
    # Anchor the 1x1 to the last *confirmed* swing low — the final ZigZag pivot
    # is the still-forming leg and would track the current price itself.
    swing_lows = [p for p in pivots[:-1] if p.kind == "L"]
    if swing_lows and unit and unit > 0:
        anchor = swing_lows[-1]
        line = anchor.price + (cur_idx - anchor.index) * unit
        below_1x1 = price < line

    bars_since: int | None = None
    nearest_cycle: int | None = None
    if pivots:
        bars_since = cur_idx - pivots[-1].index
        if bars_since > 0:
            nearest_cycle = _cycle_due(bars_since, _GANN_CYCLES, _TIME_TOLERANCE_BARS)

    time_due = nearest_cycle is not None

    signal: str | None = None
    if below_1x1:
        signal = "BELOW_1X1_BEARISH"
    elif nearest_res is not None and (nearest_res - price) / price <= _RESISTANCE_PROXIMITY:
        signal = "AT_GANN_RESISTANCE"
    elif time_due:
        signal = "TIME_TURN_DUE"

    return GannResult(
        nearest_resistance=round(nearest_res, 2) if nearest_res is not None else None,
        nearest_support=round(nearest_sup, 2) if nearest_sup is not None else None,
        below_1x1=below_1x1,
        time_cycle_due=time_due,
        nearest_cycle=nearest_cycle,
        bars_since_pivot=bars_since,
        signal=signal,
    )
