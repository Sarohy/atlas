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

from dataclasses import dataclass
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
    STARTER_WATCH: Final[str] = "STARTER_WATCH"
    BUY_ON_PULLBACK: Final[str] = "BUY_ON_PULLBACK"
    HOLD_TRIM: Final[str] = "HOLD_TRIM"
    TRIM_HEDGE: Final[str] = "TRIM_HEDGE"
    AVOID: Final[str] = "AVOID"


# ATLAS final score at/above which a name counts as "high conviction" for the
# action matrix (Tier 2+ per the v7.3.4 tier structure).
_HIGH_CONVICTION_MIN: Final[int] = 70

# F4 options-flow score at/above which flow is "confirming" (BUY-grade). Mirrors
# forward_growth._F4_CONFIRMING_MIN so the two panels agree on what "flow
# confirmation" means. A non-extended high-quality name only earns a full ADD
# once flow confirms; below this it is STARTER / WATCH (add on confirmation).
_F4_CONFIRMING_MIN: Final[int] = 60

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
# Technical sell / exhaustion signals (deterministic, price-only)
# ---------------------------------------------------------------------------
#
# DeMark TD Sequential, RSI bearish divergence, and a fresh MACD bearish cross —
# all computed from the daily bars. Elliott Wave / Gann are intentionally NOT
# here: they are interpretive (no objective algorithm) and would be vibes dressed
# as math. These three are objective exhaustion reads that reinforce the
# "extended — don't chase" timing signal.


@dataclass(frozen=True)
class TdSequential:
    """DeMark TD Sequential state at the latest bar (simplified — standard
    9-count setup + a 13-count sell countdown, without the esoteric
    deferral/qualifier rules)."""

    setup_count: int  # current consecutive setup count, capped at 9
    setup_direction: str | None  # "SELL" | "BUY" | None
    sell_countdown: int  # 0-13 sell countdown progress since the last setup-9
    signal: str | None  # "SELL_SETUP_9" | "SELL_COUNTDOWN_13" | "BUY_SETUP_9" | None


def td_sequential(highs: list[float], closes: list[float]) -> TdSequential:
    """Compute DeMark TD Sequential (setup + sell countdown) from daily bars.

    TD setup: a bar is a *sell* setup bar when close > close 4 bars earlier
    (a *buy* setup bar when close < close 4 bars earlier); 9 consecutive
    completes a setup. TD sell countdown: after a completed sell setup, count
    bars where close >= the high 2 bars earlier, up to 13.
    """
    n = len(closes)
    if n < 5:
        return TdSequential(0, None, 0, None)

    sell_run = 0
    buy_run = 0
    sell_complete_idx: list[int] = []
    for i in range(4, n):
        if closes[i] > closes[i - 4]:
            sell_run, buy_run = sell_run + 1, 0
        elif closes[i] < closes[i - 4]:
            buy_run, sell_run = buy_run + 1, 0
        else:
            sell_run = buy_run = 0
        if sell_run == 9:
            sell_complete_idx.append(i)

    if sell_run > 0:
        count, direction = min(sell_run, 9), "SELL"
    elif buy_run > 0:
        count, direction = min(buy_run, 9), "BUY"
    else:
        count, direction = 0, None

    countdown = 0
    if sell_complete_idx:
        start = sell_complete_idx[-1]
        for i in range(start + 1, n):
            if i >= 2 and closes[i] >= highs[i - 2]:
                countdown += 1
                if countdown >= 13:
                    break

    signal: str | None = None
    if countdown >= 13:
        signal = "SELL_COUNTDOWN_13"
    elif direction == "SELL" and count >= 9:
        signal = "SELL_SETUP_9"
    elif direction == "BUY" and count >= 9:
        signal = "BUY_SETUP_9"

    return TdSequential(count, direction, min(countdown, 13), signal)


