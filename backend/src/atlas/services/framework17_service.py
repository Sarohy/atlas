"""Framework 17 — Geopolitical Monitor service.

Single source of truth for geopolitical flag state and its downstream effects.

Data sources (single source of truth rules):
  geopolitical_flag DB  — ONLY source for operator-set flag state.
  Framework 2 endpoint  — ONLY source for current market regime.
  Polygon.io            — ONLY source for Brent crude price (ticker: BZ).
  atlas_config DB       — ONLY source for display thresholds.

Carry-forward logic:
  1. Query geopolitical_flag WHERE session_date = today ORDER BY set_at DESC LIMIT 1
  2. If no row: query ORDER BY session_date DESC LIMIT 1 (carry forward)
  3. If still no row: return NOT_SET with f17_active = None
  4. NOT_SET is NEVER auto-resolved; only the operator can set a flag.

Cache: module-level dict, 60-second TTL (geo flag can change anytime intraday).

Consuming frameworks:
  Framework 2  — reads get_f17_clear_blocked() to prevent CLEAR when ACTIVE.
  Framework 3  — reads get_f17_simple() for oil_priority_elevated flag.
  Framework 7  — reads get_f17_simple() for oil_priority_elevated flag.
  Framework 27 — receives Framework17Result directly from evaluate_framework17().
  Framework 28 — receives Framework17Result directly from evaluate_framework17().
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Final

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.models.decision_trace import DecisionTrace
from atlas.models.geopolitical_flag import GeopoliticalFlag
from atlas.schemas.framework17 import (
    F17Severity,
    Framework17Result,
    Framework17SimpleResult,
    GeoFlagState,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — all spec values named, never hardcoded inline
# ---------------------------------------------------------------------------

# Cache TTL: 60 seconds — geo flag can change anytime intraday.
_CACHE_TTL_SECONDS: Final[int] = 60

# Module-level result cache: single portfolio-level entry.
_CACHE_KEY: Final[str] = "f17_result"

# Cache: key → (Framework17Result, expiry_monotonic)
_cache: dict[str, tuple[Framework17Result, float]] = {}

# Framework 2 regime endpoint path (same process — localhost call).
_F2_REGIME_PATH: Final[str] = "/api/v1/regime-modifier/regime"

# Polygon.io Brent crude daily aggs endpoint template.
# Ticker BZ = Brent Crude front-month futures (daily).
_POLYGON_BRENT_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/BZ/range/1/day/{date}/{date}"
)

# Regime labels that indicate CRISIS or CAUTION (F17 severity → CRITICAL).
_CRITICAL_REGIMES: Final[frozenset[str]] = frozenset({"CRISIS HALT", "CAUTION"})

# Regime labels that indicate SOFT_CAUTION (F17 severity → HIGH).
_HIGH_REGIMES: Final[frozenset[str]] = frozenset({"SOFT CAUTION"})

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> Framework17Result | None:
    """Return cached result if not expired, else None."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _cache[_CACHE_KEY]
        return None
    return result


def _cache_set(result: Framework17Result) -> None:
    """Store result with TTL expiry."""
    _cache[_CACHE_KEY] = (result, time.monotonic() + _CACHE_TTL_SECONDS)


def cache_invalidate() -> None:
    """Invalidate the F17 result cache.

    Called after POST /framework17/flag so the next read reflects the new flag.
    """
    _cache.pop(_CACHE_KEY, None)


# ---------------------------------------------------------------------------
# Public accessors for consuming frameworks
# ---------------------------------------------------------------------------


def get_f17_simple() -> Framework17SimpleResult | None:
    """Return the lightweight F17 result from cache (no DB call).

    Returns None when the cache is empty (first request of the day or after
    invalidation). Consuming frameworks must treat None as BLOCKED.
    """
    result = _cache_get()
    if result is None:
        return None
    return Framework17SimpleResult(
        f17_active=result.f17_active,
        flag_state=result.flag_state,
        clear_regime_possible=result.clear_regime_possible,
        severity=result.severity,
        brent_price=result.brent_price,
        conflict_duration_days=result.conflict_duration_days,
    )


def get_f17_clear_blocked() -> bool:
    """Return True when the ACTIVE geo flag should block CLEAR regime.

    Used by Framework 2 (regime_modifier_service) to prevent Rule 4 (CLEAR)
    when the operator has flagged an active geopolitical risk.

    Returns True when:
      - f17_active is True (ACTIVE flag)
    Returns False when:
      - Cache is empty (unknown — do not block; F2 falls back to market data)
      - f17_active is False (NONE or DE_ESCALATING)
      - f17_active is None (NOT_SET — do not silently default to block)
    """
    simple = get_f17_simple()
    if simple is None:
        return False
    return simple.f17_active is True


