"""Section 17 — LEAPS Strategy Module service.

V1 scope: read-only eligibility tracking.  No execution engine.
Positions are tracked manually via the leaps_positions table.

Eligibility (tristate: True | False | None):
  True  — all required checks passed
  False — one or more checks failed (blocked)
  None  — required data unavailable; decision deferred

Tier rules:
  T1_ELITE (score ≥ 85): auto-eligible when IV ≤ 90% and gates clear
  T1 (80-84): eligible only with $500K+ dark pool flow from F9
  T2 (70-79): eligible only with $500K+ dark pool flow from F9
  T3 / BELOW_GATE: ineligible

IV hard rule:
  IV > 90% always blocks LEAPS regardless of tier.
  IV = null → iv_blocked = null → leaps_eligible = null.

Gate rules:
  F7 earnings gate active → LEAPS blocked
  F29 AND gate not passed → LEAPS blocked
  F30 HARD_HALT → LEAPS blocked
  F30 CARVEOUT → LEAPS allowed but capped per leaps_position_cap_pct

Entry conditions (Section 17.4):
  1. Washout signal — VIX spike with subsequent decline (sourced from F29 Signal 1)
  2. Regime confirms CLEAR or SOFT_CAUTION (F2 regime state)
  3. Score improvement momentum (3 consecutive session improvement)

Caching:
  Results are cached per ticker for 5 minutes (300 s).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Final

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.leaps import LeapsPosition
from atlas.schemas.leaps import (
    EntryCondition,
    EntryConditionStatus,
    IVAlert,
    LeapsBucketStatus,
    LeapsEligibility,
    SizeGuidanceSchema,
    _default_expiry_guidance,
)
from atlas.schemas.leaps import (
    LeapsPosition as LeapsPositionSchema,
)
from atlas.core.scoring import classify_tier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes

# CRITICAL — single source of truth for the conviction score read by LEAPS.
# Always read this attribute from the regime-modifier response. It is the
# post-regime conviction score: F1-F5 weighted → F8 cap on F5 → regime
# modifier applied. NEVER read pre-regime fields (e.g. ``final_score`` from
# FrameworkScoreResponse, ``raw_total``, ``f1_score``..``f5_score``,
# ``pre_regime_score``) for LEAPS decisions. If this constant changes, every
# read site updates with one edit.
F1_SCORE_FIELD: Final[str] = "adjusted_score"

# Valid range for a conviction score; anything outside is treated as invalid
# input and forces ``leaps_eligible=None`` with a defensive block reason.
_SCORE_MIN: Final[int] = 0
_SCORE_MAX: Final[int] = 100

# Tier score thresholds — derived from core/scoring.py (single source of truth).
# These are kept as named constants for clarity in LEAPS-specific rules only.
_TIER_1_SCORE_MIN: Final[int] = 85   # T1_ELITE
_TIER_2_SCORE_MIN: Final[int] = 70   # Minimum score for any LEAPS eligibility (T2 and above)

# IV hard-block threshold (as a decimal fraction, e.g. 0.90 = 90%).
_IV_BLOCK_THRESHOLD: Final[float] = 0.90

# Dark pool flow required for Tier 2 LEAPS eligibility.
_TIER_2_DARK_POOL_FLOW_USD: Final[float] = 500_000.0

# LEAPS bucket cap as % of NAV (Bucket 2 hard cap per F33 spec).
_LEAPS_BUCKET_CAP_PCT: Final[float] = 4.0  # 4% max of NAV

# Unusual Whales IV endpoint.
_UW_BASE_URL: Final[str] = "https://api.unusualwhales.com"
_UW_IV_URL: Final[str] = f"{_UW_BASE_URL}/api/stock/{{ticker}}/iv-rank"

# Regime states that clear LEAPS eligibility.
_LEAPS_ALLOWED_REGIMES: Final[frozenset[str]] = frozenset(
    {"CLEAR", "SOFT_CAUTION", "NORMAL", "NONE"}
)

# Days to wait after a major catalyst (earnings) for IV to compress.
_IV_CATALYST_WAIT_DAYS: Final[int] = 7

# Minimum price gap (open vs. prev close as %) to trigger the gap-entry block.
_GAP_THRESHOLD_PCT: Final[float] = 2.0  # 2% gap constitutes a "gap day"

# Polygon snapshot URL for gap detection (open / prev-close fetch).
_POLYGON_TICKER_SNAPSHOT_URL: Final[str] = (
    "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
)

# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[LeapsEligibility, float]] = {}


def _cache_get(ticker: str) -> tuple[LeapsEligibility | None, float]:
    """Return (result, age_minutes) from cache, or (None, 0)."""
    entry = _cache.get(ticker)
    if entry is None:
        return None, 0.0
    result, fetched_at = entry
    age_minutes = (time.time() - fetched_at) / 60.0
    return result, age_minutes


def _cache_set(ticker: str, result: LeapsEligibility) -> None:
    """Store result in cache."""
    _cache[ticker] = (result, time.time())


def _cache_invalidate(ticker: str) -> None:
    """Remove cached result for ticker."""
    _cache.pop(ticker, None)


# ---------------------------------------------------------------------------
# Entry type classification (pure)
# ---------------------------------------------------------------------------

# Thresholds for WASHOUT detection.
_WASHOUT_DROP_THRESHOLD: Final[float] = 0.08   # single-session price drop ≥ 8%
_WASHOUT_F4_SCORE_MIN: Final[float] = 11.0     # F4 dark pool score ≥ 11

# Thresholds for CATALYST_VALIDATED detection.
_CATALYST_T2_SCORE_MIN: Final[int] = 70        # T2 tier floor (score ≥ 70)
_CATALYST_MIN_SIGNALS: Final[int] = 2          # minimum confirmed catalyst signals


def _determine_entry_type(
    single_session_drop_pct: float | None,
    f4_score: float | None,
    position_held: bool,
    score: int | None,
    catalyst_13f_concentration_buy: bool | None = None,
    catalyst_analyst_pt_raise: bool | None = None,
    catalyst_revenue_inflection: bool | None = None,
) -> str:
    """Classify the F29 entry type.  Pure function — no I/O.

    Priority order:
      1. WASHOUT: underlying fell ≥8% in a single session AND F4 dark pool ≥11.
         Bypasses the F29 AND gate entirely.
      2. CATALYST_VALIDATED: position already held + score ≥ T2 (≥70) + at
         least 2 of: 13F concentration buy, analyst PT raise post-mgmt meeting,
         revenue inflection confirmed in earnings.
         Also bypasses the F29 AND gate.
      3. DISCRETIONARY: everything else.  Requires F29 AND gate to pass.

    Returns one of the string literals "WASHOUT", "CATALYST_VALIDATED", or
    "DISCRETIONARY".
    """
    # 1 — WASHOUT check (highest priority)
    if (
        single_session_drop_pct is not None
        and single_session_drop_pct >= _WASHOUT_DROP_THRESHOLD
        and f4_score is not None
        and f4_score >= _WASHOUT_F4_SCORE_MIN
    ):
        return "WASHOUT"

    # 2 — CATALYST_VALIDATED check
    if position_held and score is not None and score >= _CATALYST_T2_SCORE_MIN:
        catalyst_signals = [
            catalyst_13f_concentration_buy,
            catalyst_analyst_pt_raise,
            catalyst_revenue_inflection,
        ]
        confirmed_count = sum(1 for s in catalyst_signals if s is True)
        if confirmed_count >= _CATALYST_MIN_SIGNALS:
            return "CATALYST_VALIDATED"

    return "DISCRETIONARY"


# ---------------------------------------------------------------------------
# Score resolution helper
# ---------------------------------------------------------------------------


async def _resolve_current_score(
    ticker: str,
    *,
    polygon_api_key: str,
    uw_api_key: str,
    alphavantage_api_key: str,
    sec_api_key: str,
    transcript_api_key: str,
    benzinga_api_key: str,
    session: AsyncSession,
) -> tuple[int | None, str | None, object]:
    """Compute the current post-regime conviction score for ``ticker``.

    Returns ``(score, tier, f7_result)`` where:
      • ``score`` is the validated post-regime conviction score
        (``RegimeModifierResponse.adjusted_score``) or ``None`` if any
        upstream input was unavailable / out of range.
      • ``tier`` is the tier string for ``score`` or ``None`` when score
        is ``None``.
      • ``f7_result`` is the F7 earnings-gate response (or the raised
        ``BaseException``) so the caller can reuse it without making a
        second F7 call.

    This helper is invoked **before** the LEAPS cache lookup so the cache
    can be score-keyed: a cached entry whose ``score`` differs from the
    current resolved score is treated as stale and re-evaluated.
    """
    # Local imports avoid circular-import risk at module load.
    from atlas.services.framework7_service import Framework7Service
    from atlas.services.regime_modifier_service import RegimeModifierService

    f7_service = Framework7Service(
        alphavantage_api_key=alphavantage_api_key,
        polygon_api_key=polygon_api_key,
        transcript_api_key=transcript_api_key,
        benzinga_api_key=benzinga_api_key,
        unusual_whales_api_key=uw_api_key,
        sec_api_key=sec_api_key,
    )

    f7_result: object
    try:
        f7_result = await f7_service.compute(ticker)
    except BaseException as exc:
        logger.warning(
            "F7 fetch failed during LEAPS score resolution",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return None, None, exc

    f7_final_score = getattr(f7_result, "final_score", None)
    if f7_final_score is None:
        return None, None, f7_result

    regime_service = RegimeModifierService(
        polygon_api_key=polygon_api_key,
        alphavantage_api_key=alphavantage_api_key,
        transcript_api_key=transcript_api_key,
        benzinga_api_key=benzinga_api_key,
        unusual_whales_api_key=uw_api_key,
        sec_api_key=sec_api_key,
        session=session,
    )
    try:
        regime_resp = await regime_service.compute_regime_modifier(
            ticker,
            geopolitical_state="NONE",
            provided_base_score=int(f7_final_score),
        )
        raw_score = getattr(regime_resp, F1_SCORE_FIELD, None)
    except Exception as exc:
        logger.warning(
            "Regime modifier fetch failed for LEAPS — score unavailable",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return None, None, f7_result

    # Defensive validation — score must be a number inside [0, 100].
    if raw_score is None:
        return None, None, f7_result
    if not isinstance(raw_score, (int, float)):
        logger.error(
            "Regime modifier returned non-numeric score",
            extra={"ticker": ticker, "value": repr(raw_score)},
        )
        return None, None, f7_result
    if not (_SCORE_MIN <= float(raw_score) <= _SCORE_MAX):
        logger.error(
            "Regime modifier returned out-of-range score",
            extra={
                "ticker": ticker,
                "value": float(raw_score),
                "expected_range": [_SCORE_MIN, _SCORE_MAX],
            },
        )
        return None, None, f7_result

    score = round(float(raw_score))
    return score, _determine_tier(score), f7_result


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def _determine_tier(score: int) -> str:
    """Map score to tier label using the canonical classify_tier() function."""
    return classify_tier(score)["tier"]


def _check_iv_block(iv_current: float | None) -> bool | None:
    """Check if IV blocks LEAPS entry.

    Returns True when IV > 90% (blocked), False when IV ≤ 90% (allowed),
    None when IV data is unavailable.
    """
    if iv_current is None:
        return None
    return iv_current > _IV_BLOCK_THRESHOLD


def _check_regime_clears_leaps(regime_state: str | None) -> bool | None:
    """Return True when regime permits LEAPS, False when it doesn't, None when unknown."""
    if regime_state is None:
        return None
    return regime_state.upper() in _LEAPS_ALLOWED_REGIMES


