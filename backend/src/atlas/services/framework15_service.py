"""Framework 15 — VIX Regime Override service.

Protects the portfolio from panic buying into a sudden intraday VIX spike.
Framework 1 reacts to VIX at close; Framework 15 reacts to VIX intraday.
Together they cover both time horizons.

Trigger condition:
    spike_size = current_vix - session_open_vix
    If spike_size > spike_threshold → Framework 15 fires.

    spike_threshold comes from atlas_config (key: f15_spike_threshold_points).
    session_start / session_end from atlas_config (keys: f15_session_start_et,
    f15_session_end_et).  NEVER hardcode these values.

Data sources (single-source-of-truth rules):
    Polygon.io       — ONLY source for intraday VIX data.
    Framework 2      — ONLY source for current regime; F15 never computes regime.
    gtc_orders table — source for open non-stop buy orders.
    atlas_config     — all threshold/session values.

F15 is the ONLY source for f15_active in the system.
F3 (Score Action Map), F4 (Tranche Deployment), Section 17 (LEAPS),
and F25 (Liquidity Protocol) all read from this module's cache.

Cache:
    Module-level dict with 60-second TTL.  Very short because intraday
    VIX changes every minute.
    Cache key: "f15_result" (portfolio-level, not per-ticker).

Session state persistence:
    framework15_sessions table — one row per trading day.
    Once f15_triggered = True for a session it stays True for that session.
    At the next session open the service creates a fresh row.

Session open VIX:
    Fetched once per session from Polygon.io and stored in a module-level
    dict keyed by date string (no Redis in V1; pattern matches F12 / F29).
    Key: session_open_vix_{date}

Conservative defaults:
    VIX data unavailable → f15_active = None → treat as BLOCKED everywhere.
    Regime unavailable → severity = HIGH (never UNKNOWN when spike is confirmed).
    Config unavailable → return CRITICAL status immediately; do not evaluate.
    Order DB unavailable → log halt; manual review required.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Final

import httpx
import pytz
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.models.atlas_config import AtlasConfig
from atlas.models.decision_trace import DecisionTrace
from atlas.models.framework15_paused_order import Framework15PausedOrder
from atlas.models.framework15_session import Framework15Session
from atlas.models.gtc_order import GtcOrder
from atlas.schemas.framework15 import (
    F15Severity,
    F15Status,
    Framework15Result,
    Framework15SimpleResult,
    OrderReviewStatus,
    PausedOrder,
    VixSnapshot,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — all spec values are named constants, never hardcoded inline
# ---------------------------------------------------------------------------

# Cache TTL: 60 seconds — intraday VIX changes every minute.
_CACHE_TTL_SECONDS: Final[int] = 60

# Module-level result cache.  Single portfolio-level entry.
_CACHE_KEY: Final[str] = "f15_result"

# Session open VIX cache — keyed by ISO date string (YYYY-MM-DD).
# Stores (vix_value: float, fetched_at: float).
_SESSION_OPEN_VIX_CACHE: dict[str, tuple[float, float]] = {}

# Main result cache: key → (Framework15Result, expiry_monotonic)
_cache: dict[str, tuple[Framework15Result, float]] = {}

# Config DB key names — ONLY the key strings are constants; values come from DB.
_CONFIG_KEY_SPIKE_THRESHOLD: Final[str] = "f15_spike_threshold_points"
_CONFIG_KEY_SESSION_START: Final[str] = "f15_session_start_et"
_CONFIG_KEY_SESSION_END: Final[str] = "f15_session_end_et"

# Framework 2 internal endpoint for regime reads.
_F2_REGIME_PATH: Final[str] = "/api/v1/regime-modifier/regime"

# Polygon VIX intraday aggs endpoint template.
_POLYGON_VIX_AGGS: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/I:VIX/range/1/minute/{date}/{date}"
)

# Eastern Time timezone object.
_ET_TZ: Final = pytz.timezone("America/New_York")


# ---------------------------------------------------------------------------
# Module-level cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> Framework15Result | None:
    """Return cached result if not expired, else None."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _cache[_CACHE_KEY]
        return None
    return result


