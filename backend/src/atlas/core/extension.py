"""ATLAS Overbought / Extension Overlay — pure scoring engine.

A name can be fundamentally elite (high ATLAS conviction) and still be a bad
*entry* today because it is technically overbought / extended.  This module is
the pure, side-effect-free core of the Extension Overlay:

  * per-name extension metrics (RSI-14, RSI-7, 14d/21d moves, distance from the
    20/50/200-day MAs, gap %),
  * a 0-N "Extension Risk Score" built from a fixed points table,
  * a Green / Yellow / Red / Extreme-Red flag,
  * an action recommendation that combines ATLAS conviction (quality) with the
    extension flag (timing),
  * the F1 Momentum overbought cap that prevents a vertical chart from earning
    a perfect momentum sub-score.

Every function here is a pure function of its inputs (no I/O, no globals) so the
whole engine is unit-testable without any network calls.  IV rank is supplied by
the service from Unusual Whales (the same source the LEAPS module uses) and feeds
the points table here; it is an optional input and contributes 0 when absent.
Intraday VWAP gating is not modelled — the service surfaces the *daily* VWAP from
Polygon as a reference, but the intraday running VWAP would need a new data path.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Flags & actions
# ---------------------------------------------------------------------------


class ExtensionFlag:
    """Extension Risk flag buckets."""

    GREEN: Final[str] = "GREEN"
    YELLOW: Final[str] = "YELLOW"
    RED: Final[str] = "RED"
    EXTREME_RED: Final[str] = "EXTREME_RED"


class OverlayAction:
    """Action recommendations (ATLAS quality x extension timing)."""

    ADD: Final[str] = "ADD"
    BUY_ON_PULLBACK: Final[str] = "BUY_ON_PULLBACK"
    HOLD_TRIM: Final[str] = "HOLD_TRIM"
    TRIM_HEDGE: Final[str] = "TRIM_HEDGE"
    AVOID: Final[str] = "AVOID"


# ATLAS final score at/above which a name counts as "high conviction" for the
# action matrix (Tier 2+ per the v7.3.4 tier structure).
_HIGH_CONVICTION_MIN: Final[int] = 70

# ---------------------------------------------------------------------------
# Extension Risk Score — points table (client spec)
# ---------------------------------------------------------------------------

_RSI14_OVERBOUGHT: Final[float] = 70.0
_RSI14_EXTREME: Final[float] = 80.0
_RSI7_HOT: Final[float] = 75.0
_MOVE14_VERTICAL: Final[float] = 20.0
_MOVE14_EXTREME: Final[float] = 35.0
_MOVE21_EXTENDED: Final[float] = 30.0
_ABOVE_20DMA_STRETCH: Final[float] = 15.0
_ABOVE_50DMA_STRETCH: Final[float] = 25.0
_ABOVE_200DMA_STRETCH: Final[float] = 50.0
_GAP_CHASE: Final[float] = 5.0
_IV_RANK_EXPENSIVE: Final[float] = 70.0

# Flag bucket upper bounds (inclusive).
_GREEN_MAX: Final[int] = 2
_YELLOW_MAX: Final[int] = 5
_RED_MAX: Final[int] = 8

# F1 overbought caps.
_F1_CAP_SINGLE: Final[int] = 17
_F1_CAP_MULTI: Final[int] = 15


# ---------------------------------------------------------------------------
# Metric helpers — pure
# ---------------------------------------------------------------------------


def compute_rsi(closes: list[float], period: int) -> float | None:
    """Wilder RSI over a close-price series.

    Returns None when fewer than ``period + 1`` closes are available.  Returns
    100.0 for an all-up series and 50.0 for a perfectly flat series (the same
    conventions used by the F1 momentum service).
    """
    if period < 1 or len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0.0, c) for c in changes]
    losses = [max(0.0, -c) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def pct_move(closes: list[float], sessions: int) -> float | None:
    """Percentage price change over the trailing ``sessions`` trading days.

    Returns None when there are not enough closes, or when the reference close
    is zero.
    """
    if sessions < 1 or len(closes) < sessions + 1:
        return None
    then = closes[-(sessions + 1)]
    if then == 0:
        return None
    return (closes[-1] - then) / then * 100.0


def simple_ma(closes: list[float], window: int) -> float | None:
    """Simple moving average of the trailing ``window`` closes, or None."""
    if window < 1 or len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def pct_above_ma(price: float, ma: float | None) -> float | None:
    """Percentage distance of ``price`` above a moving average (None-safe)."""
    if ma is None or ma == 0:
        return None
    return (price - ma) / ma * 100.0


def gap_pct(today_open: float | None, prev_close: float | None) -> float | None:
    """Today's opening gap vs the prior session close, as a percentage."""
    if today_open is None or prev_close in (None, 0):
        return None
    return (today_open - prev_close) / prev_close * 100.0  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Extension Risk Score
# ---------------------------------------------------------------------------