def _evaluate_entry_condition1(
    f29_vix_signal_confirmed: bool | None,
) -> EntryCondition:
    """Condition 1: Washout signal — VIX 5-day SMA declining (F29 Signal 1)."""
    if f29_vix_signal_confirmed is None:
        return EntryCondition(
            condition_name="Washout Signal (VIX Declining)",
            status=EntryConditionStatus.INCOMPLETE,
            met=None,
            detail="F29 VIX signal data unavailable.",
        )
    if f29_vix_signal_confirmed:
        return EntryCondition(
            condition_name="Washout Signal (VIX Declining)",
            status=EntryConditionStatus.CONFIRMED,
            met=True,
            detail="VIX 5-day SMA declining — washout/capitulation signal present.",
        )
    return EntryCondition(
        condition_name="Washout Signal (VIX Declining)",
        status=EntryConditionStatus.NOT_MET,
        met=False,
        detail="VIX 5-day SMA not yet declining — washout signal not confirmed.",
    )


def _evaluate_entry_condition2(regime_state: str | None) -> EntryCondition:
    """Condition 2: Regime is CLEAR or SOFT_CAUTION."""
    if regime_state is None:
        return EntryCondition(
            condition_name="Regime CLEAR or SOFT_CAUTION",
            status=EntryConditionStatus.INCOMPLETE,
            met=None,
            detail="Regime data unavailable.",
        )
    allowed = regime_state.upper() in _LEAPS_ALLOWED_REGIMES
    return EntryCondition(
        condition_name="Regime CLEAR or SOFT_CAUTION",
        status=EntryConditionStatus.CONFIRMED if allowed else EntryConditionStatus.NOT_MET,
        met=allowed,
        detail=f"Regime is {regime_state}.",
    )