def _cache_set(result: Framework15Result) -> None:
    """Store result with TTL expiry."""
    _cache[_CACHE_KEY] = (result, time.monotonic() + _CACHE_TTL_SECONDS)


def cache_invalidate() -> None:
    """Invalidate the F15 result cache."""
    _cache.pop(_CACHE_KEY, None)


# ---------------------------------------------------------------------------
# Sync accessor for consuming frameworks (F3, F4, Section 17, F25)
# ---------------------------------------------------------------------------


def get_f15_simple() -> Framework15SimpleResult | None:
    """Return lightweight F15 status from cache.

    Returns None when the cache is empty or expired.
    Consuming frameworks call this — never evaluate_framework15 directly.
    F15 is the single source of truth for f15_active.
    """
    cached = _cache_get()
    if cached is None:
        return None
    return Framework15SimpleResult(
        f15_status=cached.f15_status,
        f15_active=cached.f15_active,
        severity=cached.severity,
        new_market_orders_blocked=cached.new_market_orders_blocked,
        non_stop_orders_paused=cached.non_stop_orders_paused,
        data_gap_severity=cached.data_gap_severity,
        market_open=cached.market_open,
    )


def get_vix_snapshot() -> VixSnapshot | None:
    """Return VIX snapshot for Framework 25 from cache.

    Returns None when cache is empty.  Caller must handle None gracefully.
    """
    cached = _cache_get()
    if cached is None:
        return None
    return VixSnapshot(
        current_vix=cached.current_vix,
        session_open_vix=cached.session_open_vix,
        spike_size=cached.spike_size,
        spike_threshold=cached.spike_threshold,
        f15_active=cached.f15_active,
        data_available=cached.polygon_available,
        market_open=cached.market_open,
        last_updated=cached.last_updated,
    )


# ---------------------------------------------------------------------------
# Config reader
# ---------------------------------------------------------------------------


async def _get_config_str(key: str, session: AsyncSession) -> str:
    """Read a string value from atlas_config.  Raises RuntimeError if missing."""
    row = await session.get(AtlasConfig, key)
    if row is None:
        raise RuntimeError(
            f"atlas_config key '{key}' not found. "
            "Run 'alembic upgrade head' to seed required config values."
        )
    return row.value


async def _get_config_float(key: str, session: AsyncSession) -> float:
    """Read a float value from atlas_config.  Raises RuntimeError if missing."""
    return float(await _get_config_str(key, session))


# ---------------------------------------------------------------------------
# Market hours check (pure logic — session times come from atlas_config)
# ---------------------------------------------------------------------------


def is_market_open(session_start: str, session_end: str) -> bool:
    """Return True when current ET time is within market session hours.

    session_start and session_end are HH:MM strings from atlas_config.
    NEVER hardcoded.  Weekends always return False.
    """
    now_et = datetime.now(_ET_TZ)

    # Skip weekends (Saturday=5, Sunday=6)
    if now_et.weekday() >= 5:
        return False

    start_h, start_m = map(int, session_start.split(":"))
    end_h, end_m = map(int, session_end.split(":"))

    session_open = now_et.replace(
        hour=start_h, minute=start_m, second=0, microsecond=0
    )
    session_close = now_et.replace(
        hour=end_h, minute=end_m, second=0, microsecond=0
    )

    return session_open <= now_et <= session_close


# ---------------------------------------------------------------------------
# Polygon VIX fetchers
# ---------------------------------------------------------------------------


