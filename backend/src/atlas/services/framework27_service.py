"""Framework 27 — Supply Chain Contagion Map service.

Evaluates active contagion rules from the framework27_contagion_map table
against current conditions (F17 flag, Brent price, conflict duration,
operator manual flags).

Data sources (single source of truth rules):
  framework27_contagion_map DB  — ONLY source for contagion rules and tickers.
  manual_contagion_flags DB     — ONLY source for operator-flagged disruptions.
  Framework 17 service          — ONLY source for geo flag and Brent price.

NEVER hardcode ticker names, trigger types, or thresholds in this service.
All values come from DB rows or Framework 17 results.

Cache: module-level dict, 300-second TTL (5 minutes).

Trigger type evaluation logic:
  HORMUZ_CLOSURE_DAYS         — conflict_duration_days >= trigger_threshold
                                 AND conflict_duration_days >= trigger_duration_days
  ASIA_FREIGHT_DISRUPTION_PCT — operator manual flag in manual_contagion_flags
  OIL_PRICE_SUSTAINED_DAYS    — Brent > trigger_threshold
                                 AND conflict_duration_days >= trigger_duration_days
  DISRUPTION_DURATION_DAYS    — conflict_duration_days >= trigger_threshold
  METALS_DISRUPTION           — operator manual flag in manual_contagion_flags
  INDIUM_SUPPLY_DISRUPTION    — operator manual flag in manual_contagion_flags
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.framework27_contagion_map import Framework27ContagionMap
from atlas.models.manual_contagion_flag import ManualContagionFlag
from atlas.schemas.framework17 import Framework17Result
from atlas.schemas.framework27 import ContagionRuleResult, Framework27Result

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cache TTL: 300 seconds (5 minutes) — contagion triggers change slowly.
_CACHE_TTL_SECONDS: Final[int] = 300

# Module-level result cache.
_CACHE_KEY: Final[str] = "f27_result"

# Cache: key → (Framework27Result, expiry_monotonic)
_cache: dict[str, tuple[Framework27Result, float]] = {}

# Operator-confirmed trigger types (require manual_contagion_flags row).
# Comes from DB column values, not hardcoded logic.
_OPERATOR_FLAG_TRIGGER_TYPES: Final[frozenset[str]] = frozenset(
    {
        "ASIA_FREIGHT_DISRUPTION_PCT",
        "METALS_DISRUPTION",
        "INDIUM_SUPPLY_DISRUPTION",
    }
)

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> Framework27Result | None:
    """Return cached result if not expired, else None."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _cache[_CACHE_KEY]
        return None
    return result


def _cache_set(result: Framework27Result) -> None:
    """Store result with TTL expiry."""
    _cache[_CACHE_KEY] = (result, time.monotonic() + _CACHE_TTL_SECONDS)


def cache_invalidate() -> None:
    """Invalidate the F27 result cache."""
    _cache.pop(_CACHE_KEY, None)


# ---------------------------------------------------------------------------
# DB readers
# ---------------------------------------------------------------------------