def _evaluate_entry_condition3(
    score: int | None,
) -> EntryCondition:
    """Condition 3: Score meets LEAPS tier threshold (≥70 required)."""
    if score is None:
        return EntryCondition(
            condition_name="Score Meets LEAPS Threshold (≥70)",
            status=EntryConditionStatus.INCOMPLETE,
            met=None,
            detail="Score data unavailable.",
        )
    meets = score >= _TIER_2_SCORE_MIN
    return EntryCondition(
        condition_name="Score Meets LEAPS Threshold (≥70)",
        status=EntryConditionStatus.CONFIRMED if meets else EntryConditionStatus.NOT_MET,
        met=meets,
        detail=(
            f"Score {score} {'meets' if meets else 'does not meet'} "
            f"LEAPS minimum ({_TIER_2_SCORE_MIN})."
        ),
    )


def _compute_iv_alert(
    iv_current: float | None,
    iv_percentile: float | None,
) -> IVAlert:
    """Determine IV alert state from current IV and percentile. Pure function."""
    if iv_current is None:
        return IVAlert.DATA_UNAVAILABLE
    if iv_current > _IV_BLOCK_THRESHOLD:
        return IVAlert.IV_HIGH_ALERT
    if iv_percentile is not None and iv_percentile < 0.30:
        return IVAlert.IV_COMPRESSION_SIGNAL
    return IVAlert.NONE


def _compute_iv_catalyst_wait(
    earnings_date: date | None,
    today: date | None = None,
) -> int | None:
    """Return days remaining in the 7-day post-catalyst IV compression wait.

    Spec: "Wait 5-7 days after a major catalyst for IV compression."

    Parameters
    ----------
    earnings_date:
        Most recent earnings date (past or present).  None when unavailable.
    today:
        Reference date — injectable for testing.  Defaults to ``date.today()``.

    Returns
    -------
    int | None
        None  — no earnings date available; no wait tracked.
        0     — wait window over (> 7 days since catalyst) or catalyst in future.
        1-7   — days remaining in the wait window.
    """
    if earnings_date is None:
        return None
    _today = today or date.today()
    days_since = (_today - earnings_date).days
    if 0 <= days_since <= _IV_CATALYST_WAIT_DAYS:
        return _IV_CATALYST_WAIT_DAYS - days_since
    return 0


def _detect_price_gap(
    open_price: float | None,
    prev_close: float | None,
    *,
    threshold_pct: float = _GAP_THRESHOLD_PCT,
) -> bool | None:
    """Return True when today's open gaps from the previous close by ≥ threshold_pct.

    Spec: "Never buy LEAPS into a gap."

    Parameters
    ----------
    open_price:
        Today's official open price.
    prev_close:
        Previous session's closing price.
    threshold_pct:
        Minimum absolute % deviation that constitutes a gap (default 2%).

    Returns
    -------
    bool | None
        True  — gap detected (open differs from prev_close by ≥ threshold).
        False — no gap.
        None  — data unavailable.
    """
    if open_price is None or prev_close is None or prev_close == 0.0:
        return None
    gap_pct = abs(open_price - prev_close) / prev_close * 100.0
    return gap_pct >= threshold_pct