def extension_risk_score(
    *,
    rsi14: float | None,
    rsi7: float | None,
    move14_pct: float | None,
    move21_pct: float | None,
    pct_above_20dma: float | None,
    pct_above_50dma: float | None,
    pct_above_200dma: float | None,
    gap_today_pct: float | None,
    iv_rank: float | None,
) -> int:
    """Sum the Extension Risk Score points table.

    Each metric only contributes when present (a missing/None metric scores 0
    rather than penalising the name).  RSI-14 and the 14-day move are graduated:
    the extreme tier replaces the lower tier (it does not stack).
    """
    points = 0

    if rsi14 is not None:
        if rsi14 > _RSI14_EXTREME:
            points += 3
        elif rsi14 > _RSI14_OVERBOUGHT:
            points += 2

    if rsi7 is not None and rsi7 > _RSI7_HOT:
        points += 2

    if move14_pct is not None:
        if move14_pct > _MOVE14_EXTREME:
            points += 3
        elif move14_pct > _MOVE14_VERTICAL:
            points += 2

    if move21_pct is not None and move21_pct > _MOVE21_EXTENDED:
        points += 2

    if pct_above_20dma is not None and pct_above_20dma > _ABOVE_20DMA_STRETCH:
        points += 2

    if pct_above_50dma is not None and pct_above_50dma > _ABOVE_50DMA_STRETCH:
        points += 2

    if pct_above_200dma is not None and pct_above_200dma > _ABOVE_200DMA_STRETCH:
        points += 1

    if gap_today_pct is not None and gap_today_pct > _GAP_CHASE:
        points += 2

    if iv_rank is not None and iv_rank > _IV_RANK_EXPENSIVE:
        points += 1

    return points


def classify_extension_flag(risk_score: int) -> str:
    """Bucket a risk score into a Green/Yellow/Red/Extreme-Red flag."""
    if risk_score <= _GREEN_MAX:
        return ExtensionFlag.GREEN
    if risk_score <= _YELLOW_MAX:
        return ExtensionFlag.YELLOW
    if risk_score <= _RED_MAX:
        return ExtensionFlag.RED
    return ExtensionFlag.EXTREME_RED


# ---------------------------------------------------------------------------
# Action matrix — ATLAS quality x extension timing
# ---------------------------------------------------------------------------

_HIGH_CONVICTION_ACTIONS: Final[dict[str, tuple[str, str]]] = {
    ExtensionFlag.GREEN: (
        OverlayAction.ADD,
        "Buyable — conviction is high and the name is not extended.",
    ),
    ExtensionFlag.YELLOW: (
        OverlayAction.BUY_ON_PULLBACK,
        "Good name; add only on a pullback / VWAP hold, size-controlled.",
    ),
    ExtensionFlag.RED: (
        OverlayAction.HOLD_TRIM,
        "Great company, bad entry — hold / trim strength; do not chase.",
    ),
    ExtensionFlag.EXTREME_RED: (
        OverlayAction.TRIM_HEDGE,
        "Extremely extended — trim / hedge; no new capital.",
    ),
}


def recommend_action(atlas_score: int | None, flag: str) -> tuple[str | None, str | None]:
    """Combine ATLAS conviction with the extension flag into an action.

    Returns ``(action, detail)``.  When ``atlas_score`` is None (caller did not
    supply a conviction score) the action is omitted — the overlay is purely
    informational without a quality anchor.

    Low-conviction names never generate a buy purely because they are oversold.
    """
    if atlas_score is None:
        return None, None

    if atlas_score < _HIGH_CONVICTION_MIN:
        if flag == ExtensionFlag.GREEN:
            return (
                OverlayAction.AVOID,
                "Oversold but conviction is insufficient — no new capital.",
            )
        return OverlayAction.AVOID, "Conviction is insufficient — no new capital."

    return _HIGH_CONVICTION_ACTIONS[flag]


# ---------------------------------------------------------------------------
# F1 Momentum overbought cap
# ---------------------------------------------------------------------------


def f1_overbought_cap(
    *,
    rsi14: float | None,
    move14_pct: float | None,
    pct_above_50dma: float | None,
    gap_today_pct: float | None,
) -> int | None:
    """Return the F1 Momentum ceiling for an overbought name, or None.

    Per the client spec:
      * Extremely extended on multiple metrics — RSI-14 > 80 AND 14-day move
        > +35% AND gap up > +5% — caps F1 at 15/20 (raw 75/100).
      * Extremely overbought on any single metric — RSI-14 > 80, OR 14-day move
        > +35%, OR price > 25% above the 50-day MA — caps F1 at 17/20 (raw
        85/100).

    A missing metric simply cannot trip its condition.  The cap is expressed on
    the 0-100 raw F1 scale (15/20 -> 75, 17/20 -> 85) so callers can clamp the
    composite F1 score directly.
    """
    rsi_extreme = rsi14 is not None and rsi14 > _RSI14_EXTREME
    move_extreme = move14_pct is not None and move14_pct > _MOVE14_EXTREME
    gap_chase = gap_today_pct is not None and gap_today_pct > _GAP_CHASE
    above_50_stretch = pct_above_50dma is not None and pct_above_50dma > _ABOVE_50DMA_STRETCH

    if rsi_extreme and move_extreme and gap_chase:
        return _F1_CAP_MULTI * 5  # 15/20 -> 75/100

    if rsi_extreme or move_extreme or above_50_stretch:
        return _F1_CAP_SINGLE * 5  # 17/20 -> 85/100

    return None
