"""Deterministic ZigZag swing-pivot detector.

Shared foundation for the (rule-based, reproducible) Elliott Wave and Gann
engines. The classic art of EW/Gann is discretionary; the *inputs* don't have
to be. This module turns a price series into an unambiguous, alternating
sequence of swing highs/lows using a fixed percentage-reversal threshold —
given the same bars and threshold, the pivots are always identical.

Pure functions only: no I/O, no globals, fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_DEFAULT_THRESHOLD_PCT: Final[float] = 5.0


@dataclass(frozen=True)
class Pivot:
    """A confirmed swing pivot."""

    index: int  # bar index in the input series
    price: float  # swing extreme (high for "H", low for "L")
    kind: str  # "H" (swing high) or "L" (swing low)


def zigzag_pivots(
    highs: list[float],
    lows: list[float],
    *,
    threshold_pct: float = _DEFAULT_THRESHOLD_PCT,
) -> list[Pivot]:
    """Return alternating swing pivots via the ZigZag rule.

    A new pivot is confirmed only after price reverses from the running extreme
    by more than ``threshold_pct``. The result strictly alternates H/L. The final
    (still-forming) extreme is appended as a tentative last pivot so callers can
    see the current leg.
    """
    n = min(len(highs), len(lows))
    if n < 2:
        return []
    thr = threshold_pct / 100.0
    pivots: list[Pivot] = []

    trend = 0  # 0 unknown, 1 up-leg, -1 down-leg
    ext_i = 0
    ext_p = highs[0]
    hi_i, hi = 0, highs[0]
    lo_i, lo = 0, lows[0]

    for i in range(1, n):
        if trend == 0:
            if highs[i] > hi:
                hi, hi_i = highs[i], i
            if lows[i] < lo:
                lo, lo_i = lows[i], i
            # Establish the first leg once a >threshold move is in the books.
            if lo_i < hi_i and hi >= lo * (1 + thr):
                trend, ext_i, ext_p = 1, hi_i, hi
                pivots.append(Pivot(lo_i, lo, "L"))
            elif hi_i < lo_i and lo <= hi * (1 - thr):
                trend, ext_i, ext_p = -1, lo_i, lo
                pivots.append(Pivot(hi_i, hi, "H"))
        elif trend == 1:
            if highs[i] > ext_p:
                ext_p, ext_i = highs[i], i
            elif lows[i] <= ext_p * (1 - thr):
                pivots.append(Pivot(ext_i, ext_p, "H"))
                trend, ext_i, ext_p = -1, i, lows[i]
        else:  # trend == -1
            if lows[i] < ext_p:
                ext_p, ext_i = lows[i], i
            elif highs[i] >= ext_p * (1 + thr):
                pivots.append(Pivot(ext_i, ext_p, "L"))
                trend, ext_i, ext_p = 1, i, highs[i]

    if trend == 1:
        pivots.append(Pivot(ext_i, ext_p, "H"))
    elif trend == -1:
        pivots.append(Pivot(ext_i, ext_p, "L"))
    return pivots