def _compute_eligibility(
    *,
    ticker: str,
    score: int | None,
    tier: str | None,
    flow_confirmed: bool | None,
    regime_state: str | None,
    gate_f7_active: bool | None,
    gate_f29_passed: bool | None,
    gate_f30_permits_leaps: bool | None,
    gate_f11_blocks: bool | None,
    gate_f15_blocks: bool | None,
    iv_current: float | None,
    iv_percentile: float | None,
    entry_conditions: list[EntryCondition],
    data_age_minutes: int,
    gap_detected: bool | None = None,
    iv_catalyst_wait_days_remaining: int | None = None,
    size_guidance_f33: object | None = None,
    entry_type: str | None = None,
    crisis_halt_blocked: bool = False,
) -> LeapsEligibility:
    """Compute LEAPS eligibility from all pre-fetched inputs. Pure function.

    Returns LeapsEligibility with leaps_eligible as True | False | None.

    entry_type controls two bypass behaviours:
      WASHOUT / CATALYST_VALIDATED — skip the F29 AND gate check and allow
        CAUTION regime (only CRISIS_HALT is a hard stop for these entries).
      DISCRETIONARY / None — full gate checks apply.

    crisis_halt_blocked=True is a hard stop regardless of entry_type.
    """
    iv_blocked = _check_iv_block(iv_current)
    regime_clears = _check_regime_clears_leaps(regime_state)
    iv_alert = _compute_iv_alert(iv_current, iv_percentile)

    # Whether this entry type bypasses the F29 gate and CAUTION regime check.
    _bypass_macro_gate = entry_type in ("WASHOUT", "CATALYST_VALIDATED")

    block_reasons: list[str] = []
    warning_messages: list[str] = []
    has_unknown = False

    # --- CRISIS HALT hard stop (overrides every entry type) ---
    if crisis_halt_blocked:
        block_reasons.append(
            "CRISIS HALT active — no LEAPS permitted regardless of entry type."
        )

    # --- Score availability check (Rule 6: never default to any score value) ---
    # When Framework 1 data is missing, eligibility cannot be determined.
    if score is None:
        has_unknown = True
        warning_messages.append(
            "Score unavailable — Framework 1 data missing. "
            "Cannot determine LEAPS eligibility."
        )

    # --- Hard blocks (make eligible=False immediately) ---

    if score is not None and score < _TIER_2_SCORE_MIN:
        block_reasons.append(
            f"Score {score} below LEAPS minimum ({_TIER_2_SCORE_MIN})."
        )

    if tier in ("T3", "BELOW_GATE"):
        block_reasons.append("Tier 3 / Below Gate positions are not eligible for LEAPS.")

    if gate_f7_active is True:
        block_reasons.append("F7 earnings gate active — LEAPS blocked during gate window.")
    elif gate_f7_active is None:
        has_unknown = True
        warning_messages.append("F7 gate status unknown — eligibility deferred.")

    # F29 gate only required for DISCRETIONARY entries (WASHOUT/CATALYST_VALIDATED bypass).
    if not _bypass_macro_gate:
        if gate_f29_passed is False:
            block_reasons.append(
                "F29 AND gate not passed — capitulation/re-entry conditions not met."
            )
        elif gate_f29_passed is None:
            has_unknown = True
            warning_messages.append("F29 gate status unknown — eligibility deferred.")

    if gate_f30_permits_leaps is False:
        block_reasons.append("F30 HARD_HALT — LEAPS blocked.")
    elif gate_f30_permits_leaps is None:
        has_unknown = True
        warning_messages.append("F30 drawdown state unknown — eligibility deferred.")

    if gate_f11_blocks is True:
        block_reasons.append(
            "F11 cash floor violated — all LEAPS entries blocked until cash restored."
        )
    elif gate_f11_blocks is None:
        has_unknown = True
        warning_messages.append("F11 cash floor status unknown — eligibility deferred.")

    if gate_f15_blocks is True:
        block_reasons.append(
            "F15 VIX session halt — no new LEAPS entries this session."
        )
    elif gate_f15_blocks is None:
        has_unknown = True
        warning_messages.append("F15 status unknown — blocked for safety.")

    if iv_blocked is True:
        block_reasons.append(
            f"IV {iv_current:.0%} exceeds {_IV_BLOCK_THRESHOLD:.0%} — LEAPS blocked."
        )
    elif iv_blocked is None:
        has_unknown = True
        warning_messages.append("IV data unavailable — eligibility deferred.")

    # CAUTION regime blocks DISCRETIONARY only; WASHOUT/CATALYST_VALIDATED bypass it.
    # (CRISIS_HALT is handled above as a separate hard stop.)
    if regime_clears is False:
        if not _bypass_macro_gate:
            block_reasons.append(f"Regime {regime_state} does not permit LEAPS.")
    elif regime_clears is None:
        if not _bypass_macro_gate:
            has_unknown = True
            warning_messages.append("Regime data unavailable — eligibility deferred.")

    # T1 and T2 require dark pool flow confirmation.
    if tier in ("T1", "T2"):
        if flow_confirmed is False:
            block_reasons.append(
                f"T1/T2 LEAPS requires \u2265${_TIER_2_DARK_POOL_FLOW_USD:,.0f} "
                "dark pool flow (F9). Not confirmed."
            )
        elif flow_confirmed is None:
            has_unknown = True
            warning_messages.append("F9 dark pool flow data unavailable for T1/T2 check.")

    # --- Gap-day block (spec: "Never buy LEAPS into a gap") ---
    if gap_detected is True:
        block_reasons.append(
            f"Price gap detected (≥{_GAP_THRESHOLD_PCT:.0f}% open vs. prev close) — "
            "do not enter LEAPS on a gap day."
        )
    elif gap_detected is None:
        has_unknown = True
        warning_messages.append("Gap data unavailable — price check deferred.")

    # --- Post-catalyst IV compression wait ---
    if iv_catalyst_wait_days_remaining is not None and iv_catalyst_wait_days_remaining > 0:
        block_reasons.append(
            f"Post-catalyst IV wait: {iv_catalyst_wait_days_remaining} day(s) remaining "
            f"(spec: wait {_IV_CATALYST_WAIT_DAYS} days after earnings for IV compression)."
        )

    # --- Determine overall eligibility ---
    conditions_met = sum(1 for c in entry_conditions if c.met is True)
    conditions_required = 2  # At least 2 of 3 entry conditions should be met

    if block_reasons:
        leaps_eligible: bool | None = False
        eligibility_undetermined = False
    elif has_unknown:
        leaps_eligible = None
        eligibility_undetermined = True
    else:
        # All required checks passed and no unknowns.
        leaps_eligible = True
        eligibility_undetermined = False

    # Build size guidance schema from F33 dataclass (or use default).
    from atlas.services.framework33_service import SizeGuidance

    if size_guidance_f33 is not None and isinstance(size_guidance_f33, SizeGuidance):
        size_guidance = SizeGuidanceSchema(
            standard_max_pct=size_guidance_f33.standard_max_pct,
            baseline_pct=size_guidance_f33.baseline_pct,
            baseline_max_pct=size_guidance_f33.baseline_max_pct,
            carveout_active=size_guidance_f33.carveout_active,
            data_missing=size_guidance_f33.data_missing,
        )
    else:
        size_guidance = SizeGuidanceSchema(
            standard_max_pct=1.0,
            baseline_pct=0.3,
            baseline_max_pct=0.75,
            carveout_active=False,
            data_missing=False,
        )

    return LeapsEligibility(
        ticker=ticker,
        leaps_eligible=leaps_eligible,
        eligibility_undetermined=eligibility_undetermined,
        score=score,
        tier=tier,
        flow_confirmed=flow_confirmed,
        regime_state=regime_state,
        regime_clears_leaps=regime_clears,
        gate_f7_active=gate_f7_active,
        gate_f29_passed=gate_f29_passed,
        gate_f30_permits_leaps=gate_f30_permits_leaps,
        iv_current=iv_current,
        iv_percentile=iv_percentile,
        iv_blocked=iv_blocked,
        iv_alert=iv_alert,
        iv_catalyst_wait_days_remaining=iv_catalyst_wait_days_remaining,
        gap_detected=gap_detected,
        entry_conditions=entry_conditions,
        conditions_met=conditions_met,
        conditions_required=conditions_required,
        block_reasons=block_reasons,
        warning_messages=warning_messages,
        entry_type=entry_type,
        expiry_guidance=_default_expiry_guidance(),
        size_guidance=size_guidance,
        data_age_minutes=data_age_minutes,
        cache_hit=False,
    )