# ---------------------------------------------------------------------------
# Config reader
# ---------------------------------------------------------------------------


async def _get_config_str(key: str, session: AsyncSession) -> str:
    """Read a string value from atlas_config. Raises RuntimeError if missing."""
    from atlas.models.atlas_config import AtlasConfig

    row = await session.get(AtlasConfig, key)
    if row is None:
        raise RuntimeError(
            f"atlas_config key '{key}' not found. "
            "Run 'alembic upgrade head' to seed required config values."
        )
    return row.value


async def _get_config_float(key: str, session: AsyncSession) -> float:
    """Read a float value from atlas_config. Raises RuntimeError if missing."""
    return float(await _get_config_str(key, session))


# ---------------------------------------------------------------------------
# External data fetchers
# ---------------------------------------------------------------------------


async def _fetch_geopolitical_flag(session: AsyncSession) -> dict:
    """Fetch the current geopolitical flag from DB with carry-forward logic.

    Returns:
        {
          "found": bool,
          "flag_state": str,         # "NONE", "DE_ESCALATING", "ACTIVE", "NOT_SET"
          "set_by": str | None,
          "set_at": datetime | None,
          "conflict_start_date": date | None,
          "notes": str | None,
          "session_date": date | None,
          "carried_forward": bool,
        }
    """
    today = date.today()

    # Step 1: Try today's flag first.
    stmt_today = (
        select(GeopoliticalFlag)
        .where(GeopoliticalFlag.session_date == today)
        .order_by(GeopoliticalFlag.set_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt_today)).scalars().first()

    if row is not None:
        return {
            "found": True,
            "flag_state": row.flag_state,
            "set_by": row.set_by,
            "set_at": row.set_at,
            "conflict_start_date": row.conflict_start_date,
            "notes": row.notes,
            "session_date": row.session_date,
            "carried_forward": False,
        }

    # Step 2: Carry forward the most recent historical flag.
    stmt_history = (
        select(GeopoliticalFlag)
        .order_by(GeopoliticalFlag.session_date.desc(), GeopoliticalFlag.set_at.desc())
        .limit(1)
    )
    row_hist = (await session.execute(stmt_history)).scalars().first()

    if row_hist is not None:
        return {
            "found": True,
            "flag_state": row_hist.flag_state,
            "set_by": row_hist.set_by,
            "set_at": row_hist.set_at,
            "conflict_start_date": row_hist.conflict_start_date,
            "notes": row_hist.notes,
            "session_date": row_hist.session_date,
            "carried_forward": True,
        }

    # Step 3: No history — flag has never been set.
    return {
        "found": False,
        "flag_state": "NOT_SET",
        "set_by": None,
        "set_at": None,
        "conflict_start_date": None,
        "notes": None,
        "session_date": None,
        "carried_forward": False,
    }


async def _fetch_framework2_regime() -> dict:
    """Fetch current regime from Framework 2 endpoint.

    Framework 2 is the ONLY source for market regime.
    F17 never independently computes regime.

    Returns {"available": bool, "regime": str | None}.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8000{_F2_REGIME_PATH}",
                timeout=5.0,
            )

        if response.status_code != 200:
            return {
                "available": False,
                "regime": None,
                "reason": f"F2 endpoint returned {response.status_code}",
            }

        data = response.json()
        # Try multiple field names for compatibility with the regime response.
        regime = (
            data.get("effective_regime")
            or data.get("regime")
            or data.get("regime_rule")
        )
        return {"available": regime is not None, "regime": regime}

    except Exception as exc:
        return {"available": False, "regime": None, "reason": str(exc)}


async def _fetch_brent_price() -> float | None:
    """Fetch today's Brent crude daily close from Polygon.io.

    Uses the BZ ticker (Brent front-month). Returns None if today's data is
    not yet available or on any failure — does NOT fall back to stale prices.
    Polygon.io is the ONLY source for Brent price in F17.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        logger.warning("F17: POLYGON_API_KEY not set — Brent price unavailable")
        return None

    today_str = date.today().isoformat()
    url = _POLYGON_BRENT_URL.format(date=today_str)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={"adjusted": "true", "apiKey": settings.polygon_api_key},
                timeout=5.0,
            )

        if response.status_code != 200:
            logger.warning(
                "F17: Polygon Brent fetch failed",
                extra={"status": response.status_code},
            )
            return None

        data = response.json()
        results = data.get("results", [])
        if results:
            return float(results[-1].get("c", 0)) or None

        # No results for today — do not fall back to stale data.
        logger.warning("F17: No Brent price available for today — returning None")
        return None

    except Exception as exc:
        logger.warning("F17: Brent price fetch error", extra={"error": repr(exc)})
        return None


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def calculate_conflict_duration(conflict_start_date_str: str | None) -> int | None:
    """Calculate days elapsed since the conflict start date.

    Pure function — no I/O, no side effects.

    Args:
        conflict_start_date_str: ISO date string (YYYY-MM-DD) or None.

    Returns:
        Integer number of days since start_date (inclusive of today),
        or None if start_date is None or cannot be parsed.
    """
    if conflict_start_date_str is None:
        return None
    try:
        start = date.fromisoformat(str(conflict_start_date_str))
        delta = (date.today() - start).days
        return max(0, delta)
    except (ValueError, TypeError):
        return None


