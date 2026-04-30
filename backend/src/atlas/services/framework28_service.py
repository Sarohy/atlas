"""Framework 28 — War Duration Ladder service.

Matches current conflict duration and Brent price against tiered portfolio
guidance stored in the framework28_ladder_tiers table.

Data sources (single source of truth rules):
  framework28_ladder_tiers DB  — ONLY source for tier thresholds and actions.
  Framework 17 service         — ONLY source for conflict duration and Brent price.

NEVER hardcode duration thresholds, Brent price ranges, or portfolio actions.
All values come from framework28_ladder_tiers DB rows.

Cache: module-level dict, 300-second TTL (5 minutes).

Tier matching:
  Find active tier where:
    duration_min_days <= conflict_duration_days
    AND (duration_max_days IS NULL OR conflict_duration_days <= duration_max_days)
    AND brent_range_low <= brent_price
    AND (brent_range_high IS NULL OR brent_price <= brent_range_high)
  When multiple tiers match, use the one with the highest tier_order (most severe).
  When no tier matches (e.g. Brent out of range), return no_match_reason.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.framework28_ladder_tier import Framework28LadderTier
from atlas.schemas.framework17 import Framework17Result
from atlas.schemas.framework28 import Framework28Result, LadderTierResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cache TTL: 300 seconds (5 minutes).
_CACHE_TTL_SECONDS: Final[int] = 300

# Module-level result cache.
_CACHE_KEY: Final[str] = "f28_result"

# Cache: key → (Framework28Result, expiry_monotonic)
_cache: dict[str, tuple[Framework28Result, float]] = {}

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> Framework28Result | None:
    """Return cached result if not expired, else None."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _cache[_CACHE_KEY]
        return None
    return result


def _cache_set(result: Framework28Result) -> None:
    """Store result with TTL expiry."""
    _cache[_CACHE_KEY] = (result, time.monotonic() + _CACHE_TTL_SECONDS)


def cache_invalidate() -> None:
    """Invalidate the F28 result cache."""
    _cache.pop(_CACHE_KEY, None)


# ---------------------------------------------------------------------------
# DB reader
# ---------------------------------------------------------------------------