# ---------------------------------------------------------------------------
# Async data fetchers
# ---------------------------------------------------------------------------


async def _fetch_iv_from_uw(
    ticker: str,
    uw_api_key: str,
    client: httpx.AsyncClient,
) -> tuple[float | None, float | None]:
    """Fetch current IV and IV percentile from Unusual Whales.

    Returns (iv_current, iv_percentile) where values are 0-1 fractions.
    Returns (None, None) on error.
    """
    if not uw_api_key:
        return None, None

    try:
        response = await client.get(
            _UW_IV_URL.format(ticker=ticker.upper()),
            headers={"Authorization": f"Bearer {uw_api_key}"},
            timeout=8.0,
        )

        if response.status_code != 200:
            logger.warning(
                "UW IV rank non-200",
                extra={"ticker": ticker, "status": response.status_code},
            )
            return None, None

        data = response.json()
        # UW returns something like {"data": {"iv_rank": 0.45, "iv": 0.32}}
        inner = data.get("data", {}) if isinstance(data, dict) else {}
        iv_current = inner.get("iv") or inner.get("iv_current")
        iv_percentile = inner.get("iv_rank") or inner.get("iv_percentile")

        return (
            float(iv_current) if iv_current is not None else None,
            float(iv_percentile) if iv_percentile is not None else None,
        )

    except Exception as exc:
        logger.warning("UW IV fetch failed", extra={"ticker": ticker, "error": repr(exc)})
        return None, None


