"""Framework 19 — NVDA Kill Switch service.

Trigger condition:
    NVDA falls > f19_drop_threshold_pct (4 %) within the last
    f19_time_window_minutes (60 minutes) of intraday trading.

When triggered:
    1. All AI-correlated buy orders are paused (status = 'PAUSED_F19').
    2. Holdings with beta_vs_nvda > f19_beta_threshold (1.5) are flagged —
       any new market orders for those tickers are blocked.
    3. A structured alert is sent (V1: structlog only).
    4. Session state is persisted to framework19_sessions for the rest of
       the trading day (the kill switch does NOT auto-reset intraday).

Zero-cache rule:
    Unlike Framework 15 (60s cache) and Framework 18 (900s cache),
    Framework 19 makes a fresh Polygon.io call on EVERY evaluation.
    This is intentional: the kill switch must be reactive to the most
    recent NVDA move and no stale price data is tolerable.

Session state:
    DB-backed — framework19_sessions table (one row per trading day).
    Once f19_triggered = True it NEVER reverts within that session.
    This is enforced at the DB level — no UPDATE f19_triggered to False.

Consuming frameworks:
    F3 (Score Action Map) and F4 (Tranche Deployment) call
    get_f19_simple(session) — lightweight async read of today's
    session row.  They NEVER independently evaluate NVDA drop.

APScheduler:
    evaluate_framework19 is called by the scheduler every 2 minutes
    during market hours (09:30-16:00 ET, weekdays only).
    See atlas.core.scheduler for the job definition.

Data sources (single-source-of-truth rules):
    Polygon.io           — ONLY source for intraday NVDA prices.
    portfolio_beta table — ONLY source for ticker beta vs NVDA.
    gtc_orders table     — ONLY source for open buy orders.
    atlas_config         — all threshold / session values.
    Framework 2          — ONLY source for regime; F19 never computes it.

Conservative defaults:
    Polygon unavailable   → f19_active = None → treat as BLOCKED everywhere.
    Beta data missing     → assume high beta → block market orders for that ticker.
    Config key missing    → raise RuntimeError; never substitute assumed values.
    Order DB unavailable  → log warning; halt manually.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final

import httpx
import pytz
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.models.atlas_config import AtlasConfig
from atlas.models.framework19_paused_order import Framework19PausedOrder
from atlas.models.framework19_session import Framework19Session
from atlas.models.gtc_order import GtcOrder
from atlas.models.portfolio_beta import PortfolioBeta
from atlas.models.ticker import Ticker
from atlas.schemas.framework19 import (
    AffectedHolding,
    F19Severity,
    F19Status,
    Framework19Result,
    Framework19SimpleResult,
    NVDADropDetail,
    OrderReviewStatus,
    PausedOrder,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — never hardcode spec values in the evaluation logic
# ---------------------------------------------------------------------------

# Config DB key names.  Values always come from atlas_config table.
_CONFIG_KEY_DROP_THRESHOLD: Final[str] = "f19_drop_threshold_pct"
_CONFIG_KEY_WINDOW_MINUTES: Final[str] = "f19_time_window_minutes"
_CONFIG_KEY_BETA_THRESHOLD: Final[str] = "f19_beta_threshold"
_CONFIG_KEY_SESSION_START: Final[str] = "f15_session_start_et"   # reuse F15 key
_CONFIG_KEY_SESSION_END: Final[str] = "f15_session_end_et"       # reuse F15 key

# Polygon endpoint template for NVDA 1-minute candles.
_POLYGON_NVDA_AGGS: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/NVDA/range/1/minute/{date}/{date}"
)

# Framework 2 internal endpoint for regime reads.
_F2_REGIME_PATH: Final[str] = "/api/v1/regime-modifier/regime"

# Eastern Time timezone.
_ET_TZ: Final = pytz.timezone("America/New_York")

# Number of extra candles to request beyond the window to account for missing minutes.
_CANDLE_BUFFER: Final[int] = 10

# Status returned for buy orders paused by F19.
_PAUSED_STATUS: Final[str] = "PAUSED_F19"


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
# Market hours (pure logic — times come from atlas_config)
# ---------------------------------------------------------------------------


def _is_market_open(session_start: str, session_end: str) -> bool:
    """Return True when current ET time is within market session hours.

    session_start and session_end are HH:MM strings from atlas_config.
    Weekends always return False.
    Pure function — no I/O.
    """
    now_et = datetime.now(_ET_TZ)

    # Saturday=5, Sunday=6 — markets closed.
    if now_et.weekday() >= 5:
        return False

    start_h, start_m = map(int, session_start.split(":"))
    end_h, end_m = map(int, session_end.split(":"))

    session_open = now_et.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    session_close = now_et.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    return session_open <= now_et <= session_close


# ---------------------------------------------------------------------------
# NVDA intraday fetch — NO CACHE (every call hits Polygon fresh)
# ---------------------------------------------------------------------------


async def _fetch_nvda_intraday_minutes(
    session_date: str,
    window_minutes: int,
    polygon_api_key: str,
) -> dict[str, Any]:
    """Fetch NVDA 1-minute candles from Polygon.io.

    ZERO CACHING — this is the invariant that makes F19 reactive.
    Returns {"available": bool, "candles": list[dict], "reason": str | None}.

    Candle dict format: {"t": int (ms epoch), "c": float, "o": float,
                         "h": float, "l": float, "v": int}
    """
    if not polygon_api_key:
        return {
            "available": False,
            "candles": [],
            "reason": "Polygon API key not configured",
        }

    url = _POLYGON_NVDA_AGGS.format(date=session_date)
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": str(window_minutes + _CANDLE_BUFFER),
        "apiKey": polygon_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

        if response.status_code != 200:
            logger.warning(
                "F19: Polygon returned non-200 for NVDA candles",
                extra={"status": response.status_code, "date": session_date},
            )
            return {
                "available": False,
                "candles": [],
                "reason": f"Polygon HTTP {response.status_code}",
            }

        data = response.json()
        results = data.get("results") or []
        return {"available": True, "candles": results, "reason": None}

    except httpx.TimeoutException:
        logger.warning("F19: Polygon request timed out", extra={"date": session_date})
        return {"available": False, "candles": [], "reason": "Polygon request timed out"}
    except Exception as exc:
        logger.warning(
            "F19: Polygon fetch error",
            extra={"error": repr(exc), "date": session_date},
        )
        return {"available": False, "candles": [], "reason": str(exc)}


# ---------------------------------------------------------------------------
# Pure drop calculation — no I/O, fully unit-testable
# ---------------------------------------------------------------------------


def calculate_nvda_drop(
    candles: list[dict[str, Any]],
    threshold_pct: float,
    window_minutes: int,
) -> dict[str, Any]:
    """Determine whether NVDA dropped >= threshold % within the window.

    Algorithm (rolling peak-to-trough within the last window_minutes):
      1. Filter candles to the last window_minutes items.
      2. Find the highest close price within those candles (peak).
      3. Get the most recent close (current).
      4. Compute drop_pct = (peak - current) / peak * 100.
      5. If drop_pct >= threshold_pct → threshold_breached = True.

    Returns:
        {
            "threshold_breached": bool,
            "drop_pct": float | None,
            "drop_amount": float | None,
            "peak_price": float | None,
            "current_price": float | None,
            "candles_used": int,
        }

    Pure function — no I/O, no side effects, no randomness.
    """
    if not candles:
        return {
            "threshold_breached": False,
            "drop_pct": None,
            "drop_amount": None,
            "peak_price": None,
            "current_price": None,
            "candles_used": 0,
        }

    # Use the most recent window_minutes candles (already sorted ascending by Polygon).
    window_candles = candles[-window_minutes:] if len(candles) > window_minutes else candles

    closes = [float(c["c"]) for c in window_candles if "c" in c]
    if not closes:
        return {
            "threshold_breached": False,
            "drop_pct": None,
            "drop_amount": None,
            "peak_price": None,
            "current_price": None,
            "candles_used": len(window_candles),
        }

    peak = max(closes)
    current = closes[-1]

    if peak <= 0.0:
        return {
            "threshold_breached": False,
            "drop_pct": 0.0,
            "drop_amount": 0.0,
            "peak_price": peak,
            "current_price": current,
            "candles_used": len(window_candles),
        }

    drop_pct = (peak - current) / peak * 100.0
    drop_amount = peak - current
    threshold_breached = drop_pct >= threshold_pct

    return {
        "threshold_breached": threshold_breached,
        "drop_pct": round(drop_pct, 4),
        "drop_amount": round(drop_amount, 4),
        "peak_price": round(peak, 4),
        "current_price": round(current, 4),
        "candles_used": len(window_candles),
    }


# ---------------------------------------------------------------------------
# Regime reader (Framework 2 internal call)
# ---------------------------------------------------------------------------


async def _fetch_current_regime(polygon_api_key: str) -> dict[str, Any]:
    """Fetch regime from Framework 2.

    Returns {"available": bool, "regime": str | None}.
    F19 is never the source of regime; we only read it here for the
    alert context and the session record.
    """
    try:
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:8000", timeout=5.0
        ) as client:
            resp = await client.get(_F2_REGIME_PATH)
        if resp.status_code == 200:
            data = resp.json()
            regime_val = data.get("regime") or data.get("regime_state")
            return {"available": True, "regime": str(regime_val) if regime_val else None}
        return {"available": False, "regime": None}
    except Exception as exc:
        logger.debug("F19: regime fetch failed", extra={"error": repr(exc)})
        return {"available": False, "regime": None}


# ---------------------------------------------------------------------------
# Portfolio beta reader
# ---------------------------------------------------------------------------


async def _fetch_portfolio_betas(session: AsyncSession) -> dict[str, Any]:
    """Read beta vs NVDA for all tickers in portfolio_beta table.

    Returns {"available": bool, "betas": dict[str, float]}.
    A missing ticker in this table is treated as unknown beta → high risk →
    market orders blocked conservatively.
    """
    try:
        result = await session.execute(
            select(PortfolioBeta.ticker, PortfolioBeta.beta_vs_nvda)
        )
        rows = result.all()
        betas = {row.ticker.upper(): float(row.beta_vs_nvda) for row in rows}
        return {"available": True, "betas": betas}
    except Exception as exc:
        logger.warning("F19: beta DB query failed", extra={"error": repr(exc)})
        return {"available": False, "betas": {}, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Held tickers reader (from tickers / portfolio table)
# ---------------------------------------------------------------------------


async def _fetch_held_tickers(session: AsyncSession) -> dict[str, Any]:
    """Read all tickers currently held (non-zero position) from the DB.

    Returns {"available": bool, "tickers": list[str]}.
    The real portfolio table is 'tickers' (not 'portfolio_positions').
    """
    try:
        result = await session.execute(
            select(Ticker.ticker).where(Ticker.shares > 0)
        )
        rows = result.scalars().all()
        return {"available": True, "tickers": [str(t).upper() for t in rows]}
    except Exception as exc:
        logger.warning("F19: held tickers DB query failed", extra={"error": repr(exc)})
        return {"available": False, "tickers": [], "reason": str(exc)}


# ---------------------------------------------------------------------------
# Open buy orders reader
# ---------------------------------------------------------------------------


async def _fetch_open_buy_orders(session: AsyncSession) -> dict[str, Any]:
    """Return all open non-stop buy orders from gtc_orders.

    GtcOrder has no order_type column — all OPEN BUY orders are included.
    Stop-loss orders are on the SELL side, so BUY filter is sufficient.

    Returns {"available": bool, "orders": list[dict]}.
    """
    try:
        result = await session.execute(
            select(GtcOrder.id, GtcOrder.ticker, GtcOrder.status).where(
                GtcOrder.status.in_(["OPEN", "PENDING"]),
                GtcOrder.side == "BUY",
            )
        )
        rows = result.all()
        orders = [
            {"id": row.id, "ticker": str(row.ticker).upper(), "status": row.status}
            for row in rows
        ]
        return {"available": True, "orders": orders}
    except Exception as exc:
        logger.warning("F19: order DB query failed", extra={"error": repr(exc)})
        return {"available": False, "orders": [], "reason": str(exc)}


# ---------------------------------------------------------------------------
# Order pausing (append-only — idempotent)
# ---------------------------------------------------------------------------


async def _pause_orders(
    orders: list[dict[str, Any]],
    session_date: date,
    betas: dict[str, float],
    beta_threshold: float,
    session: AsyncSession,
) -> int:
    """Pause all provided buy orders for this session.

    Sets gtc_orders.status = 'PAUSED_F19' and inserts a tracking row
    into framework19_paused_orders.  The unique constraint on
    (session_date, order_id) makes this idempotent across re-evaluations.

    Returns the count of orders successfully paused.
    """
    paused_count = 0
    now_utc = datetime.now(UTC)

    for order in orders:
        order_id = order["id"]
        ticker = order.get("ticker", "")
        beta_val = betas.get(ticker)
        is_high = (beta_val is None) or (beta_val > beta_threshold)

        try:
            await session.execute(
                text(
                    "UPDATE gtc_orders "
                    "SET status = :status, updated_at = NOW() "
                    "WHERE id = :order_id"
                ),
                {"status": _PAUSED_STATUS, "order_id": order_id},
            )
            await session.execute(
                text(
                    "INSERT INTO framework19_paused_orders "
                    "(session_date, order_id, ticker, order_type, "
                    " beta_vs_nvda, is_high_beta, paused_at, review_status) "
                    "VALUES (:sd, :oid, :ticker, :otype, :beta, :high, :at, 'PENDING') "
                    "ON CONFLICT (session_date, order_id) DO NOTHING"
                ),
                {
                    "sd": session_date,
                    "oid": order_id,
                    "ticker": ticker,
                    "otype": "GTC",
                    "beta": Decimal(str(round(beta_val, 4))) if beta_val is not None else None,
                    "high": is_high,
                    "at": now_utc,
                },
            )
            paused_count += 1
        except Exception as exc:
            logger.warning(
                "F19: failed to pause order",
                extra={"order_id": order_id, "ticker": ticker, "error": repr(exc)},
            )

    return paused_count


# ---------------------------------------------------------------------------
# Session persistence (append-only, idempotent upsert)
# ---------------------------------------------------------------------------


async def _upsert_session(
    *,
    session_date: date,
    f19_triggered: bool,
    triggered_at: datetime | None,
    nvda_price: float | None,
    nvda_drop_pct: float | None,
    drop_window_minutes: int | None,
    peak_price: float | None,
    regime: str | None,
    orders_paused_count: int,
    high_beta_names: list[str],
    alert_sent_at: datetime | None,
    db_session: AsyncSession,
) -> None:
    """Upsert the framework19_sessions row for today.

    CRITICAL: This function must never set f19_triggered from True back to False.
    The row is created as CLEAR at the start of the session; if the kill switch
    fires it is updated to TRIGGERED and never reversed.
    """
    now_utc = datetime.now(UTC)
    high_beta_json = json.dumps(high_beta_names)

    existing = await db_session.execute(
        select(Framework19Session).where(Framework19Session.session_date == session_date)
    )
    row = existing.scalar_one_or_none()

    if row is None:
        row = Framework19Session(
            session_date=session_date,
            f19_triggered=f19_triggered,
            triggered_at=triggered_at,
            nvda_price_at_trigger=(
                Decimal(str(round(nvda_price, 4))) if nvda_price is not None else None
            ),
            nvda_drop_pct=(
                Decimal(str(round(nvda_drop_pct, 4))) if nvda_drop_pct is not None else None
            ),
            drop_window_minutes=drop_window_minutes,
            peak_price_in_window=(
                Decimal(str(round(peak_price, 4))) if peak_price is not None else None
            ),
            regime_at_trigger=regime,
            orders_paused_count=orders_paused_count,
            high_beta_names_blocked=high_beta_json if high_beta_names else None,
            alert_sent_at=alert_sent_at,
            alert_sent_within_minutes=(
                int((alert_sent_at - triggered_at).total_seconds() / 60)
                if alert_sent_at and triggered_at
                else None
            ),
            updated_at=now_utc,
        )
        db_session.add(row)
    else:
        # Never regress f19_triggered from True to False.
        if f19_triggered and not row.f19_triggered:
            row.f19_triggered = True
            row.triggered_at = triggered_at
            row.nvda_price_at_trigger = (
                Decimal(str(round(nvda_price, 4))) if nvda_price is not None else None
            )
            row.nvda_drop_pct = (
                Decimal(str(round(nvda_drop_pct, 4))) if nvda_drop_pct is not None else None
            )
            row.drop_window_minutes = drop_window_minutes
            row.peak_price_in_window = (
                Decimal(str(round(peak_price, 4))) if peak_price is not None else None
            )
            row.regime_at_trigger = regime
            row.orders_paused_count = orders_paused_count
            row.high_beta_names_blocked = high_beta_json if high_beta_names else None
            row.alert_sent_at = alert_sent_at
            row.alert_sent_within_minutes = (
                int((alert_sent_at - triggered_at).total_seconds() / 60)
                if alert_sent_at and triggered_at
                else None
            )
        row.updated_at = now_utc

    await db_session.commit()


# ---------------------------------------------------------------------------
# Alert sender (V1: structlog stub)
# ---------------------------------------------------------------------------


def _send_f19_alert(
    *,
    session_date: date,
    nvda_price: float | None,
    nvda_drop_pct: float | None,
    regime: str | None,
    orders_paused_count: int,
    high_beta_tickers: list[str],
) -> datetime:
    """Send the F19 kill-switch alert.

    V1: structlog only — no external notification service.
    Replace with real notification in production.

    Returns the UTC timestamp when the alert was sent.
    """
    alert_time = datetime.now(UTC)
    logger.critical(
        "F19_KILL_SWITCH_TRIGGERED",
        extra={
            "session_date": str(session_date),
            "nvda_price": nvda_price,
            "nvda_drop_pct": nvda_drop_pct,
            "regime": regime,
            "orders_paused_count": orders_paused_count,
            "high_beta_tickers": high_beta_tickers,
            "alert_sent_at": alert_time.isoformat(),
        },
    )
    return alert_time


# ---------------------------------------------------------------------------
# Session state reader — for consuming frameworks (F3, F4)
# ---------------------------------------------------------------------------


async def get_f19_simple(session: AsyncSession) -> Framework19SimpleResult:
    """Return lightweight F19 status for consuming frameworks (F3, F4).

    Reads the session row from DB — no Polygon call.
    This is ASYNC because F19 has no module-level cache.
    Consuming frameworks must await this function.

    F19 is the single source of truth for f19_active.
    F3 and F4 MUST NOT independently evaluate NVDA drop conditions.

    Conservative handling:
      - Market open + no session row yet → UNKNOWN (evaluation not yet run)
      - Market open + row found → read f19_triggered from DB
      - Market closed           → OUTSIDE_HOURS (safe to trade)
    """
    try:
        session_start = await _get_config_str(_CONFIG_KEY_SESSION_START, session)
        session_end = await _get_config_str(_CONFIG_KEY_SESSION_END, session)
        beta_threshold = await _get_config_float(_CONFIG_KEY_BETA_THRESHOLD, session)
        drop_threshold = await _get_config_float(_CONFIG_KEY_DROP_THRESHOLD, session)
    except RuntimeError as exc:
        logger.warning("F19: config unavailable in get_f19_simple", extra={"error": str(exc)})
        return Framework19SimpleResult(
            f19_status=F19Status.UNKNOWN,
            f19_active=None,
            all_ai_buys_blocked=True,
            high_beta_market_orders_blocked=True,
            beta_threshold=None,
            drop_pct=None,
            threshold_pct=None,
            polygon_available=False,
            data_gap_severity="CRITICAL",
            market_open=False,
        )

    market_open = _is_market_open(session_start, session_end)
    today = datetime.now(_ET_TZ).date()

    existing = await session.execute(
        select(Framework19Session).where(Framework19Session.session_date == today)
    )
    row = existing.scalar_one_or_none()

    if not market_open:
        return Framework19SimpleResult(
            f19_status=F19Status.OUTSIDE_HOURS,
            f19_active=False,
            all_ai_buys_blocked=False,
            high_beta_market_orders_blocked=False,
            beta_threshold=beta_threshold,
            drop_pct=float(row.nvda_drop_pct) if row and row.nvda_drop_pct else None,
            threshold_pct=drop_threshold,
            polygon_available=True,
            data_gap_severity="NONE",
            market_open=False,
        )

    if row is None:
        # Market is open but no evaluation has run yet today.
        return Framework19SimpleResult(
            f19_status=F19Status.UNKNOWN,
            f19_active=None,
            all_ai_buys_blocked=True,   # conservative — block until first evaluation
            high_beta_market_orders_blocked=True,
            beta_threshold=beta_threshold,
            drop_pct=None,
            threshold_pct=drop_threshold,
            polygon_available=False,
            data_gap_severity="MAJOR",
            market_open=True,
        )

    if row.f19_triggered:
        drop_pct = float(row.nvda_drop_pct) if row.nvda_drop_pct else None
        return Framework19SimpleResult(
            f19_status=F19Status.ACTIVE,
            f19_active=True,
            all_ai_buys_blocked=True,
            high_beta_market_orders_blocked=True,
            beta_threshold=beta_threshold,
            drop_pct=drop_pct,
            threshold_pct=drop_threshold,
            polygon_available=True,
            data_gap_severity="NONE",
            market_open=True,
        )

    return Framework19SimpleResult(
        f19_status=F19Status.CLEAR,
        f19_active=False,
        all_ai_buys_blocked=False,
        high_beta_market_orders_blocked=False,
        beta_threshold=beta_threshold,
        drop_pct=None,
        threshold_pct=drop_threshold,
        polygon_available=True,
        data_gap_severity="NONE",
        market_open=True,
    )


# ---------------------------------------------------------------------------
# Main evaluation — ZERO CACHE — fresh Polygon call every time
# ---------------------------------------------------------------------------


async def evaluate_framework19(session: AsyncSession) -> Framework19Result:
    """Evaluate Framework 19 — NVDA Kill Switch.

    ZERO CACHING.  Every call makes a fresh Polygon.io request.
    This is the hard invariant for F19.

    Flow:
      1. Read all config from atlas_config (never hardcoded).
      2. Check market hours.
      3. Check if already triggered today (DB read).
      4. Fetch NVDA intraday candles from Polygon (NO CACHE).
      5. Calculate drop using the pure helper.
      6. If threshold breached → trigger:
           a. Fetch betas, held tickers, open buy orders.
           b. Pause all buy orders.
           c. Upsert session record.
           d. Send alert.
      7. Return full Framework19Result.
    """
    now_utc = datetime.now(UTC)
    last_updated = now_utc.isoformat()
    warnings: list[str] = []

    settings = get_settings()
    polygon_api_key = settings.polygon_api_key or ""

    # ── Step 1: Read config ───────────────────────────────────────────────
    try:
        drop_threshold = await _get_config_float(_CONFIG_KEY_DROP_THRESHOLD, session)
        window_minutes = int(await _get_config_float(_CONFIG_KEY_WINDOW_MINUTES, session))
        beta_threshold = await _get_config_float(_CONFIG_KEY_BETA_THRESHOLD, session)
        session_start = await _get_config_str(_CONFIG_KEY_SESSION_START, session)
        session_end = await _get_config_str(_CONFIG_KEY_SESSION_END, session)
    except RuntimeError as exc:
        logger.error("F19: config unavailable — cannot evaluate", extra={"error": str(exc)})
        return Framework19Result(
            f19_status=F19Status.UNKNOWN,
            f19_active=None,
            severity=F19Severity.UNKNOWN,
            nvda_drop=NVDADropDetail(
                current_price=None,
                peak_price_in_window=None,
                drop_pct=None,
                drop_amount=None,
                window_minutes=None,
                threshold_pct=0.0,
                threshold_breached=False,
            ),
            market_open=False,
            session_date=str(datetime.now(_ET_TZ).date()),
            triggered_at=None,
            all_ai_buys_blocked=True,
            high_beta_market_orders_blocked=True,
            beta_threshold=None,
            affected_holdings=[],
            paused_orders_count=0,
            paused_orders=[],
            regime=None,
            regime_available=False,
            polygon_available=False,
            alert_sent=False,
            alert_sent_at=None,
            data_gap_severity="CRITICAL",
            warning_messages=[str(exc)],
            last_updated=last_updated,
        )

    market_open = _is_market_open(session_start, session_end)
    today_et = datetime.now(_ET_TZ).date()
    today_str = str(today_et)

    # ── Step 2: Outside hours ────────────────────────────────────────────
    if not market_open:
        return Framework19Result(
            f19_status=F19Status.OUTSIDE_HOURS,
            f19_active=False,
            severity=None,
            nvda_drop=NVDADropDetail(
                current_price=None,
                peak_price_in_window=None,
                drop_pct=None,
                drop_amount=None,
                window_minutes=window_minutes,
                threshold_pct=drop_threshold,
                threshold_breached=False,
            ),
            market_open=False,
            session_date=today_str,
            triggered_at=None,
            all_ai_buys_blocked=False,
            high_beta_market_orders_blocked=False,
            beta_threshold=beta_threshold,
            affected_holdings=[],
            paused_orders_count=0,
            paused_orders=[],
            regime=None,
            regime_available=False,
            polygon_available=True,
            alert_sent=False,
            alert_sent_at=None,
            data_gap_severity="NONE",
            warning_messages=[],
            last_updated=last_updated,
        )

    # ── Step 3: Check if already triggered today ─────────────────────────
    existing_q = await session.execute(
        select(Framework19Session).where(Framework19Session.session_date == today_et)
    )
    existing_session = existing_q.scalar_one_or_none()
    already_triggered = existing_session is not None and existing_session.f19_triggered

    # ── Step 4: Fetch NVDA candles (ZERO CACHE — always fresh) ───────────
    nvda_fetch = await _fetch_nvda_intraday_minutes(
        session_date=today_str,
        window_minutes=window_minutes,
        polygon_api_key=polygon_api_key,
    )
    polygon_available = nvda_fetch["available"]
    candles: list[dict[str, Any]] = nvda_fetch.get("candles") or []

    if not polygon_available:
        reason = nvda_fetch.get("reason", "Unknown Polygon error")
        warnings.append(f"Polygon unavailable: {reason}")
        logger.warning("F19: Polygon fetch failed", extra={"reason": reason})

        # Even if already triggered, we must report UNKNOWN when Polygon is down.
        # The session is ACTIVE but price data for display is unavailable.
        if already_triggered:
            triggered_at = (
                existing_session.triggered_at.isoformat()
                if existing_session and existing_session.triggered_at
                else None
            )
            return Framework19Result(
                f19_status=F19Status.ACTIVE,
                f19_active=True,
                severity=F19Severity.HIGH,
                nvda_drop=NVDADropDetail(
                    current_price=None,
                    peak_price_in_window=(
                        float(existing_session.peak_price_in_window)
                        if existing_session and existing_session.peak_price_in_window
                        else None
                    ),
                    drop_pct=(
                        float(existing_session.nvda_drop_pct)
                        if existing_session and existing_session.nvda_drop_pct
                        else None
                    ),
                    drop_amount=None,
                    window_minutes=window_minutes,
                    threshold_pct=drop_threshold,
                    threshold_breached=True,
                ),
                market_open=True,
                session_date=today_str,
                triggered_at=triggered_at,
                all_ai_buys_blocked=True,
                high_beta_market_orders_blocked=True,
                beta_threshold=beta_threshold,
                affected_holdings=[],
                paused_orders_count=(
                    existing_session.orders_paused_count if existing_session else 0
                ),
                paused_orders=[],
                regime=existing_session.regime_at_trigger if existing_session else None,
                regime_available=False,
                polygon_available=False,
                alert_sent=(
                    existing_session.alert_sent_at is not None if existing_session else False
                ),
                alert_sent_at=(
                    existing_session.alert_sent_at.isoformat()
                    if existing_session and existing_session.alert_sent_at
                    else None
                ),
                data_gap_severity="MAJOR",
                warning_messages=warnings,
                last_updated=last_updated,
            )

        return Framework19Result(
            f19_status=F19Status.UNKNOWN,
            f19_active=None,
            severity=F19Severity.UNKNOWN,
            nvda_drop=NVDADropDetail(
                current_price=None,
                peak_price_in_window=None,
                drop_pct=None,
                drop_amount=None,
                window_minutes=window_minutes,
                threshold_pct=drop_threshold,
                threshold_breached=False,
            ),
            market_open=True,
            session_date=today_str,
            triggered_at=None,
            all_ai_buys_blocked=True,
            high_beta_market_orders_blocked=True,
            beta_threshold=beta_threshold,
            affected_holdings=[],
            paused_orders_count=0,
            paused_orders=[],
            regime=None,
            regime_available=False,
            polygon_available=False,
            alert_sent=False,
            alert_sent_at=None,
            data_gap_severity="CRITICAL",
            warning_messages=warnings,
            last_updated=last_updated,
        )

    # ── Step 5: If already triggered — return active state with fresh price ─
    if already_triggered:
        drop_calc = calculate_nvda_drop(candles, drop_threshold, window_minutes)
        triggered_at = (
            existing_session.triggered_at.isoformat()
            if existing_session and existing_session.triggered_at
            else None
        )
        return Framework19Result(
            f19_status=F19Status.ACTIVE,
            f19_active=True,
            severity=F19Severity.HIGH,
            nvda_drop=NVDADropDetail(
                current_price=drop_calc.get("current_price"),
                peak_price_in_window=drop_calc.get("peak_price"),
                drop_pct=drop_calc.get("drop_pct"),
                drop_amount=drop_calc.get("drop_amount"),
                window_minutes=window_minutes,
                threshold_pct=drop_threshold,
                threshold_breached=True,
            ),
            market_open=True,
            session_date=today_str,
            triggered_at=triggered_at,
            all_ai_buys_blocked=True,
            high_beta_market_orders_blocked=True,
            beta_threshold=beta_threshold,
            affected_holdings=[],
            paused_orders_count=(
                existing_session.orders_paused_count if existing_session else 0
            ),
            paused_orders=[],
            regime=existing_session.regime_at_trigger if existing_session else None,
            regime_available=existing_session is not None and bool(
                existing_session.regime_at_trigger
            ),
            polygon_available=True,
            alert_sent=existing_session.alert_sent_at is not None if existing_session else False,
            alert_sent_at=(
                existing_session.alert_sent_at.isoformat()
                if existing_session and existing_session.alert_sent_at
                else None
            ),
            data_gap_severity="NONE",
            warning_messages=[],
            last_updated=last_updated,
        )

    # ── Step 6: Calculate drop ───────────────────────────────────────────
    drop_calc = calculate_nvda_drop(candles, drop_threshold, window_minutes)
    threshold_breached = drop_calc["threshold_breached"]

    if not threshold_breached:
        # Ensure a CLEAR session row exists so consuming frameworks see CLEAR.
        if existing_session is None:
            await _upsert_session(
                session_date=today_et,
                f19_triggered=False,
                triggered_at=None,
                nvda_price=drop_calc.get("current_price"),
                nvda_drop_pct=drop_calc.get("drop_pct"),
                drop_window_minutes=window_minutes,
                peak_price=drop_calc.get("peak_price"),
                regime=None,
                orders_paused_count=0,
                high_beta_names=[],
                alert_sent_at=None,
                db_session=session,
            )

        return Framework19Result(
            f19_status=F19Status.CLEAR,
            f19_active=False,
            severity=None,
            nvda_drop=NVDADropDetail(
                current_price=drop_calc.get("current_price"),
                peak_price_in_window=drop_calc.get("peak_price"),
                drop_pct=drop_calc.get("drop_pct"),
                drop_amount=drop_calc.get("drop_amount"),
                window_minutes=window_minutes,
                threshold_pct=drop_threshold,
                threshold_breached=False,
            ),
            market_open=True,
            session_date=today_str,
            triggered_at=None,
            all_ai_buys_blocked=False,
            high_beta_market_orders_blocked=False,
            beta_threshold=beta_threshold,
            affected_holdings=[],
            paused_orders_count=0,
            paused_orders=[],
            regime=None,
            regime_available=False,
            polygon_available=True,
            alert_sent=False,
            alert_sent_at=None,
            data_gap_severity="NONE",
            warning_messages=warnings,
            last_updated=last_updated,
        )

    # ── Step 7: Kill switch fires ─────────────────────────────────────────
    trigger_time = datetime.now(UTC)

    # Parallel fetch: betas + held tickers + open orders + regime.
    betas_task = asyncio.create_task(_fetch_portfolio_betas(session))
    held_task = asyncio.create_task(_fetch_held_tickers(session))
    orders_task = asyncio.create_task(_fetch_open_buy_orders(session))
    regime_task = asyncio.create_task(_fetch_current_regime(polygon_api_key))

    betas_result, held_result, orders_result, regime_result = await asyncio.gather(
        betas_task, held_task, orders_task, regime_task
    )

    betas: dict[str, float] = betas_result.get("betas") or {}
    held_tickers: list[str] = held_result.get("tickers") or []
    open_orders: list[dict[str, Any]] = orders_result.get("orders") or []
    regime = regime_result.get("regime")
    regime_available = regime_result.get("available", False)

    # Build affected holdings list.
    affected_holdings: list[AffectedHolding] = []
    high_beta_tickers: list[str] = []
    for ticker_sym in held_tickers:
        beta_val = betas.get(ticker_sym)
        # Missing beta → treat as unknown → is_high_beta = True (conservative).
        is_high = (beta_val is None) or (beta_val > beta_threshold)
        if is_high:
            high_beta_tickers.append(ticker_sym)
        affected_holdings.append(
            AffectedHolding(
                ticker=ticker_sym,
                beta_vs_nvda=beta_val,
                is_high_beta=is_high,
                market_orders_blocked=is_high,
                buy_orders_paused=True,
            )
        )

    # Pause all buy orders.
    if orders_result.get("available") and open_orders:
        paused_count = await _pause_orders(
            orders=open_orders,
            session_date=today_et,
            betas=betas,
            beta_threshold=beta_threshold,
            session=session,
        )
    else:
        paused_count = 0
        if not orders_result.get("available"):
            warnings.append("Order DB unavailable — manual review required")

    # Severity: CRITICAL if Crisis regime co-occurs, otherwise HIGH.
    severity = (
        F19Severity.CRITICAL
        if regime and "CRISIS" in str(regime).upper()
        else F19Severity.HIGH if regime_available
        else F19Severity.UNKNOWN
    )

    # Send alert (V1: structlog only).
    alert_sent_at = _send_f19_alert(
        session_date=today_et,
        nvda_price=drop_calc.get("current_price"),
        nvda_drop_pct=drop_calc.get("drop_pct"),
        regime=regime,
        orders_paused_count=paused_count,
        high_beta_tickers=high_beta_tickers,
    )

    # Persist session state.
    await _upsert_session(
        session_date=today_et,
        f19_triggered=True,
        triggered_at=trigger_time,
        nvda_price=drop_calc.get("current_price"),
        nvda_drop_pct=drop_calc.get("drop_pct"),
        drop_window_minutes=window_minutes,
        peak_price=drop_calc.get("peak_price"),
        regime=regime,
        orders_paused_count=paused_count,
        high_beta_names=high_beta_tickers,
        alert_sent_at=alert_sent_at,
        db_session=session,
    )

    # Load paused orders for response.
    paused_orders_q = await session.execute(
        select(Framework19PausedOrder).where(
            Framework19PausedOrder.session_date == today_et
        )
    )
    paused_rows = paused_orders_q.scalars().all()
    paused_orders_out = [
        PausedOrder(
            order_id=po.order_id,
            ticker=po.ticker,
            order_type=po.order_type,
            beta_vs_nvda=float(po.beta_vs_nvda) if po.beta_vs_nvda is not None else None,
            is_high_beta=po.is_high_beta,
            paused_at=po.paused_at.isoformat() if po.paused_at else "",
            review_status=OrderReviewStatus(po.review_status)
            if po.review_status in OrderReviewStatus._value2member_map_
            else OrderReviewStatus.PENDING_REVIEW,
        )
        for po in paused_rows
    ]

    return Framework19Result(
        f19_status=F19Status.ACTIVE,
        f19_active=True,
        severity=severity,
        nvda_drop=NVDADropDetail(
            current_price=drop_calc.get("current_price"),
            peak_price_in_window=drop_calc.get("peak_price"),
            drop_pct=drop_calc.get("drop_pct"),
            drop_amount=drop_calc.get("drop_amount"),
            window_minutes=window_minutes,
            threshold_pct=drop_threshold,
            threshold_breached=True,
        ),
        market_open=True,
        session_date=today_str,
        triggered_at=trigger_time.isoformat(),
        all_ai_buys_blocked=True,
        high_beta_market_orders_blocked=True,
        beta_threshold=beta_threshold,
        affected_holdings=affected_holdings,
        paused_orders_count=paused_count,
        paused_orders=paused_orders_out,
        regime=regime,
        regime_available=regime_available,
        polygon_available=True,
        alert_sent=True,
        alert_sent_at=alert_sent_at.isoformat(),
        data_gap_severity="NONE",
        warning_messages=warnings,
        last_updated=last_updated,
    )