async def _fetch_session_open_vix(
    session_date: str,
    session_start: str,
    polygon_api_key: str,
) -> dict:
    """Fetch VIX at session open from Polygon.io.

    Caches the result in _SESSION_OPEN_VIX_CACHE for the session duration.
    The cache key is the ISO date string (YYYY-MM-DD).
    Returns {"available": bool, "vix": float | None, "from_cache": bool, "reason": str}.
    """
    cached_entry = _SESSION_OPEN_VIX_CACHE.get(session_date)
    if cached_entry is not None:
        vix_val, _ = cached_entry
        return {"available": True, "vix": vix_val, "from_cache": True}

    if not polygon_api_key:
        return {
            "available": False,
            "vix": None,
            "from_cache": False,
            "reason": "POLYGON_API_KEY not configured",
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _POLYGON_VIX_AGGS.format(date=session_date),
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 10,
                    "apiKey": polygon_api_key,
                },
                timeout=10.0,
            )

        if response.status_code == 429:
            return {
                "available": False,
                "vix": None,
                "from_cache": False,
                "reason": "Polygon rate limited (429)",
            }

        if response.status_code != 200:
            return {
                "available": False,
                "vix": None,
                "from_cache": False,
                "reason": f"Polygon returned {response.status_code}",
            }

        results = response.json().get("results", [])
        if not results:
            return {
                "available": False,
                "vix": None,
                "from_cache": False,
                "reason": "No VIX data at session open yet — market may have just opened.",
            }

        # Use open price of the first candle; fall back to close if open is None.
        first = results[0]
        open_vix = first.get("o") or first.get("c")
        if open_vix is None:
            return {
                "available": False,
                "vix": None,
                "from_cache": False,
                "reason": "VIX open price missing from first candle.",
            }

        vix_f = float(open_vix)
        _SESSION_OPEN_VIX_CACHE[session_date] = (vix_f, time.time())

        return {"available": True, "vix": vix_f, "from_cache": False}

    except Exception as exc:
        return {
            "available": False,
            "vix": None,
            "from_cache": False,
            "reason": str(exc),
        }