async def _fetch_open_and_prev_close(
    ticker: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> tuple[float | None, float | None]:
    """Fetch today's open price and previous session close from Polygon snapshot.

    Used to detect gap-day entries (spec: "Never buy LEAPS into a gap").

    Returns
    -------
    (open_price, prev_close) — both None when unavailable.
    """
    if not api_key:
        return None, None
    try:
        response = await client.get(
            _POLYGON_TICKER_SNAPSHOT_URL.format(ticker=ticker.upper()),
            params={"apiKey": api_key},
            timeout=8.0,
        )
        if response.status_code != 200:
            logger.warning(
                "Polygon snapshot non-200 for gap check",
                extra={"ticker": ticker, "status": response.status_code},
            )
            return None, None
        data = response.json()
        snapshot = data.get("ticker", {})
        day = snapshot.get("day", {})
        prev_day = snapshot.get("prevDay", {})
        open_price = day.get("o")
        prev_close = prev_day.get("c")
        return (
            float(open_price) if open_price else None,
            float(prev_close) if prev_close else None,
        )
    except Exception as exc:
        logger.warning(
            "Polygon gap-check fetch failed", extra={"ticker": ticker, "error": repr(exc)}
        )
        return None, None


# ---------------------------------------------------------------------------
# Size guidance helper
# ---------------------------------------------------------------------------


def _get_f33_size_guidance(gate_f30_permits_leaps: bool | None) -> object:
    """Derive F33 SizeGuidance from F30 gate state.

    gate_f30_permits_leaps=True  → F30 permits LEAPS; no carveout
    gate_f30_permits_leaps=False → HARD_HALT; carveout applied defensively
    gate_f30_permits_leaps=None  → unknown; conservative carveout
    """
    from atlas.services.framework33_service import compute_per_name_size_pct

    if gate_f30_permits_leaps is True:
        return compute_per_name_size_pct(f30_drawdown_gate_active=False)
    if gate_f30_permits_leaps is False:
        return compute_per_name_size_pct(f30_drawdown_gate_active=True)
    return compute_per_name_size_pct(f30_drawdown_gate_active=None)


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def check_leaps_eligibility(
    ticker: str,
    session: AsyncSession,
    polygon_api_key: str = "",
    uw_api_key: str = "",
    alphavantage_api_key: str = "",
    sec_api_key: str = "",
    transcript_api_key: str = "",
    benzinga_api_key: str = "",
    provided_score: int | None = None,
) -> LeapsEligibility:
    """Evaluate LEAPS eligibility for a specific ticker.

    Orchestrates parallel data fetches from:
      - F29 AND gate (from in-memory cache or live evaluation)
      - F30 drawdown state (from in-memory cache or DB evaluation)
      - F7 earnings gate (live — requires AV API)
      - F9 dark pool flow (from in-memory cache or live evaluation)
      - Unusual Whales IV data

    Returns a LeapsEligibility with tristate leaps_eligible.
    """
    normalised = ticker.strip().upper()

    # ------------------------------------------------------------------
    # F33 excluded-ticker check (OTC / foreign / thin US options chains)
    # ------------------------------------------------------------------
    from atlas.services.framework33_service import is_excluded_ticker

    if is_excluded_ticker(normalised):
        return LeapsEligibility(
            ticker=normalised,
            leaps_eligible=False,
            eligibility_undetermined=False,
            score=None,
            tier=None,
            flow_confirmed=None,
            regime_state=None,
            regime_clears_leaps=None,
            gate_f7_active=None,
            gate_f29_passed=None,
            gate_f30_permits_leaps=None,
            iv_current=None,
            iv_percentile=None,
            iv_blocked=None,
            iv_alert=IVAlert.NONE,
            iv_catalyst_wait_days_remaining=None,
            gap_detected=None,
            entry_conditions=[],
            conditions_met=0,
            conditions_required=1,
            block_reasons=[
                f"{normalised} is excluded from LEAPS "
                "(OTC / foreign / thin US options chain — see F33)."
            ],
            warning_messages=[],
            expiry_guidance=_default_expiry_guidance(),
            data_age_minutes=0,
            cache_hit=False,
        )

    # ------------------------------------------------------------------
    # Score-keyed cache validation (Section 4.4 — Precedence of Truth).
    # ------------------------------------------------------------------
    # The LEAPS result includes the post-regime conviction score. F1's
    # score path (FrameworkScore → Regime) is uncached and tracks live
    # VIX / Brent / F4 on every call, so it can move *between* writes to
    # this cache. To prevent serving a stale score when an upstream
    # source (e.g. F4 / UW / Polygon / AV) recovers and pushes F1 to a
    # new value, we compute the *current* post-regime score first and
    # only honour a cached entry when its ``score`` field matches.
    #
    # Cost: cache hits now pay one F7 (earnings) + one regime call
    # (~500 ms). All other heavy fetches (F9, F29, F30, IV) are still
    # served from the cached result. On score change, the entry is
    # invalidated and a full re-evaluation runs.
    #
    # When the caller supplies ``provided_score`` (e.g. the F1-panel
    # score already displayed to the investor), skip the F7 + regime
    # re-fetch to avoid a 1-point rounding divergence caused by
    # independent per-factor computations in the two code paths.
    if provided_score is not None:
        current_score: int | None = provided_score
        current_tier: str | None = _determine_tier(provided_score)
        # Use a sentinel so the downstream F7-reuse logic triggers a fresh
        # fetch (the isinstance(…, BaseException) guard treats this as "not
        # pre-fetched" and calls f7_service.compute() instead of replaying).
        prefetched_f7: object = RuntimeError("score provided externally — F7 not pre-fetched")
    else:
        current_score, current_tier, prefetched_f7 = await _resolve_current_score(
            normalised,
            polygon_api_key=polygon_api_key,
            uw_api_key=uw_api_key,
            alphavantage_api_key=alphavantage_api_key,
            sec_api_key=sec_api_key,
            transcript_api_key=transcript_api_key,
            benzinga_api_key=benzinga_api_key,
            session=session,
        )

    cached, age_minutes = _cache_get(normalised)
    if (
        cached is not None
        and age_minutes <= _CACHE_TTL_SECONDS / 60.0
        and cached.score == current_score
    ):
        return LeapsEligibility(
            **{**cached.model_dump(), "cache_hit": True}
        )
    if cached is not None:
        # Either TTL expired or the conviction score moved. Drop the
        # entry so a fresh evaluation is persisted below.
        _cache_invalidate(normalised)

    # 1. Fetch F29 gate status (from cache or evaluate).
    from atlas.services.framework29_service import (
        evaluate_framework29,
    )
    from atlas.services.framework29_service import (
        get_gate_status as get_f29_gate,
    )

    f29_cached = get_f29_gate()

    # 2. Fetch F30 drawdown state (from cache or DB evaluate).
    from atlas.services.framework30_service import (
        evaluate_framework30,
    )
    from atlas.services.framework30_service import (
        get_drawdown_state as get_f30_state,
    )

    f30_cached = get_f30_state()

    # 3. Framework 7 gate (requires AV API key + ticker).
    from atlas.services.framework7_service import Framework7Service

    f7_service = Framework7Service(
        alphavantage_api_key=alphavantage_api_key,
        polygon_api_key=polygon_api_key,
        transcript_api_key=transcript_api_key,
        benzinga_api_key=benzinga_api_key,
        unusual_whales_api_key=uw_api_key,
        sec_api_key=sec_api_key,
    )

    # 4. F9 score for dark pool flow (use module cache).
    from atlas.services.framework9_service import evaluate_framework9

    # 5. Run parallel tasks where possible. F7 was already computed by
    # ``_resolve_current_score`` above; reuse it instead of refetching.
    async def _replay_f7() -> object:
        return prefetched_f7

    async with httpx.AsyncClient() as client:
        f7_task = (
            _replay_f7()
            if not isinstance(prefetched_f7, BaseException)
            else f7_service.compute(normalised)
        )
        f9_task = evaluate_framework9(normalised, uw_api_key, polygon_api_key, alphavantage_api_key)
        iv_task = _fetch_iv_from_uw(normalised, uw_api_key, client)
        gap_task = _fetch_open_and_prev_close(normalised, polygon_api_key, client)

        async def _resolved_f29() -> object:
            return f29_cached

        async def _resolved_f30() -> object:
            return f30_cached

        f29_task = (
            _resolved_f29()
            if f29_cached is not None
            else evaluate_framework29(polygon_api_key, uw_api_key)
        )
        f30_task = (
            _resolved_f30()
            if f30_cached is not None
            else evaluate_framework30(session, polygon_api_key)
        )

        results = await asyncio.gather(
            f7_task, f9_task, iv_task, gap_task, f29_task, f30_task,
            return_exceptions=True,
        )

    f7_result, f9_result, iv_result, gap_result_raw, f29_result_raw, f30_result_raw = results

    # Conviction score — already resolved (and validated) by
    # ``_resolve_current_score`` before the cache check above. This is the
    # POST-regime conviction score (RegimeModifierResponse.adjusted_score)
    # — the only score LEAPS may use.
    score = current_score
    tier = current_tier

    # Unwrap remaining gate/flow results safely.
    gate_f7_active: bool | None = None
    if not isinstance(f7_result, BaseException):
        gate_f7_active = f7_result.gate_active  # type: ignore[attr-defined]

    # --- Post-catalyst IV wait (spec: wait 7 days after earnings for IV compression) ---
    iv_catalyst_wait_days_remaining: int | None = None
    if not isinstance(f7_result, BaseException):
        earnings_dt = getattr(f7_result, "earnings_date", None)
        iv_catalyst_wait_days_remaining = _compute_iv_catalyst_wait(earnings_dt)

    # --- Gap-day detection from Polygon price snapshot ---
    gap_detected: bool | None = None
    single_session_drop_pct: float | None = None
    open_price_val: float | None = None
    prev_close_val: float | None = None
    if not isinstance(gap_result_raw, BaseException):
        open_price_val, prev_close_val = gap_result_raw
        gap_detected = _detect_price_gap(open_price_val, prev_close_val)
        if (
            open_price_val is not None
            and prev_close_val is not None
            and prev_close_val > 0
            and open_price_val < prev_close_val
        ):
            single_session_drop_pct = (prev_close_val - open_price_val) / prev_close_val

    # --- Dark pool flow from F9 (Tier 2 confirmation only) ---
    # F9 is used exclusively for the $500K dark pool flow check.
    # F9 f4_score is NOT the conviction score — do not use it here.
    flow_confirmed: bool | None = None
    f4_score_val: float | None = None

    if not isinstance(f9_result, BaseException):
        dp_usd = f9_result.largest_print_usd
        if dp_usd is not None:
            flow_confirmed = float(dp_usd) >= _TIER_2_DARK_POOL_FLOW_USD
        f4_score_val = getattr(f9_result, "f4_score", None)

    iv_current: float | None = None
    iv_percentile: float | None = None
    if not isinstance(iv_result, BaseException):
        iv_current, iv_percentile = iv_result

    gate_f29_passed: bool | None = None
    f29_vix_signal: bool | None = None
    crisis_halt_blocked: bool = False
    if not isinstance(f29_result_raw, BaseException) and f29_result_raw is not None:
        gate_f29_passed = f29_result_raw.and_gate_passed  # type: ignore[attr-defined]
        crisis_halt_blocked = bool(getattr(f29_result_raw, "crisis_halt_blocked", False))
        # Extract Signal 1 (VIX declining) status for entry condition 1.
        signals = getattr(f29_result_raw, "signals", [])
        if signals:
            sig1 = next((s for s in signals if s.signal_number == 1), None)
            if sig1:
                from atlas.schemas.framework29 import SignalStatus
                f29_vix_signal = sig1.status == SignalStatus.CONFIRMED

    gate_f30_permits_leaps: bool | None = None
    regime_state: str | None = None
    if not isinstance(f30_result_raw, BaseException) and f30_result_raw is not None:
        gate_f30_permits_leaps = getattr(f30_result_raw, "leaps_permitted", None)

    # Regime state: derive from F30 drawdown (best we can without a separate F2 call).
    # For LEAPS, we use F29 gate as a proxy for regime health when F2 is not called.
    if gate_f29_passed is True and (
        gate_f30_permits_leaps is True or gate_f30_permits_leaps is None
    ):
        regime_state = "CLEAR"
    elif gate_f29_passed is False:
        regime_state = "CAUTION"
    else:
        regime_state = None

    # Build entry conditions using F33 (Condition A + Condition B + Condition C).
    from atlas.services.framework33_service import (
        evaluate_condition_a,
        evaluate_condition_b,
        evaluate_condition_c,
    )

    # F33 inputs — all come from upstream data already fetched above.
    # drawdown_from_high_pct: not yet fetched in this service; pass None
    # (will show INCOMPLETE).  Callers that have drawdown data can extend
    # this path.  VIX current is sourced from the F29 signals.
    f29_vix_current: float | None = None
    f29_drawdown: float | None = None
    if not isinstance(f29_result_raw, BaseException) and f29_result_raw is not None:
        for _sig in getattr(f29_result_raw, "signals", []):
            if getattr(_sig, "signal_number", None) == 1:
                f29_vix_current = getattr(_sig, "value", None)
                break

    cond_a = evaluate_condition_a(
        drawdown_from_high_pct=f29_drawdown,
        vix_current=f29_vix_current,
    )
    cond_b = evaluate_condition_b(
        sector_drawdown_pct=None,
        capitulation_volume_confirmed=(
            f29_vix_signal if f29_vix_signal is not None else None
        ),
        vix_elevated=(
            True if (f29_vix_current is not None and f29_vix_current > 20.0) else
            (False if f29_vix_current is not None else None)
        ),
        vix_declining_from_peak=f29_vix_signal,
    )
    cond_c = evaluate_condition_c(
        t1e_score=score,
        dark_pool_bullish=flow_confirmed,
        options_flow_bullish=None,  # not yet sourced separately
        no_gap_day=(None if gap_detected is None else not gap_detected),
    )

    def _entry_condition_from_f33(
        label: str, confirmed: bool | None, detail: str
    ) -> EntryCondition:
        if confirmed is True:
            status = EntryConditionStatus.CONFIRMED
        elif confirmed is False:
            status = EntryConditionStatus.NOT_MET
        else:
            status = EntryConditionStatus.INCOMPLETE
        return EntryCondition(
            condition_name=label, status=status, met=confirmed, detail=detail
        )

    entry_conditions = [
        _entry_condition_from_f33(
            "F33 Condition A — Calm Accumulation",
            cond_a.confirmed,
            cond_a.detail,
        ),
        _entry_condition_from_f33(
            "F33 Condition B — Washout",
            cond_b.confirmed,
            cond_b.detail,
        ),
        _entry_condition_from_f33(
            "F33 Condition C — Bull Market Path",
            cond_c.confirmed,
            cond_c.detail,
        ),
    ]

    # Framework 11 — Cash Floor Gate (read-only from F11 cache).
    from atlas.services.framework11_service import get_f11_simple

    f11_simple = get_f11_simple()
    gate_f11_blocks: bool | None
    if f11_simple is None:
        # F11 not yet evaluated — treat as unknown (don't block on missing cache).
        gate_f11_blocks = None
    elif f11_simple.all_buys_blocked:
        gate_f11_blocks = True
    else:
        gate_f11_blocks = False

    # Framework 15 — VIX Regime Override gate.
    from atlas.services.framework15_service import get_f15_simple

    f15_simple = get_f15_simple()
    gate_f15_blocks: bool | None
    if f15_simple is None:
        gate_f15_blocks = None
    elif f15_simple.new_market_orders_blocked:
        gate_f15_blocks = True
    else:
        gate_f15_blocks = False

    # --- Entry type classification (F29 bypass logic) ---
    # position_held: requires a DB check; stubbed False until Section 17 DB query
    # is added. WASHOUT path is fully functional; CATALYST_VALIDATED requires a
    # future DB lookup to confirm the position exists.
    entry_type = _determine_entry_type(
        single_session_drop_pct=single_session_drop_pct,
        f4_score=f4_score_val,
        position_held=False,  # TODO(#leaps-position-held): query DB for open position
        score=score,
    )

    result = _compute_eligibility(
        ticker=normalised,
        score=score,
        tier=tier,
        flow_confirmed=flow_confirmed,
        regime_state=regime_state,
        gate_f7_active=gate_f7_active,
        gate_f29_passed=gate_f29_passed,
        gate_f30_permits_leaps=gate_f30_permits_leaps,
        gate_f11_blocks=gate_f11_blocks,
        gate_f15_blocks=gate_f15_blocks,
        iv_current=iv_current,
        iv_percentile=iv_percentile,
        entry_conditions=entry_conditions,
        data_age_minutes=0,
        gap_detected=gap_detected,
        iv_catalyst_wait_days_remaining=iv_catalyst_wait_days_remaining,
        size_guidance_f33=_get_f33_size_guidance(gate_f30_permits_leaps),
        entry_type=entry_type,
        crisis_halt_blocked=crisis_halt_blocked,
    )

    _cache_set(normalised, result)
    return result


# ---------------------------------------------------------------------------
# Position and bucket queries
# ---------------------------------------------------------------------------


async def get_leaps_positions(session: AsyncSession) -> list[LeapsPositionSchema]:
    """Return all open LEAPS positions from the DB.

    V1: positions have no live price enrichment — prices are null.
    """
    result = await session.execute(
        select(LeapsPosition).where(LeapsPosition.status == "OPEN")
    )
    positions = list(result.scalars().all())

    return [
        LeapsPositionSchema(
            id=p.id,
            ticker=p.ticker,
            option_symbol=p.option_symbol,
            expiration_date=p.expiration_date.isoformat(),
            strike_price=float(p.strike_price),
            option_type=p.option_type,
            contracts=p.contracts,
            entry_price=float(p.entry_price),
            current_price=None,
            current_value=None,
            theta_daily=None,
            iv_at_entry=float(p.iv_at_entry) if p.iv_at_entry else None,
            iv_current=None,
            pnl_usd=None,
            pnl_pct=None,
            days_to_expiry=(p.expiration_date - date.today()).days,
            status=p.status,
            notes=p.notes,
        )
        for p in positions
    ]


async def get_leaps_bucket(
    session: AsyncSession,
    current_nav: float | None = None,
) -> LeapsBucketStatus:
    """Return the current LEAPS bucket utilisation.

    V1: positions have no live prices, so deployed_usd uses entry_price.
    """
    result = await session.execute(
        select(LeapsPosition).where(LeapsPosition.status == "OPEN")
    )
    positions = list(result.scalars().all())

    # Total cost basis (entry_price * contracts * 100).
    _shares_per_contract: Final[int] = 100
    total_deployed_usd = sum(
        float(p.entry_price) * p.contracts * _shares_per_contract for p in positions
    )

    total_deployed_pct = 0.0
    bucket_available_usd: float | None = None

    if current_nav and current_nav > 0:
        total_deployed_pct = total_deployed_usd / current_nav * 100.0
        bucket_available_usd = max(
            0.0, (_LEAPS_BUCKET_CAP_PCT / 100.0 - total_deployed_usd / current_nav) * current_nav
        )

    bucket_available_pct = max(0.0, _LEAPS_BUCKET_CAP_PCT - total_deployed_pct)

    warning_messages: list[str] = []
    if total_deployed_pct > _LEAPS_BUCKET_CAP_PCT:
        warning_messages.append(
            f"LEAPS bucket at {total_deployed_pct:.1f}% NAV — exceeds {_LEAPS_BUCKET_CAP_PCT}% cap."
        )

    return LeapsBucketStatus(
        total_deployed_usd=round(total_deployed_usd, 2),
        total_deployed_pct=round(total_deployed_pct, 4),
        total_cap_pct=_LEAPS_BUCKET_CAP_PCT,
        positions_count=len(positions),
        bucket_available_pct=round(bucket_available_pct, 4),
        bucket_available_usd=(
            round(bucket_available_usd, 2) if bucket_available_usd is not None else None
        ),
        warning_messages=warning_messages,
    )
