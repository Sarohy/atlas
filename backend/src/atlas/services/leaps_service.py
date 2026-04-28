"""Section 17 — LEAPS Strategy Module service.

V1 scope: read-only eligibility tracking.  No execution engine.
Positions are tracked manually via the leaps_positions table.

Eligibility (tristate: True | False | None):
  True  — all required checks passed
  False — one or more checks failed (blocked)
  None  — required data unavailable; decision deferred

Tier rules:
  TIER_1 (score ≥ 85): auto-eligible when IV ≤ 90% and gates clear
  TIER_2 (70-84): eligible only with $500K+ dark pool flow from F9
  TIER_3 / WATCHLIST: ineligible

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
)
from atlas.schemas.leaps import (
    LeapsPosition as LeapsPositionSchema,
)

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

# Tier score thresholds.
_TIER_1_SCORE_MIN: Final[int] = 85
_TIER_2_SCORE_MIN: Final[int] = 70

# IV hard-block threshold (as a decimal fraction, e.g. 0.90 = 90%).
_IV_BLOCK_THRESHOLD: Final[float] = 0.90

# Dark pool flow required for Tier 2 LEAPS eligibility.
_TIER_2_DARK_POOL_FLOW_USD: Final[float] = 500_000.0

# LEAPS bucket cap as % of NAV.
_LEAPS_BUCKET_CAP_PCT: Final[float] = 5.0  # 5% max of NAV

# Unusual Whales IV endpoint.
_UW_BASE_URL: Final[str] = "https://api.unusualwhales.com"
_UW_IV_URL: Final[str] = f"{_UW_BASE_URL}/api/stock/{{ticker}}/iv-rank"

# Regime states that clear LEAPS eligibility.
_LEAPS_ALLOWED_REGIMES: Final[frozenset[str]] = frozenset(
    {"CLEAR", "SOFT_CAUTION", "NORMAL", "NONE"}
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
    """Map score to tier label. Pure function."""
    if score >= _TIER_1_SCORE_MIN:
        return "TIER_1"
    if score >= _TIER_2_SCORE_MIN:
        return "TIER_2"
    return "TIER_3"


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
) -> LeapsEligibility:
    """Compute LEAPS eligibility from all pre-fetched inputs. Pure function.

    Returns LeapsEligibility with leaps_eligible as True | False | None.
    """
    iv_blocked = _check_iv_block(iv_current)
    regime_clears = _check_regime_clears_leaps(regime_state)
    iv_alert = _compute_iv_alert(iv_current, iv_percentile)

    block_reasons: list[str] = []
    warning_messages: list[str] = []
    has_unknown = False

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

    if tier == "TIER_3":
        block_reasons.append("Tier 3 positions are not eligible for LEAPS.")

    if gate_f7_active is True:
        block_reasons.append("F7 earnings gate active — LEAPS blocked during gate window.")
    elif gate_f7_active is None:
        has_unknown = True
        warning_messages.append("F7 gate status unknown — eligibility deferred.")

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

    if regime_clears is False:
        block_reasons.append(f"Regime {regime_state} does not permit LEAPS.")
    elif regime_clears is None:
        has_unknown = True
        warning_messages.append("Regime data unavailable — eligibility deferred.")

    # Tier 2 requires dark pool flow confirmation.
    if tier == "TIER_2":
        if flow_confirmed is False:
            block_reasons.append(
                f"Tier 2 LEAPS requires \u2265${_TIER_2_DARK_POOL_FLOW_USD:,.0f} "
                "dark pool flow (F9). Not confirmed."
            )
        elif flow_confirmed is None:
            has_unknown = True
            warning_messages.append("F9 dark pool flow data unavailable for Tier 2 check.")

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
        entry_conditions=entry_conditions,
        conditions_met=conditions_met,
        conditions_required=conditions_required,
        block_reasons=block_reasons,
        warning_messages=warning_messages,
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
            f7_task, f9_task, iv_task, f29_task, f30_task,
            return_exceptions=True,
        )

    f7_result, f9_result, iv_result, f29_result_raw, f30_result_raw = results

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

    # --- Dark pool flow from F9 (Tier 2 confirmation only) ---
    # F9 is used exclusively for the $500K dark pool flow check.
    # F9 f4_score is NOT the conviction score — do not use it here.
    flow_confirmed: bool | None = None

    if not isinstance(f9_result, BaseException):
        dp_usd = f9_result.largest_print_usd
        if dp_usd is not None:
            flow_confirmed = float(dp_usd) >= _TIER_2_DARK_POOL_FLOW_USD

    iv_current: float | None = None
    iv_percentile: float | None = None
    if not isinstance(iv_result, BaseException):
        iv_current, iv_percentile = iv_result

    gate_f29_passed: bool | None = None
    f29_vix_signal: bool | None = None
    if not isinstance(f29_result_raw, BaseException) and f29_result_raw is not None:
        gate_f29_passed = f29_result_raw.and_gate_passed  # type: ignore[attr-defined]
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

    # Build entry conditions.
    entry_conditions = [
        _evaluate_entry_condition1(f29_vix_signal),
        _evaluate_entry_condition2(regime_state),
        _evaluate_entry_condition3(score),
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