async def _fetch_current_intraday_vix(
    session_date: str,
    polygon_api_key: str,
) -> dict:
    """Fetch the most recent VIX intraday value from Polygon.io.

    Uses the last completed minute candle (sort=desc, limit=1).
    Returns {"available": bool, "vix": float | None, "reason": str}.
    """
    if not polygon_api_key:
        return {
            "available": False,
            "vix": None,
            "reason": "POLYGON_API_KEY not configured",
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _POLYGON_VIX_AGGS.format(date=session_date),
                params={
                    "adjusted": "true",
                    "sort": "desc",
                    "limit": 1,
                    "apiKey": polygon_api_key,
                },
                timeout=10.0,
            )

        if response.status_code == 429:
            return {
                "available": False,
                "vix": None,
                "reason": "Polygon rate limited (429) — cannot read current VIX.",
            }

        if response.status_code != 200:
            return {
                "available": False,
                "vix": None,
                "reason": f"Polygon returned {response.status_code}",
            }

        results = response.json().get("results", [])
        if not results:
            return {
                "available": False,
                "vix": None,
                "reason": "No VIX minute data returned for today.",
            }

        current_vix = results[0].get("c")
        if current_vix is None:
            return {
                "available": False,
                "vix": None,
                "reason": "VIX close price missing from most recent candle.",
            }

        return {"available": True, "vix": float(current_vix)}

    except Exception as exc:
        return {"available": False, "vix": None, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Framework 2 regime reader
# ---------------------------------------------------------------------------


async def _fetch_framework2_regime() -> dict:
    """Fetch current regime from Framework 2 endpoint.

    Framework 2 is the ONLY source for regime.
    F15 never independently computes regime.
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
        regime = data.get("regime") or data.get("regime_rule")
        return {"available": regime is not None, "regime": regime}

    except Exception as exc:
        return {"available": False, "regime": None, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Order management
# ---------------------------------------------------------------------------


async def _fetch_open_non_stop_buy_orders(
    session: AsyncSession,
) -> dict:
    """Query the DB for all open non-stop buy orders.

    Returns {"available": bool, "orders": list[dict]}.
    Stop-loss orders are excluded — they must remain active for downside protection.
    """
    try:
        result = await session.execute(
            select(
                GtcOrder.id,
                GtcOrder.ticker,
                GtcOrder.status,
            ).where(
                GtcOrder.status.in_(["OPEN", "PENDING"]),
                GtcOrder.side == "BUY",
            )
        )
        rows = result.all()
        orders = [
            {
                "id": row.id,
                "ticker": row.ticker,
                "order_type": "GTC",
                "status": row.status,
            }
            for row in rows
        ]
        return {"available": True, "orders": orders}
    except Exception as exc:
        logger.warning(
            "F15: order DB query failed",
            extra={"error": repr(exc)},
        )
        return {"available": False, "orders": [], "reason": str(exc)}


async def _pause_orders_for_session(
    orders: list[dict],
    session_date: date,
    session: AsyncSession,
) -> int:
    """Pause all provided non-stop buy orders for this session.

    Sets gtc_orders.status = 'PAUSED_F15' and inserts a tracking row
    into framework15_paused_orders.  Uses ON CONFLICT DO NOTHING so the
    function is idempotent if called twice in the same session.

    Returns the count of orders successfully paused.
    """
    paused_count = 0
    for order in orders:
        try:
            await session.execute(
                text(
                    "UPDATE gtc_orders SET status = 'PAUSED_F15', "
                    "updated_at = NOW() WHERE id = :order_id"
                ),
                {"order_id": order["id"]},
            )
            # framework15_paused_orders has a unique constraint on
            # (session_date, order_id) — the INSERT is idempotent.
            await session.execute(
                text(
                    "INSERT INTO framework15_paused_orders "
                    "(session_date, order_id, ticker, order_type, paused_at) "
                    "VALUES (:sd, :oid, :ticker, :otype, NOW()) "
                    "ON CONFLICT (session_date, order_id) DO NOTHING"
                ),
                {
                    "sd": session_date,
                    "oid": order["id"],
                    "ticker": order["ticker"],
                    "otype": order.get("order_type", "GTC"),
                },
            )
            paused_count += 1
        except Exception as exc:
            logger.warning(
                "F15: failed to pause order",
                extra={"order_id": order.get("id"), "error": repr(exc)},
            )
    return paused_count


# ---------------------------------------------------------------------------
# Decision trace logger (append-only)
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

    CRITICAL: This is append-only.  Never UPDATE or DELETE decision_trace rows.
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
            "F15: decision trace write failed",
            extra={"error": repr(exc)},
        )


# ---------------------------------------------------------------------------
# Severity mapping (pure — no I/O)
# ---------------------------------------------------------------------------


def _determine_severity(
    regime: str | None,
    regime_available: bool,
) -> F15Severity:
    """Map regime to F15 alert severity.

    CAUTION or CRISIS_HALT → CRITICAL.
    Regime unavailable → HIGH (conservative default per spec).
    All other regimes → HIGH.
    """
    if not regime_available or regime is None:
        return F15Severity.HIGH

    regime_upper = regime.strip().upper()
    if regime_upper in {"CAUTION", "CRISIS_HALT", "CRISIS"}:
        return F15Severity.CRITICAL

    return F15Severity.HIGH


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def evaluate_framework15(session: AsyncSession) -> Framework15Result:
    """Evaluate Framework 15 VIX Regime Override for the current session.

    Steps:
      1. Read config from atlas_config (spike_threshold, session hours).
      2. Check market hours.  Return OUTSIDE_HOURS immediately if closed.
      3. Check session DB record — if already triggered, preserve halt state.
      4. Fetch VIX data (session open + current) and regime in parallel.
      5. Calculate spike size and determine if threshold is exceeded.
      6. Determine f15_active (True | False | None).
      7. Determine alert severity from Framework 2 regime.
      8. If newly triggered: pause orders, write session record, log trace.
      9. If already triggered: load paused orders from DB.
     10. Check override state.
     11. Assemble result, cache for 60 s, return.

    All threshold and session-hours values come from atlas_config.
    None is used (not False) when data is unavailable — consumers treat
    None as UNKNOWN and block as a precaution.
    """
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Step 1 — Read config
    # ------------------------------------------------------------------
    try:
        spike_threshold = await _get_config_float(
            _CONFIG_KEY_SPIKE_THRESHOLD, session
        )
        session_start = await _get_config_str(_CONFIG_KEY_SESSION_START, session)
        session_end = await _get_config_str(_CONFIG_KEY_SESSION_END, session)
    except RuntimeError as exc:
        now_str = datetime.now(timezone.utc).isoformat()
        return Framework15Result(
            f15_status=F15Status.UNKNOWN,
            f15_active=None,
            severity=None,
            current_vix=None,
            session_open_vix=None,
            spike_size=None,
            spike_threshold=None,
            spike_confirmed=None,
            market_open=False,
            session_date=date.today().isoformat(),
            halt_triggered_at=None,
            new_market_orders_blocked=True,
            non_stop_orders_paused=False,
            limit_orders_flagged=False,
            paused_orders_count=0,
            paused_orders=[],
            regime=None,
            regime_available=False,
            polygon_available=False,
            override_active=False,
            override_reason=None,
            data_gap_severity="CRITICAL",
            warning_messages=[f"Cannot read config from atlas_config: {exc}"],
            last_updated=now_str,
            cache_hit=False,
        )

    # ------------------------------------------------------------------
    # Step 2 — Check market hours (pure function — reads atlas_config values)
    # ------------------------------------------------------------------
    market_open = is_market_open(session_start, session_end)
    today = date.today()
    session_date_str = today.isoformat()
    now_utc = datetime.now(timezone.utc).isoformat()

    if not market_open:
        result = Framework15Result(
            f15_status=F15Status.OUTSIDE_HOURS,
            f15_active=False,
            severity=None,
            current_vix=None,
            session_open_vix=None,
            spike_size=None,
            spike_threshold=spike_threshold,
            spike_confirmed=False,
            market_open=False,
            session_date=session_date_str,
            halt_triggered_at=None,
            new_market_orders_blocked=False,
            non_stop_orders_paused=False,
            limit_orders_flagged=False,
            paused_orders_count=0,
            paused_orders=[],
            regime=None,
            regime_available=False,
            polygon_available=False,
            override_active=False,
            override_reason=None,
            data_gap_severity="NONE",
            warning_messages=[
                f"Market closed — F15 only monitors during market hours "
                f"({session_start}–{session_end} ET)."
            ],
            last_updated=now_utc,
            cache_hit=False,
        )
        _cache_set(result)
        return result

    # ------------------------------------------------------------------
    # Step 3 — Check DB session record for existing halt state
    # ------------------------------------------------------------------
    session_record = await session.execute(
        select(Framework15Session).where(
            Framework15Session.session_date == today
        )
    )
    session_row = session_record.scalar_one_or_none()
    already_triggered = session_row is not None and session_row.f15_triggered

    # ------------------------------------------------------------------
    # Step 4 — Fetch VIX data + Framework 2 regime in parallel
    # ------------------------------------------------------------------
    polygon_api_key = get_settings().polygon_api_key

    (
        session_open_result,
        current_vix_result,
        regime_result,
    ) = await asyncio.gather(
        _fetch_session_open_vix(session_date_str, session_start, polygon_api_key),
        _fetch_current_intraday_vix(session_date_str, polygon_api_key),
        _fetch_framework2_regime(),
        return_exceptions=True,
    )

    # Unwrap any unexpected exceptions from gather.
    if isinstance(session_open_result, BaseException):
        session_open_result = {
            "available": False,
            "vix": None,
            "reason": str(session_open_result),
        }
    if isinstance(current_vix_result, BaseException):
        current_vix_result = {
            "available": False,
            "vix": None,
            "reason": str(current_vix_result),
        }
    if isinstance(regime_result, BaseException):
        regime_result = {"available": False, "regime": None}

    polygon_available = (
        session_open_result.get("available", False)
        and current_vix_result.get("available", False)
    )
    regime_available: bool = regime_result.get("available", False)

    session_open_vix: float | None = session_open_result.get("vix")
    current_vix: float | None = current_vix_result.get("vix")
    regime: str | None = regime_result.get("regime")

    if not polygon_available:
        reason_parts: list[str] = []
        if not session_open_result.get("available"):
            reason_parts.append(
                session_open_result.get("reason", "session open VIX unavailable")
            )
        if not current_vix_result.get("available"):
            reason_parts.append(
                current_vix_result.get("reason", "current VIX unavailable")
            )
        warnings.append(
            "Polygon.io VIX data unavailable — cannot calculate spike size. "
            "F15 status UNKNOWN. All new orders blocked for safety. "
            f"Detail: {'; '.join(reason_parts)}"
        )

    if not regime_available:
        warnings.append(
            "Framework 2 regime unavailable — "
            "using HIGH severity as conservative default."
        )

    # Session open VIX "waiting" message at market open.
    if (
        polygon_available
        and session_open_vix is None
        and not session_open_result.get("from_cache", False)
    ):
        warnings.append(
            "Waiting for session open VIX — "
            "market may have just opened; first minute candle not yet available."
        )

    # ------------------------------------------------------------------
    # Step 5 — Calculate spike
    # ------------------------------------------------------------------
    spike_size: float | None = None
    spike_confirmed: bool | None = None

    if session_open_vix is not None and current_vix is not None:
        spike_size = current_vix - session_open_vix
        # Spike must be GREATER than threshold — exactly equal does NOT trigger.
        spike_confirmed = spike_size > spike_threshold
    elif already_triggered:
        # Halt already recorded in DB — preserve it regardless of VIX availability.
        spike_confirmed = True
        warnings.append(
            "VIX data currently unavailable but F15 was already triggered "
            "this session. Halt remains active for the full session."
        )
    else:
        spike_confirmed = None

    # ------------------------------------------------------------------
    # Step 6 — Determine f15_active
    # ------------------------------------------------------------------
    if already_triggered:
        f15_active: bool | None = True
        f15_status = F15Status.ACTIVE
    elif spike_confirmed is True:
        f15_active = True
        f15_status = F15Status.ACTIVE
    elif spike_confirmed is False:
        f15_active = False
        f15_status = F15Status.CLEAR
    else:
        # spike_confirmed is None — data unavailable
        f15_active = None
        f15_status = F15Status.UNKNOWN

    # ------------------------------------------------------------------
    # Step 7 — Determine severity
    # ------------------------------------------------------------------
    severity: F15Severity | None = None
    if f15_active is True or f15_active is None:
        severity = _determine_severity(regime, regime_available)

    # ------------------------------------------------------------------
    # Step 8 — If newly triggered: pause orders + write DB record
    # ------------------------------------------------------------------
    halt_triggered_at: str | None = None
    paused_orders_count: int = 0
    paused_orders: list[PausedOrder] = []

    if spike_confirmed is True and not already_triggered:
        halt_triggered_at = datetime.now(timezone.utc).isoformat()

        # Pause all open non-stop buy orders.
        orders_result = await _fetch_open_non_stop_buy_orders(session)
        if orders_result.get("available"):
            paused_orders_count = await _pause_orders_for_session(
                orders_result.get("orders", []), today, session
            )
        else:
            warnings.append(
                "Order DB unavailable — cannot pause orders automatically. "
                "Manual review required. "
                f"Detail: {orders_result.get('reason', 'unknown')}"
            )

        # Write / update the session record.
        await session.execute(
            text(
                """
                INSERT INTO framework15_sessions
                  (session_date, session_open_vix, f15_triggered,
                   f15_triggered_at, vix_at_trigger, spike_size,
                   severity, regime_at_trigger, orders_paused_count)
                VALUES
                  (:sd, :sov, true, :triggered_at, :vat, :ss, :sev, :rat, :opc)
                ON CONFLICT (session_date) DO UPDATE SET
                  f15_triggered        = true,
                  f15_triggered_at     = EXCLUDED.f15_triggered_at,
                  vix_at_trigger       = EXCLUDED.vix_at_trigger,
                  spike_size           = EXCLUDED.spike_size,
                  severity             = EXCLUDED.severity,
                  regime_at_trigger    = EXCLUDED.regime_at_trigger,
                  orders_paused_count  = EXCLUDED.orders_paused_count,
                  updated_at           = NOW()
                """
            ),
            {
                "sd": today,
                "sov": session_open_vix,
                "triggered_at": datetime.now(timezone.utc),
                "vat": current_vix,
                "ss": round(spike_size, 2) if spike_size is not None else None,
                "sev": severity.value if severity else None,
                "rat": regime,
                "opc": paused_orders_count,
            },
        )

        await _log_decision_trace(
            trigger="FRAMEWORK_15",
            signal_type="HALT",
            resolution=(
                f"VIX spike {spike_size:.2f} points above session open "
                f"({session_open_vix:.2f} → {current_vix:.2f}). "
                f"Session halt activated. {paused_orders_count} orders paused. "
                f"Severity: {severity.value if severity else 'UNKNOWN'}."
            ),
            human_override=False,
            override_reason=None,
            session=session,
        )

        await session.commit()

        # Refresh session_row to get the freshly inserted record.
        session_record2 = await session.execute(
            select(Framework15Session).where(
                Framework15Session.session_date == today
            )
        )
        session_row = session_record2.scalar_one_or_none()

    elif already_triggered and session_row is not None:
        # Load halt state from existing DB record.
        if session_row.f15_triggered_at:
            halt_triggered_at = session_row.f15_triggered_at.isoformat()
        paused_orders_count = session_row.orders_paused_count or 0

        # Load paused order details.
        paused_rows_result = await session.execute(
            select(Framework15PausedOrder).where(
                Framework15PausedOrder.session_date == today
            )
        )
        paused_rows = paused_rows_result.scalars().all()
        paused_orders = [
            PausedOrder(
                order_id=row.order_id,
                ticker=row.ticker,
                order_type=row.order_type,
                paused_at=row.paused_at.isoformat(),
                review_status=OrderReviewStatus(row.review_status),
            )
            for row in paused_rows
        ]

    # ------------------------------------------------------------------
    # Step 9 — Store session open VIX in DB record if not already stored
    # ------------------------------------------------------------------
    if (
        session_open_vix is not None
        and session_row is not None
        and session_row.session_open_vix is None
    ):
        await session.execute(
            text(
                "UPDATE framework15_sessions SET session_open_vix = :sov, "
                "updated_at = NOW() WHERE session_date = :sd"
            ),
            {"sov": session_open_vix, "sd": today},
        )
        await session.commit()
    elif session_open_vix is not None and session_row is None:
        # Create a CLEAR session row to store the open VIX for later comparison.
        await session.execute(
            text(
                "INSERT INTO framework15_sessions (session_date, session_open_vix) "
                "VALUES (:sd, :sov) ON CONFLICT (session_date) DO NOTHING"
            ),
            {"sd": today, "sov": session_open_vix},
        )
        await session.commit()

    # ------------------------------------------------------------------
    # Step 10 — Check override
    # ------------------------------------------------------------------
    override_active = False
    override_reason: str | None = None
    if session_row is not None and session_row.override_applied:
        override_active = True
        override_reason = session_row.override_reason

    # ------------------------------------------------------------------
    # Step 11 — Data gap severity
    # ------------------------------------------------------------------
    if not polygon_available and not regime_available:
        gap_severity = "CRITICAL"
    elif not polygon_available:
        gap_severity = "MAJOR"
    elif not regime_available:
        gap_severity = "PARTIAL"
    else:
        gap_severity = "NONE"

    # ------------------------------------------------------------------
    # Step 12 — Assemble and cache result
    # ------------------------------------------------------------------
    result = Framework15Result(
        f15_status=f15_status,
        f15_active=f15_active,
        severity=severity,
        current_vix=current_vix,
        session_open_vix=session_open_vix,
        spike_size=round(spike_size, 2) if spike_size is not None else None,
        spike_threshold=spike_threshold,
        spike_confirmed=spike_confirmed,
        market_open=market_open,
        session_date=session_date_str,
        halt_triggered_at=halt_triggered_at,
        # Blocking state:
        # - market orders blocked when f15_active is True OR None (unknown)
        # - non-stop orders paused only when f15_active is True (confirmed halt)
        # - limit orders flagged for review when f15_active is True
        new_market_orders_blocked=(f15_active is True or f15_active is None),
        non_stop_orders_paused=(f15_active is True),
        limit_orders_flagged=(f15_active is True),
        paused_orders_count=paused_orders_count,
        paused_orders=paused_orders,
        regime=regime,
        regime_available=regime_available,
        polygon_available=polygon_available,
        override_active=override_active,
        override_reason=override_reason,
        data_gap_severity=gap_severity,
        warning_messages=warnings,
        last_updated=now_utc,
        cache_hit=False,
    )

    _cache_set(result)
    return result