def rsi_series(closes: list[float], period: int) -> list[float | None]:
    """Wilder RSI value at each bar (None for the first ``period`` bars)."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0.0, c) for c in changes]
    losses = [max(0.0, -c) for c in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(g: float, ls: float) -> float:
        if ls == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / ls)

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


def detect_rsi_bearish_divergence(
    closes: list[float],
    rsi_vals: list[float | None],
    *,
    window: int = 40,
    pivot_k: int = 3,
) -> bool:
    """True when the two most recent price pivot-highs make a higher high while
    RSI makes a lower high (classic bearish divergence)."""
    if len(closes) != len(rsi_vals) or len(closes) < pivot_k * 2 + 2:
        return False
    start = max(pivot_k, len(closes) - window)
    pivots = [
        i
        for i in range(start, len(closes) - pivot_k)
        if rsi_vals[i] is not None and closes[i] == max(closes[i - pivot_k : i + pivot_k + 1])
    ]
    if len(pivots) < 2:
        return False
    p_prev, p_last = pivots[-2], pivots[-1]
    r_prev, r_last = rsi_vals[p_prev], rsi_vals[p_last]
    if r_prev is None or r_last is None:
        return False
    return closes[p_last] > closes[p_prev] and r_last < r_prev


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def macd_bearish_cross(
    closes: list[float], *, fast: int = 12, slow: int = 26, signal: int = 9, recent: int = 5
) -> bool:
    """True when the MACD line crossed below its signal within the last ``recent``
    sessions (a fresh bearish cross within the past week — still actionable)."""
    if len(closes) < slow + signal + 1:
        return False
    fast_e = _ema(closes, fast)
    slow_e = _ema(closes, slow)
    macd_line = [f - s for f, s in zip(fast_e[slow - 1 :], slow_e[slow - 1 :], strict=True)]
    if len(macd_line) < 2:
        return False
    sig = _ema(macd_line, signal)
    macd_aligned = macd_line[-len(sig) :]
    if len(macd_aligned) < 2 or len(sig) < 2:
        return False
    span = min(recent, len(sig) - 1)
    return any(
        macd_aligned[-i] < sig[-i] and macd_aligned[-i - 1] >= sig[-i - 1]
        for i in range(1, span + 1)
    )


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
    td_sell_signal: str | None = None,
    rsi_bearish_divergence: bool = False,
    macd_bearish_cross: bool = False,
) -> int:
    """Sum the Extension Risk Score points table.

    Each metric only contributes when present (a missing/None metric scores 0
    rather than penalising the name).  RSI-14 and the 14-day move are graduated:
    the extreme tier replaces the lower tier (it does not stack).

    Deterministic technical sell/exhaustion signals add modest points on top:
    a DeMark sell countdown (13) > sell setup (9), an RSI bearish divergence,
    and a fresh MACD bearish cross — they reinforce "extended, don't chase".
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

    # Technical sell / exhaustion signals.
    if td_sell_signal == "SELL_COUNTDOWN_13":
        points += 3
    elif td_sell_signal == "SELL_SETUP_9":
        points += 2
    if rsi_bearish_divergence:
        points += 2
    if macd_bearish_cross:
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

# GREEN is handled separately in recommend_action() because a non-extended,
# high-conviction name must clear the F4 flow gate before it earns a full ADD.
_HIGH_CONVICTION_ACTIONS: Final[dict[str, tuple[str, str]]] = {
    ExtensionFlag.YELLOW: (
        OverlayAction.BUY_ON_PULLBACK,
        "Good name; add only on a pullback / VWAP hold, size-controlled.",
    ),
    # High-conviction name that is technically extended. This is a "wait for a
    # better entry" signal, NOT a sell — for a core compounder like MU, "trim"
    # is a position-sizing instruction (rebalance only if overweight), never a
    # bearish call on the name.
    ExtensionFlag.RED: (
        OverlayAction.HOLD_TRIM,
        "Great company, extended entry. Do not chase fresh adds. Hold core "
        "position; trim only into strength if position size is above target. "
        "Add on pullback, VWAP reset, or post-event confirmation.",
    ),
    # Extremely extended high-conviction name. The gate is "no fresh add", and
    # trim/hedge is sizing discipline (only if the position is above target) —
    # NOT a mandatory bearish sell. Re-add on reset / flow confirmation.
    ExtensionFlag.EXTREME_RED: (
        OverlayAction.TRIM_HEDGE,
        "Extremely extended — no fresh add. Trim / hedge only if the position is "
        "above target (overweight); this is sizing discipline, not a mandatory "
        "sell. Re-add on a reset / VWAP hold / flow (F4) confirmation.",
    ),
}


def recommend_action(
    atlas_score: int | None,
    flag: str,
    f4_score: int | None = None,
) -> tuple[str | None, str | None]:
    """Combine ATLAS conviction, extension flag, and F4 flow into an action.

    Returns ``(action, detail)``.  When ``atlas_score`` is None (caller did not
    supply a conviction score) the action is omitted — the overlay is purely
    informational without a quality anchor.

    Low-conviction names never generate a buy purely because they are oversold.

    Flow gate (ATLAS v2.2): a non-extended (GREEN) high-conviction name is NOT a
    full ADD on quality + clean extension alone.  A full ADD requires options
    flow (F4) to confirm (``f4_score >= _F4_CONFIRMING_MIN``).  When flow is
    neutral/weak or unavailable, the action is STARTER / WATCH — start small and
    add on flow confirmation — so the screen never says "ADD" while another panel
    says "wait for F4 confirmation".  This only gates GREEN; it never makes an
    extended name MORE aggressive (no options override of a hold/trim).
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

    if flag == ExtensionFlag.GREEN:
        f4_confirming = f4_score is not None and f4_score >= _F4_CONFIRMING_MIN
        if f4_confirming:
            return (
                OverlayAction.ADD,
                "Buyable — conviction is high, the name is not extended, and "
                "options flow (F4) is confirming.",
            )
        return (
            OverlayAction.STARTER_WATCH,
            "STARTER / WATCH — quality and extension are clean, but options flow "
            "(F4) is neutral/unconfirmed. Start small; add on F4 flow confirmation.",
        )

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