async def _fetch_contagion_rules(
    session: AsyncSession,
) -> list[Framework27ContagionMap]:
    """Fetch all active contagion rules from DB.

    Returns list of Framework27ContagionMap rows, ordered by id.
    Empty list on error.
    """
    try:
        stmt = (
            select(Framework27ContagionMap)
            .where(Framework27ContagionMap.active.is_(True))
            .order_by(Framework27ContagionMap.id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as exc:
        logger.error("F27: failed to fetch contagion rules", extra={"error": repr(exc)})
        return []


async def _fetch_manual_flags(session: AsyncSession) -> dict[str, bool]:
    """Fetch operator-confirmed manual flags for today's session.

    Returns a dict mapping trigger_type → bool (True if flagged and active).
    Carries forward most recent flag if none set today.
    """
    today = date.today()

    # Build a dict to check each operator trigger type.
    flagged: dict[str, bool] = {}
    for trigger_type in _OPERATOR_FLAG_TRIGGER_TYPES:
        # Try today first.
        stmt_today = (
            select(ManualContagionFlag)
            .where(
                ManualContagionFlag.trigger_type == trigger_type,
                ManualContagionFlag.session_date == today,
                ManualContagionFlag.active.is_(True),
            )
            .order_by(ManualContagionFlag.flagged_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt_today)).scalars().first()
        if row is not None:
            flagged[trigger_type] = True
            continue

        # Carry forward: most recent historical flag.
        stmt_hist = (
            select(ManualContagionFlag)
            .where(
                ManualContagionFlag.trigger_type == trigger_type,
                ManualContagionFlag.active.is_(True),
            )
            .order_by(
                ManualContagionFlag.session_date.desc(),
                ManualContagionFlag.flagged_at.desc(),
            )
            .limit(1)
        )
        row_hist = (await session.execute(stmt_hist)).scalars().first()
        flagged[trigger_type] = row_hist is not None

    return flagged


# ---------------------------------------------------------------------------
# Trigger evaluation (pure logic)
# ---------------------------------------------------------------------------


def _evaluate_rule(
    rule: Framework27ContagionMap,
    f17_active: bool | None,
    brent_price: float | None,
    conflict_duration_days: int | None,
    manual_flags: dict[str, bool],
) -> tuple[bool, str]:
    """Evaluate a single contagion rule against current conditions.

    Pure logic — no I/O.

    Returns:
        (triggered: bool, reason: str)
    """
    if f17_active is not True:
        return False, "F17 not active — contagion rules dormant."

    trigger_type = rule.contagion_trigger_type

    # Operator-confirmed trigger types.
    if trigger_type in _OPERATOR_FLAG_TRIGGER_TYPES:
        is_flagged = manual_flags.get(trigger_type, False)
        if is_flagged:
            return True, f"Operator has confirmed {trigger_type} disruption."
        return False, f"No operator confirmation for {trigger_type}."

    # Numeric threshold trigger types.
    threshold = float(rule.trigger_threshold) if rule.trigger_threshold is not None else None
    duration_req = rule.trigger_duration_days

    if trigger_type == "HORMUZ_CLOSURE_DAYS":
        if conflict_duration_days is None:
            return False, "No conflict start date — cannot evaluate HORMUZ_CLOSURE_DAYS."
        if threshold is not None and conflict_duration_days >= int(threshold):
            if duration_req is None or conflict_duration_days >= duration_req:
                return (
                    True,
                    f"Conflict duration {conflict_duration_days}d >= "
                    f"threshold {int(threshold)}d.",
                )
        return (
            False,
            f"Conflict duration {conflict_duration_days}d below "
            f"threshold {threshold}d.",
        )

    if trigger_type == "OIL_PRICE_SUSTAINED_DAYS":
        if brent_price is None:
            return False, "Brent price unavailable — cannot evaluate OIL_PRICE_SUSTAINED_DAYS."
        if threshold is None:
            return False, "No threshold configured for OIL_PRICE_SUSTAINED_DAYS."
        brent_above = brent_price > threshold
        duration_met = (
            duration_req is None
            or conflict_duration_days is not None
            and conflict_duration_days >= duration_req
        )
        if brent_above and duration_met:
            return (
                True,
                f"Brent ${brent_price:.2f} > ${threshold:.2f} threshold "
                f"with conflict {conflict_duration_days}d >= {duration_req}d.",
            )
        if not brent_above:
            return False, f"Brent ${brent_price:.2f} <= ${threshold:.2f} threshold."
        return False, f"Conflict duration {conflict_duration_days}d < required {duration_req}d."

    if trigger_type == "DISRUPTION_DURATION_DAYS":
        if conflict_duration_days is None:
            return False, "No conflict start date — cannot evaluate DISRUPTION_DURATION_DAYS."
        if threshold is not None and conflict_duration_days >= int(threshold):
            return (
                True,
                f"Disruption duration {conflict_duration_days}d >= "
                f"threshold {int(threshold)}d.",
            )
        return (
            False,
            f"Disruption duration {conflict_duration_days}d below "
            f"threshold {threshold}d.",
        )

    return False, f"Unknown trigger type: {trigger_type}"


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


async def evaluate_framework27(
    f17_result: Framework17Result,
    session: AsyncSession,
) -> Framework27Result:
    """Evaluate all active contagion rules against current F17 state.

    Uses F17 result for Brent price and conflict duration.
    Reads contagion rules and manual flags from DB.
    Never hardcodes ticker names or thresholds.

    Returns Framework27Result and writes to cache.
    """
    cached = _cache_get()
    if cached is not None:
        return Framework27Result(**{**cached.model_dump(), "cache_hit": True})

    # Fetch rules and manual flags concurrently.
    import asyncio

    rules, manual_flags = await asyncio.gather(
        _fetch_contagion_rules(session),
        _fetch_manual_flags(session),
        return_exceptions=True,
    )

    if isinstance(rules, Exception):
        logger.error("F27: contagion rules fetch failed", extra={"error": repr(rules)})
        rules = []

    if isinstance(manual_flags, Exception):
        logger.error("F27: manual flags fetch failed", extra={"error": repr(manual_flags)})
        manual_flags = {}

    # Evaluate each rule.
    all_rule_results: list[ContagionRuleResult] = []
    triggered_results: list[ContagionRuleResult] = []

    for rule in rules:
        triggered, reason = _evaluate_rule(
            rule=rule,
            f17_active=f17_result.f17_active,
            brent_price=f17_result.brent_price,
            conflict_duration_days=f17_result.conflict_duration_days,
            manual_flags=manual_flags,
        )
        rule_result = ContagionRuleResult(
            rule_id=rule.id,
            ticker=rule.ticker,
            primary_risk=rule.primary_risk,
            secondary_exposure=rule.secondary_exposure,
            contagion_trigger_type=rule.contagion_trigger_type,
            trigger_condition=rule.trigger_condition,
            triggered=triggered,
            trigger_reason=reason,
            action_on_trigger=rule.action_on_trigger,
        )
        all_rule_results.append(rule_result)
        if triggered:
            triggered_results.append(rule_result)

    result = Framework27Result(
        f17_active=f17_result.f17_active,
        rules_evaluated=len(all_rule_results),
        rules_triggered=len(triggered_results),
        triggered_rules=triggered_results,
        all_rules=all_rule_results,
        asia_freight_flagged=bool(manual_flags.get("ASIA_FREIGHT_DISRUPTION_PCT")),
        metals_disruption_flagged=bool(manual_flags.get("METALS_DISRUPTION")),
        indium_disruption_flagged=bool(manual_flags.get("INDIUM_SUPPLY_DISRUPTION")),
        brent_price=f17_result.brent_price,
        conflict_duration_days=f17_result.conflict_duration_days,
        cache_hit=False,
        data_as_of=datetime.now(timezone.utc),
    )

    _cache_set(result)
    return result
