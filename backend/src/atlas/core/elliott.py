"""Rule-based Elliott Wave labeling — the objective core, made deterministic.

Discretionary Elliott counting is subjective. Its *rules*, however, are not:
the three inviolable impulse rules either hold for a given pivot sequence or they
don't. This module detects a 5-wave impulse over the deterministic ZigZag pivots
(``atlas.core.swings``) and enforces those rules, with a Fibonacci-guideline
confidence score. Same bars + same threshold -> same label, every time.

The three hard rules (enforced, never waived):
  R1. Wave 2 never retraces more than 100% of wave 1 (it cannot break wave 1's
      origin).
  R2. Wave 3 is never the shortest of waves 1, 3, 5.
  R3. Wave 4 never enters the price territory of wave 1 (no overlap).

A completed, rule-valid 5-wave *up* impulse is an exhaustion/▶sell-context signal
(expect an A-B-C correction); a completed *down* impulse is a buy-context signal.
This is contextual only — it never feeds the calibrated extension risk score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from atlas.core.swings import Pivot, zigzag_pivots

# Fibonacci guideline bands (used only for confidence, never for validity).
_W2_RETRACE_BAND: Final[tuple[float, float]] = (0.382, 0.886)  # wave 2 / wave 1
_W3_EXT_MIN: Final[float] = 1.0  # wave 3 / wave 1 (ideally >= 1.618)
_W4_RETRACE_BAND: Final[tuple[float, float]] = (0.15, 0.5)  # wave 4 / wave 3
_W5_BAND: Final[tuple[float, float]] = (0.382, 1.7)  # wave 5 / wave 1

_IMPULSE_PIVOTS: Final[int] = 6  # P0..P5 == 5 waves


@dataclass(frozen=True)
class ElliottResult:
    """Deterministic Elliott Wave read at the latest bar."""

    current_wave: str | None  # "1".."5" (count of completed legs) or None
    direction: str | None  # "UP" | "DOWN" | None
    impulse_complete: bool  # a full 5-wave structure is in place
    rules_valid: bool  # the three hard rules hold for that structure
    signal: str | None  # "IMPULSE_TOP_SELL" | "IMPULSE_BOTTOM_BUY" | None
    confidence: int  # 0-100, Fibonacci-guideline adherence
    pivots_used: int


def _in_band(ratio: float, band: tuple[float, float]) -> bool:
    return band[0] <= ratio <= band[1]


def _impulse_rules_valid(p: list[Pivot], up: bool) -> bool:
    """Enforce the three inviolable impulse rules on a 6-pivot window."""
    prices = [pv.price for pv in p]
    p0, p1, p2, p3, p4, p5 = prices
    w1, w3, w5 = abs(p1 - p0), abs(p3 - p2), abs(p5 - p4)
    if up:
        r1 = p2 > p0  # wave 2 holds above wave 1 origin
        r3 = p4 > p1  # wave 4 above wave 1 top (no overlap)
    else:
        r1 = p2 < p0
        r3 = p4 < p1
    r2 = not (w3 < w1 and w3 < w5)  # wave 3 not the shortest
    return r1 and r2 and r3


def _confidence(p: list[Pivot]) -> int:
    """Fibonacci-guideline adherence over a 6-pivot impulse (0-100)."""
    prices = [pv.price for pv in p]
    p0, p1, p2, p3, p4, p5 = prices
    w1, w2, w3, w4, w5 = (
        abs(p1 - p0),
        abs(p2 - p1),
        abs(p3 - p2),
        abs(p4 - p3),
        abs(p5 - p4),
    )
    if w1 == 0 or w3 == 0:
        return 0
    checks = [
        _in_band(w2 / w1, _W2_RETRACE_BAND),
        (w3 / w1) >= _W3_EXT_MIN,
        _in_band(w4 / w3, _W4_RETRACE_BAND),
        _in_band(w5 / w1, _W5_BAND),
    ]
    return round(100 * sum(checks) / len(checks))


def label_impulse(
    highs: list[float],
    lows: list[float],
    *,
    threshold_pct: float = 5.0,
) -> ElliottResult:
    """Detect the most recent impulse structure from ZigZag pivots."""
    pivots = zigzag_pivots(highs, lows, threshold_pct=threshold_pct)
    if len(pivots) < 2:
        return ElliottResult(None, None, False, False, None, 0, len(pivots))

    window = pivots[-_IMPULSE_PIVOTS:]
    legs = len(window) - 1  # each leg between two pivots is one wave
    current_wave = str(min(legs, 5))
    # Direction of the impulse: an up-impulse starts at a swing low.
    up = window[0].kind == "L"
    direction = "UP" if up else "DOWN"

    complete = legs >= 5
    rules_valid = False
    confidence = 0
    signal: str | None = None
    if complete:
        six = window[-_IMPULSE_PIVOTS:]
        rules_valid = _impulse_rules_valid(six, up)
        confidence = _confidence(six) if rules_valid else 0
        if rules_valid:
            signal = "IMPULSE_TOP_SELL" if up else "IMPULSE_BOTTOM_BUY"

    return ElliottResult(
        current_wave=current_wave,
        direction=direction,
        impulse_complete=complete and rules_valid,
        rules_valid=rules_valid,
        signal=signal,
        confidence=confidence,
        pivots_used=len(window),
    )