async def _fetch_ladder_tiers(session: AsyncSession) -> list[Framework28LadderTier]:
    """Fetch all active ladder tiers ordered by tier_order ascending.

    Returns list of Framework28LadderTier rows. Empty list on error.
    """
    try:
        stmt = (
            select(Framework28LadderTier)
            .where(Framework28LadderTier.active.is_(True))
            .order_by(Framework28LadderTier.tier_order)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as exc:
        logger.error("F28: failed to fetch ladder tiers", extra={"error": repr(exc)})
        return []


# ---------------------------------------------------------------------------
# Tier matching (pure logic)
# ---------------------------------------------------------------------------


def _match_tier(
    tier: Framework28LadderTier,
    conflict_duration_days: int,
    brent_price: float,
) -> bool:
    """Return True if the tier matches the current conflict and Brent price.

    Pure function — no I/O.

    Matching rules (all conditions must be satisfied):
      1. duration_min_days <= conflict_duration_days
      2. duration_max_days is None OR conflict_duration_days <= duration_max_days
      3. brent_range_low <= brent_price
      4. brent_range_high is None OR brent_price <= brent_range_high
    """
    if conflict_duration_days < tier.duration_min_days:
        return False

    if (
        tier.duration_max_days is not None
        and conflict_duration_days > tier.duration_max_days
    ):
        return False

    brent_low = float(tier.brent_range_low)
    if brent_price < brent_low:
        return False

    if tier.brent_range_high is not None:
        brent_high = float(tier.brent_range_high)
        if brent_price > brent_high:
            return False

    return True


def _tier_to_result(tier: Framework28LadderTier) -> LadderTierResult:
    """Convert an ORM tier row to a Pydantic result schema.

    Pure function — no I/O.
    """
    return LadderTierResult(
        tier_order=tier.tier_order,
        duration_min_days=tier.duration_min_days,
        duration_max_days=tier.duration_max_days,
        brent_range_low=float(tier.brent_range_low),
        brent_range_high=(
            float(tier.brent_range_high) if tier.brent_range_high is not None else None
        ),
        fed_implication=tier.fed_implication,
        portfolio_action=tier.portfolio_action,
    )


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


async def evaluate_framework28(
    f17_result: Framework17Result,
    session: AsyncSession,
) -> Framework28Result:
    """Evaluate the war duration ladder against current F17 state.

    Uses F17 result for conflict duration and Brent price.
    Reads all tier thresholds and portfolio actions from DB.
    Never hardcodes tier values.

    Returns Framework28Result and writes to cache.
    """
    cached = _cache_get()
    if cached is not None:
        return Framework28Result(**{**cached.model_dump(), "cache_hit": True})

    tiers = await _fetch_ladder_tiers(session)

    all_tier_results = [_tier_to_result(t) for t in tiers]

    # Ladder is only active when F17 is active.
    if f17_result.f17_active is not True:
        result = Framework28Result(
            f17_active=f17_result.f17_active,
            conflict_duration_days=f17_result.conflict_duration_days,
            brent_price=f17_result.brent_price,
            active_tier=None,
            all_tiers=all_tier_results,
            ladder_active=False,
            no_match_reason=(
                "Ladder inactive: F17 flag is not ACTIVE."
                if f17_result.f17_active is False
                else "Ladder inactive: F17 flag has never been set (NOT_SET)."
            ),
            cache_hit=False,
            data_as_of=datetime.now(timezone.utc),
        )
        _cache_set(result)
        return result

    # F17 is active — attempt tier match.
    conflict_duration_days = f17_result.conflict_duration_days
    brent_price = f17_result.brent_price

    if conflict_duration_days is None:
        result = Framework28Result(
            f17_active=True,
            conflict_duration_days=None,
            brent_price=brent_price,
            active_tier=None,
            all_tiers=all_tier_results,
            ladder_active=False,
            no_match_reason=(
                "Cannot match tier: conflict_start_date not provided by operator."
            ),
            cache_hit=False,
            data_as_of=datetime.now(timezone.utc),
        )
        _cache_set(result)
        return result

    if brent_price is None:
        result = Framework28Result(
            f17_active=True,
            conflict_duration_days=conflict_duration_days,
            brent_price=None,
            active_tier=None,
            all_tiers=all_tier_results,
            ladder_active=False,
            no_match_reason="Cannot match tier: Brent price unavailable from Polygon.io.",
            cache_hit=False,
            data_as_of=datetime.now(timezone.utc),
        )
        _cache_set(result)
        return result

    # Find all matching tiers, select the highest severity (highest tier_order).
    matched_tiers = [
        t
        for t in tiers
        if _match_tier(t, conflict_duration_days, brent_price)
    ]

    if not matched_tiers:
        result = Framework28Result(
            f17_active=True,
            conflict_duration_days=conflict_duration_days,
            brent_price=brent_price,
            active_tier=None,
            all_tiers=all_tier_results,
            ladder_active=False,
            no_match_reason=(
                f"No tier matches: duration={conflict_duration_days}d, "
                f"Brent=${brent_price:.2f}. "
                "Check that Brent is within a tier's brent_range."
            ),
            cache_hit=False,
            data_as_of=datetime.now(timezone.utc),
        )
        _cache_set(result)
        return result

    # Use the most severe matching tier.
    best_tier = max(matched_tiers, key=lambda t: t.tier_order)

    result = Framework28Result(
        f17_active=True,
        conflict_duration_days=conflict_duration_days,
        brent_price=brent_price,
        active_tier=_tier_to_result(best_tier),
        all_tiers=all_tier_results,
        ladder_active=True,
        no_match_reason=None,
        cache_hit=False,
        data_as_of=datetime.now(timezone.utc),
    )
    _cache_set(result)
    return result