def _derive_severity(
    flag_state: GeoFlagState,
    regime: str | None,
    regime_available: bool,
) -> F17Severity:
    """Derive F17 severity from flag state and current regime.

    Pure function — no I/O.

    Rules:
      NOT_SET  → UNKNOWN
      NONE     → NONE
      DE_ESCALATING → ELEVATED
      ACTIVE + CRISIS/CAUTION → CRITICAL
      ACTIVE + SOFT_CAUTION   → HIGH
      ACTIVE + unavailable    → HIGH (conservative default)
      ACTIVE + CLEAR          → HIGH (CLEAR should be blocked by F2 integration)
    """
    if flag_state == GeoFlagState.NOT_SET:
        return F17Severity.UNKNOWN
    if flag_state == GeoFlagState.NONE:
        return F17Severity.NONE
    if flag_state == GeoFlagState.DE_ESCALATING:
        return F17Severity.ELEVATED

    # flag_state == ACTIVE from here
    if not regime_available or regime is None:
        return F17Severity.HIGH

    regime_upper = regime.upper()
    if any(crit in regime_upper for crit in ("CRISIS", "CAUTION")):
        # Distinguish CAUTION from SOFT CAUTION
        if "SOFT" in regime_upper:
            return F17Severity.HIGH
        return F17Severity.CRITICAL

    # CLEAR or unknown label with ACTIVE flag
    return F17Severity.HIGH


def _build_briefing_message(
    flag_state: GeoFlagState,
    severity: F17Severity,
    carried_forward: bool,
    conflict_duration_days: int | None,
    brent_price: float | None,
) -> tuple[str, str]:
    """Build morning briefing message and urgency level.

    Pure function — no I/O.

    Returns:
        (message: str, urgency: str)  — urgency is one of: URGENT, WARNING, INFO
    """
    if flag_state == GeoFlagState.NOT_SET:
        return (
            "URGENT: No geopolitical flag has ever been set. "
            "Operator action required before regime can be determined.",
            "URGENT",
        )

    duration_text = (
        f"Conflict duration: {conflict_duration_days} days. "
        if conflict_duration_days is not None
        else ""
    )
    brent_text = (
        f"Brent crude: ${brent_price:.2f}/bbl. "
        if brent_price is not None
        else ""
    )
    carry_text = " [Carried forward from previous session]" if carried_forward else ""

    if flag_state == GeoFlagState.ACTIVE:
        msg = (
            f"GEOPOLITICAL RISK ACTIVE.{carry_text} "
            f"{duration_text}{brent_text}"
            f"Severity: {severity.value}. "
            "Review Framework 27 contagion map and Framework 28 war duration ladder."
        )
        return msg, "URGENT" if severity == F17Severity.CRITICAL else "WARNING"

    if flag_state == GeoFlagState.DE_ESCALATING:
        msg = (
            f"Geopolitical risk de-escalating.{carry_text} "
            f"{duration_text}{brent_text}"
            "CLEAR regime now possible if market conditions permit."
        )
        return msg, "INFO"

    # NONE
    msg = (
        f"No active geopolitical risk.{carry_text} "
        f"{brent_text}"
        "CLEAR regime permitted if market conditions allow."
    )
    return msg, "INFO"


# ---------------------------------------------------------------------------
# Decision trace writer
# ---------------------------------------------------------------------------


async def _log_decision_trace(
    *,
    trigger: str,
    signal_type: str,
    resolution: str,
    human_override: bool,
    override_reason: str | None,
    session: AsyncSession,
) -> None:
    """Append a single entry to the decision_trace table.

    CRITICAL: Append-only. Never UPDATE or DELETE decision_trace rows.
    """
    try:
        trace = DecisionTrace(
            timestamp_utc=datetime.now(timezone.utc),
            trigger=trigger,
            signal_type=signal_type,
            ticker=None,
            human_override=human_override,
            override_reason=override_reason,
            resolution=resolution,
            visible_in_briefing=True,
        )
        session.add(trace)
    except Exception as exc:
        logger.error(
            "F17: decision trace write failed",
            extra={"error": repr(exc)},
        )


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


