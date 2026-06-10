"""Section 15 — Three-Bucket Allocation pure functions.

Side-effect-free helpers implementing the Section 15 bucket rules:

  * ``classify_position_bucket`` — Bucket 1 (core T1/T2), Bucket 2 (LEAPS), or
    Bucket 3 (satellite) by conviction score / LEAPS flag.
  * ``compute_bucket_weights`` — roll position values into per-bucket NAV weights
    with cap / target flags (B1 target 75-82%, B2 cap 4%, B3 cap 5%).
  * ``check_bucket3_satellite_eligible`` — satellite gate (score must clear 55
    after the CAUTION -5 modifier per Section 15.5).
  * ``get_regime_floor_pct`` — regime cash-floor lookup (Section 14.1).
  * ``compute_aggregate_gtc_exposure`` — aggregate near-money GTC window vs the
    buffered regime floor (Section 15.3); deep-OTM (>8% below) GTCs are exempt.
  * ``check_bucket1_add_conditions`` — Bucket 1 tactical-add gate (Section 15.1).

No I/O — fully unit-testable without a DB or network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

# ---------------------------------------------------------------------------
# Thresholds (Section 15)
# ---------------------------------------------------------------------------

_B1_MIN_SCORE: Final[int] = 70  # Tier 2+ → Bucket 1
_B1_TARGET_MIN_PCT: Final[float] = 75.0
_B1_TARGET_MAX_PCT: Final[float] = 82.0
_B2_CAP_PCT: Final[float] = 4.0  # LEAPS total cap
_B3_CAP_PCT: Final[float] = 5.0  # Satellite total cap
_B3_CAUTION_MODIFIER: Final[int] = 5  # Section 15.5 satellite gate uses CAUTION (-5)
_B3_MIN_SCORE: Final[int] = 55

_TACTICAL_ADD_REGIMES: Final[frozenset[str]] = frozenset({"CLEAR", "SOFT_CAUTION"})
_DARK_POOL_MIN_USD: Final[float] = 500_000.0  # strictly greater than
_UNDERWEIGHT_MIN_GAP_PCT: Final[float] = 0.5
_SOFT_CAP_PCT: Final[float] = 8.0
_DEEP_OTM_PCT: Final[float] = 8.0  # strictly more than 8% below → deep-OTM, exempt
_GTC_BUFFER_MULT: Final[float] = 1.1  # Section 15.3 buffer multiplier

# Section 14.1 regime cash floors (as fractions of NAV).
_REGIME_FLOORS: Final[dict[str, float]] = {
    "CLEAR": 0.08,
    "SOFT_CAUTION": 0.15,
    "CAUTION": 0.20,
    "CRISIS": 0.30,
    "CRISIS_HALT": 0.30,
}
_CONSERVATIVE_FLOOR: Final[float] = 0.30  # unknown/missing regime → most conservative

# Float comparison tolerance for boundary thresholds (e.g. exactly 4.0%).
_EPS: Final[float] = 1e-9


# ---------------------------------------------------------------------------
# Position classification
# ---------------------------------------------------------------------------


def classify_position_bucket(score: int | None, is_leaps: bool) -> str | None:
    """Classify a position into B1 / B2 / B3.

    LEAPS are always Bucket 2 regardless of score.  Otherwise a score >= 70
    (Tier 2+) is Bucket 1 and anything below is Bucket 3.  An unknown score on
    a non-LEAPS position is unclassified (None).
    """
    if is_leaps:
        return "B2"
    if score is None:
        return None
    return "B1" if score >= _B1_MIN_SCORE else "B3"


# ---------------------------------------------------------------------------
# Bucket weights
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BucketWeights:
    """Per-bucket NAV weights (percent) with cap/target flags."""

    b1_weight_pct: float
    b2_weight_pct: float
    b3_weight_pct: float
    unclassified_weight_pct: float
    b1_at_target: bool
    b1_below_target: bool
    b2_at_cap: bool
    b3_at_cap: bool


def compute_bucket_weights(
    positions: list[dict[str, Any]], total_nav: float
) -> BucketWeights:
    """Sum position values per bucket and express each as a percent of NAV."""
    sums = {"B1": 0.0, "B2": 0.0, "B3": 0.0, "UNCLASSIFIED": 0.0}
    for pos in positions:
        bucket = pos.get("bucket")
        key = bucket if bucket in ("B1", "B2", "B3") else "UNCLASSIFIED"
        sums[key] += float(pos.get("position_value") or 0.0)

    if total_nav <= 0:
        return BucketWeights(0.0, 0.0, 0.0, 0.0, False, False, False, False)

    b1 = sums["B1"] / total_nav * 100.0
    b2 = sums["B2"] / total_nav * 100.0
    b3 = sums["B3"] / total_nav * 100.0
    unclassified = sums["UNCLASSIFIED"] / total_nav * 100.0

    return BucketWeights(
        b1_weight_pct=b1,
        b2_weight_pct=b2,
        b3_weight_pct=b3,
        unclassified_weight_pct=unclassified,
        b1_at_target=_B1_TARGET_MIN_PCT - _EPS <= b1 <= _B1_TARGET_MAX_PCT + _EPS,
        b1_below_target=b1 < _B1_TARGET_MIN_PCT - _EPS,
        b2_at_cap=b2 >= _B2_CAP_PCT - _EPS,
        b3_at_cap=b3 >= _B3_CAP_PCT - _EPS,
    )


# ---------------------------------------------------------------------------
# Bucket 3 satellite eligibility
# ---------------------------------------------------------------------------


def check_bucket3_satellite_eligible(score: int) -> bool:
    """Section 15.5 — a satellite must score >= 55 after the CAUTION (-5) modifier."""
    return (score - _B3_CAUTION_MODIFIER) >= _B3_MIN_SCORE


# ---------------------------------------------------------------------------
# Regime cash floor
# ---------------------------------------------------------------------------


def get_regime_floor_pct(regime: str | None) -> float:
    """Return the regime cash floor as a fraction of NAV (Section 14.1).

    Unknown or missing regimes return the most conservative floor (30%).
    """
    if regime is None:
        return _CONSERVATIVE_FLOOR
    return _REGIME_FLOORS.get(regime.strip().upper(), _CONSERVATIVE_FLOOR)


# ---------------------------------------------------------------------------
# Aggregate GTC exposure (Section 15.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AggregateGtcExposure:
    """Near-money GTC notional vs the buffered regime-floor window."""

    near_gtc_usd: float
    deep_otm_gtc_usd: float
    regime_floor_pct: float
    max_aggregate_usd: float
    window_usd: float
    window_ok: bool


def compute_aggregate_gtc_exposure(
    orders: list[dict[str, Any]],
    prices: dict[str, float | None],
    cash_usd: float,
    total_nav: float,
    regime: str | None,
) -> AggregateGtcExposure:
    """Aggregate near-money GTC notional and compare it to the available window.

    Only GTCs within 8% of market count toward the aggregate; deep-OTM orders
    (more than 8% below market) are exempt because they cannot fill without a
    move large enough to imply a regime change.  Orders whose ticker has no
    known market price are excluded entirely.
    """
    near = 0.0
    deep = 0.0
    for order in orders:
        ticker_sym = order.get("ticker")
        if not isinstance(ticker_sym, str):
            continue
        market = prices.get(ticker_sym)
        if market is None or market <= 0:
            continue
        limit = float(order.get("limit_price") or 0.0)
        qty = float(order.get("quantity") or 0.0)
        notional = limit * qty
        pct_below = (market - limit) / market * 100.0
        if pct_below > _DEEP_OTM_PCT + _EPS:
            deep += notional
        else:
            near += notional

    floor = get_regime_floor_pct(regime)
    max_aggregate = cash_usd - (_GTC_BUFFER_MULT * floor * total_nav)
    window = max_aggregate - near
    return AggregateGtcExposure(
        near_gtc_usd=near,
        deep_otm_gtc_usd=deep,
        regime_floor_pct=floor,
        max_aggregate_usd=max_aggregate,
        window_usd=window,
        window_ok=window >= 0,
    )


# ---------------------------------------------------------------------------
# Bucket 1 tactical-add conditions (Section 15.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Bucket1AddConditions:
    """Result of the Bucket 1 tactical-add gate."""

    eligible: bool
    regime_ok: bool
    dark_pool_ok: bool
    underweight_ok: bool
    soft_cap_ok: bool
    reasons_blocked: list[str]


def check_bucket1_add_conditions(
    *,
    ticker: str,
    current_weight_pct: float | None,
    target_min_pct: float,
    regime: str | None,
    dark_pool_total_usd: float | None,
) -> Bucket1AddConditions:
    """Section 15.1 — a Bucket 1 tactical add requires ALL of:

      * regime is CLEAR or SOFT_CAUTION,
      * dark pool > $500K (strictly) for the name,
      * the name is at least 0.5% below its target weight,
      * the add does not sit at/above the 8% soft cap.
    """
    reasons: list[str] = []

    regime_ok = regime is not None and regime.strip().upper() in _TACTICAL_ADD_REGIMES
    if not regime_ok:
        reasons.append(f"Regime {regime} does not permit Bucket 1 tactical adds.")

    dark_pool_ok = dark_pool_total_usd is not None and dark_pool_total_usd > _DARK_POOL_MIN_USD
    if not dark_pool_ok:
        reasons.append(
            f"Dark pool {dark_pool_total_usd} does not exceed ${_DARK_POOL_MIN_USD:,.0f}."
        )

    if current_weight_pct is None:
        underweight_ok = False
        reasons.append(f"{ticker} current weight unknown — cannot confirm underweight.")
    else:
        underweight_ok = (target_min_pct - current_weight_pct) >= _UNDERWEIGHT_MIN_GAP_PCT - _EPS
        if not underweight_ok:
            reasons.append(f"{ticker} is not at least 0.5% below its target weight.")

    soft_cap_ok = current_weight_pct is None or current_weight_pct < _SOFT_CAP_PCT - _EPS
    if not soft_cap_ok:
        reasons.append(f"{ticker} is at or above the 8% soft cap.")

    eligible = regime_ok and dark_pool_ok and underweight_ok and soft_cap_ok
    return Bucket1AddConditions(
        eligible=eligible,
        regime_ok=regime_ok,
        dark_pool_ok=dark_pool_ok,
        underweight_ok=underweight_ok,
        soft_cap_ok=soft_cap_ok,
        reasons_blocked=reasons,
    )