async def evaluate_framework17(session: AsyncSession) -> Framework17Result:
    """Evaluate current geopolitical state and build a Framework17Result.

    Fetches in parallel:
      1. Geopolitical flag from DB (with carry-forward)
      2. Regime from Framework 2 endpoint
      3. Brent price from Polygon.io

    Never auto-sets the flag. Never mutates the geopolitical_flag table.
    All threshold values come from atlas_config or F28 ladder tiers (DB).

    Returns a fully populated Framework17Result and writes it to cache.
    """
    cached = _cache_get()
    if cached is not None:
        return Framework17Result(**{**cached.model_dump(), "cache_hit": True})

    # Parallel fetch: flag (DB), regime (F2 HTTP), Brent (Polygon HTTP)
    flag_task = _fetch_geopolitical_flag(session)
    regime_task = _fetch_framework2_regime()
    brent_task = _fetch_brent_price()

    flag_data, regime_data, brent_price_raw = await asyncio.gather(
        flag_task,
        regime_task,
        brent_task,
        return_exceptions=True,
    )

    # Safely extract results (gather may return exceptions).
    if isinstance(flag_data, Exception):
        logger.error("F17: flag fetch failed", extra={"error": repr(flag_data)})
        flag_data = {
            "found": False,
            "flag_state": "NOT_SET",
            "set_by": None,
            "set_at": None,
            "conflict_start_date": None,
            "notes": None,
            "session_date": None,
            "carried_forward": False,
        }

    if isinstance(regime_data, Exception):
        logger.error("F17: regime fetch failed", extra={"error": repr(regime_data)})
        regime_data = {"available": False, "regime": None}

    brent_price: float | None = None
    if isinstance(brent_price_raw, float):
        brent_price = brent_price_raw
    elif brent_price_raw is not None and not isinstance(brent_price_raw, Exception):
        try:
            brent_price = float(brent_price_raw)
        except (TypeError, ValueError):
            pass

    # Build typed flag state.
    raw_flag_state: str = flag_data.get("flag_state", "NOT_SET")
    try:
        flag_state = GeoFlagState(raw_flag_state)
    except ValueError:
        logger.warning("F17: unknown flag_state value", extra={"value": raw_flag_state})
        flag_state = GeoFlagState.NOT_SET

    # Derive f17_active (None = never set, not False)
    f17_active: bool | None
    if flag_state == GeoFlagState.NOT_SET:
        f17_active = None
    elif flag_state == GeoFlagState.ACTIVE:
        f17_active = True
    else:
        f17_active = False

    # CLEAR regime is possible only when flag is NONE or DE_ESCALATING.
    clear_regime_possible = flag_state in (GeoFlagState.NONE, GeoFlagState.DE_ESCALATING)
    clear_regime_blocked = f17_active is True

    # Extract regime data.
    regime_available: bool = bool(regime_data.get("available"))
    regime: str | None = regime_data.get("regime")

    # Derive severity.
    severity = _derive_severity(flag_state, regime, regime_available)

    # Calculate conflict duration (pure function).
    conflict_start = flag_data.get("conflict_start_date")
    conflict_start_str: str | None = (
        conflict_start.isoformat() if isinstance(conflict_start, date) else conflict_start
    )
    conflict_duration_days = calculate_conflict_duration(conflict_start_str)

    # Build briefing message.
    briefing_message, briefing_urgency = _build_briefing_message(
        flag_state=flag_state,
        severity=severity,
        carried_forward=bool(flag_data.get("carried_forward")),
        conflict_duration_days=conflict_duration_days,
        brent_price=brent_price,
    )

    result = Framework17Result(
        f17_active=f17_active,
        flag_state=flag_state,
        clear_regime_possible=clear_regime_possible,
        severity=severity,
        brent_price=brent_price,
        conflict_duration_days=conflict_duration_days,
        set_by=flag_data.get("set_by"),
        set_at=flag_data.get("set_at"),
        conflict_start_date=conflict_start if isinstance(conflict_start, date) else None,
        notes=flag_data.get("notes"),
        session_date=flag_data.get("session_date"),
        carried_forward=bool(flag_data.get("carried_forward")),
        regime=regime,
        regime_available=regime_available,
        clear_regime_blocked=clear_regime_blocked,
        briefing_message=briefing_message,
        briefing_urgency=briefing_urgency,
        cache_hit=False,
        data_as_of=datetime.now(timezone.utc),
    )

    _cache_set(result)
    return result
