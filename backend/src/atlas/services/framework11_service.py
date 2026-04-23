"""Framework 11 — Cash Floor Enforcer service.

Ensures portfolio cash remains above the regime-driven floor (Section 14.1).
Queues all buy signals when the floor is violated.  Calculates the GTC
aggregate window to prevent simultaneous fills from breaching the floor.

Key design decisions
--------------------
Caching:
  Results are cached in-memory for 2 minutes (120 s).
  Short TTL because floor violations need near-real-time detection.
  Cache key: "f11_result".

Regime source:
  Framework 11 reads regime from RegimeModifierService directly.
  It NEVER independently calculates Brent or VIX.

NAV source:
  Current NAV = sum(tickers.position_value) + portfolio_config.cash_balance.
  Computed directly from the DB using the same approach as Framework 30.

Cash source:
  portfolio_config.cash_balance — existing singleton table.
  No separate portfolio_cash table needed.

GTC window:
  window_usd = cash_usd − (1.1 × floor_pct × current_nav)
  Only GTC buy orders with limit_price within 8 % of market price
  count toward the window.  Deep-OTM GTCs (> 8 % below market) are exempt.
  Polygon.io /v2/last/trade/{ticker} used for current prices.

Signal queue:
  When floor transitions from violated to compliant, all QUEUED signals in
  the signal_queue table are released (status → RELEASED).
  The actual queuing of signals is done by consuming frameworks (F4, LEAPS)
  when they read F11 status and find all_buys_blocked=True.

Floor map (Section 14.1 — never hardcoded):
  CRISIS HALT  → 30 %
  CAUTION      → 20 %
  SOFT CAUTION → 15 %
  CLEAR        → 10 % (first 14 days) / 8 % (settled)
  unknown      → 30 % (most restrictive)

Conservative defaults:
  Regime unavailable → 30 % floor, flag using_conservative_default.
  CLEAR with no transition date → 10 % floor (not 8 %).
  NAV unavailable → floor_violated=None, all_buys_blocked=True.
  Cash unavailable → floor_violated=None, all_buys_blocked=True.

Consuming frameworks:
  get_f11_simple() — synchronous read from cache; returns None if empty.
  Called by tranche_sizing router and leaps_service before add decisions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Final

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.gtc_order import GtcOrder
from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.signal_queue import SignalQueueEntry
from atlas.models.ticker import Ticker
from atlas.schemas.framework11 import (
    F11FloorStatus,
    Framework11Result,
    Framework11SimpleResult,
    GTCItem,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — all floor percentages come from spec; named constants, no magic
# ---------------------------------------------------------------------------

# Cache TTL: 2 minutes per spec (short for near-real-time violation detection).
_CACHE_TTL_SECONDS: Final[int] = 120

# GTC proximity threshold: GTCs within 8 % below market are near-money.
_GTC_PROXIMITY_THRESHOLD_PCT: Final[float] = 8.0

# GTC window safety buffer multiplier.
_GTC_WINDOW_BUFFER_MULTIPLIER: Final[float] = 1.1

# Floor percentages (as fractions, e.g. 0.15 = 15 %) — Section 14.1.
# These are NOT hardcoded business fallbacks; they are named constants
# for the spec-defined floor values that _get_floor_from_regime() returns.
_FLOOR_CRISIS_HALT: Final[float] = 0.30
_FLOOR_CAUTION: Final[float] = 0.20
_FLOOR_SOFT_CAUTION: Final[float] = 0.15
_FLOOR_CLEAR_TRANSITION: Final[float] = 0.10   # first 14 days after CLEAR
_FLOOR_CLEAR_SETTLED: Final[float] = 0.08      # after 14 days in CLEAR
_CLEAR_TRANSITION_DAYS: Final[int] = 14

# Conservative default floor when regime is unknown.
_FLOOR_CONSERVATIVE_DEFAULT: Final[float] = 0.30

# Regime name constants (as returned by RegimeModifierService).
_REGIME_CRISIS_HALT: Final[str] = "CRISIS HALT"
_REGIME_CAUTION: Final[str] = "CAUTION"
_REGIME_SOFT_CAUTION: Final[str] = "SOFT CAUTION"
_REGIME_CLEAR: Final[str] = "CLEAR"

# Polygon.io last trade endpoint for GTC proximity checks.
_POLYGON_LAST_TRADE_URL: Final[str] = (
    "https://api.polygon.io/v2/last/trade/{ticker}"
)

# Cache key.
_CACHE_KEY: Final[str] = "f11_result"

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# In-memory result cache: "f11_result" → (result, unix_timestamp)
_cache: dict[str, tuple[Framework11Result, float]] = {}

# Previous floor_violated state for signal release detection.
_prev_floor_violated: dict[str, bool | None] = {"value": None}


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> tuple[Framework11Result | None, float]:
    """Return (result, age_minutes) from cache, or (None, 0.0)."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None, 0.0
    result, fetched_at = entry
    age_minutes = (time.time() - fetched_at) / 60.0
    return result, age_minutes


def _cache_set(result: Framework11Result) -> None:
    """Store result in cache with current timestamp."""
    _cache[_CACHE_KEY] = (result, time.time())


def _cache_invalidate() -> None:
    """Remove cached result (called on POST /framework11/refresh)."""
    _cache.pop(_CACHE_KEY, None)


def get_f11_cached() -> Framework11Result | None:
    """Return the cached Framework 11 result, or None if absent / expired.

    Synchronous — safe to call from sync functions.
    Consuming frameworks (tranche sizing router, leaps service) use this.
    """
    result, age_minutes = _cache_get()
    if result is None:
        return None
    if age_minutes > _CACHE_TTL_SECONDS / 60.0:
        return None
    return result


def get_f11_simple() -> Framework11SimpleResult | None:
    """Return the lightweight Framework 11 status from cache, or None.

    Synchronous convenience accessor for consuming frameworks.
    Returns None when the cache is empty or expired — callers should
    treat None as floor_status=UNKNOWN / all_buys_blocked=True.
    """
    cached = get_f11_cached()
    if cached is None:
        return None
    return Framework11SimpleResult(
        floor_status=cached.floor_status,
        floor_violated=cached.floor_violated,
        all_buys_blocked=cached.all_buys_blocked,
        floor_pct=cached.floor_pct,
        cash_pct=cached.cash_pct,
        shortfall_usd=cached.shortfall_usd,
        gtc_window_usd=cached.gtc_window_usd,
        gtc_oversubscribed=cached.gtc_oversubscribed,
        data_gap_severity=cached.data_gap_severity,
    )


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects
# ---------------------------------------------------------------------------


def _get_floor_from_regime(
    regime: str | None,
    clear_transition_date: date | None,
    today: date | None = None,
) -> tuple[float, str]:
    """Map regime string to (floor_fraction, source_key). Pure function.

    Parameters
    ----------
    regime:
        Regime name from RegimeModifierService (e.g. "SOFT CAUTION").
        Handles both spaced (codebase) and underscored (spec) variants.
    clear_transition_date:
        Date when portfolio entered CLEAR regime (from portfolio_config).
    today:
        Override today for deterministic testing; defaults to date.today().

    Returns
    -------
    (floor_fraction, source_key)
        floor_fraction: 0.0–1.0 (e.g. 0.15 for 15 %)
        source_key: human-readable provenance string
    """
    effective_today = today if today is not None else date.today()

    if regime is None:
        return _FLOOR_CONSERVATIVE_DEFAULT, "conservative_default_no_regime"

    # Normalise to handle both "SOFT CAUTION" and "SOFT_CAUTION" variants.
    normalised = regime.strip().upper().replace("_", " ")

    if normalised in ("CRISIS HALT", "CRISIS"):
        return _FLOOR_CRISIS_HALT, "crisis_halt_spec"

    if normalised == "CAUTION":
        return _FLOOR_CAUTION, "caution_spec"

    if normalised in ("SOFT CAUTION", "SOFT-CAUTION"):
        return _FLOOR_SOFT_CAUTION, "soft_caution_spec"

    if normalised == "CLEAR":
        if clear_transition_date is None:
            return _FLOOR_CLEAR_TRANSITION, "conservative_default_no_transition_date"
        days_since = (effective_today - clear_transition_date).days
        if days_since <= _CLEAR_TRANSITION_DAYS:
            return _FLOOR_CLEAR_TRANSITION, "clear_first_2_weeks"
        return _FLOOR_CLEAR_SETTLED, "clear_established"

    # Unknown regime — apply most restrictive floor.
    return _FLOOR_CONSERVATIVE_DEFAULT, "conservative_default_unknown_regime"


def _compute_cash_pct(cash_usd: float, current_nav: float) -> float:
    """Return cash as a percentage of NAV. Pure function."""
    return (cash_usd / current_nav) * 100.0


def _compute_gtc_window(
    cash_usd: float,
    floor_fraction: float,
    current_nav: float,
) -> float:
    """Calculate the GTC aggregate window in USD. Pure function.

    window = cash − (1.1 × floor_fraction × current_nav)
    """
    return cash_usd - (_GTC_WINDOW_BUFFER_MULTIPLIER * floor_fraction * current_nav)


def _classify_gtc_proximity(
    limit_price: float,
    current_price: float,
) -> tuple[float, bool, bool]:
    """Classify a GTC order by proximity to current market price. Pure function.

    Returns (proximity_pct, is_near_money, is_exempt).
    proximity_pct = (current_price − limit_price) / current_price × 100.
    near-money:  proximity_pct ≤ 8 %
    exempt:      proximity_pct > 8 %
    """
    proximity_pct = (current_price - limit_price) / current_price * 100.0
    is_near_money = proximity_pct <= _GTC_PROXIMITY_THRESHOLD_PCT
    return proximity_pct, is_near_money, not is_near_money


# ---------------------------------------------------------------------------
# Async data fetchers
# ---------------------------------------------------------------------------


async def _fetch_regime(
    session: AsyncSession,
    polygon_api_key: str,
    alphavantage_api_key: str,
    transcript_api_key: str,
    benzinga_api_key: str,
    unusual_whales_api_key: str,
    sec_api_key: str,
) -> dict[str, Any]:
    """Fetch regime from RegimeModifierService. Returns dict with 'available', 'rule', 'clear_transition_date'."""
    try:
        from atlas.services.regime_modifier_service import RegimeModifierService

        svc = RegimeModifierService(
            polygon_api_key=polygon_api_key,
            alphavantage_api_key=alphavantage_api_key,
            transcript_api_key=transcript_api_key,
            benzinga_api_key=benzinga_api_key,
            unusual_whales_api_key=unusual_whales_api_key,
            sec_api_key=sec_api_key,
            session=session,
        )
        result = await svc.compute_regime_modifier("PORTFOLIO", geopolitical_state="NONE")
        rule = result.rule if hasattr(result, "rule") else None
        return {"available": rule is not None, "rule": rule}
    except Exception as exc:
        logger.warning("F11: regime fetch failed", extra={"error": repr(exc)})
        return {"available": False, "rule": None, "error": repr(exc)}


async def _fetch_nav_and_cash(session: AsyncSession) -> dict[str, Any]:
    """Fetch current NAV and cash balance from the portfolio DB.

    NAV = sum(position_value from tickers) + cash_balance from portfolio_config.
    Returns dict with 'available', 'current_nav', 'cash_usd', 'clear_transition_date'.
    """
    try:
        config = await session.get(PortfolioConfig, PORTFOLIO_CONFIG_ROW_ID)
        if config is None:
            return {
                "available": False,
                "current_nav": None,
                "cash_usd": None,
                "clear_transition_date": None,
            }

        cash_usd = float(config.cash_balance)
        clear_transition_date: date | None = getattr(config, "clear_transition_date", None)

        all_values_result = await session.execute(select(Ticker.position_value))
        invested: Decimal = sum(
            (v or Decimal("0")) for v in all_values_result.scalars().all()
        ) or Decimal("0")

        current_nav = float(invested) + cash_usd

        return {
            "available": True,
            "current_nav": current_nav if current_nav > 0 else None,
            "cash_usd": cash_usd,
            "clear_transition_date": clear_transition_date,
        }
    except Exception as exc:
        logger.warning("F11: nav/cash fetch failed", extra={"error": repr(exc)})
        return {
            "available": False,
            "current_nav": None,
            "cash_usd": None,
            "clear_transition_date": None,
            "error": repr(exc),
        }


async def _fetch_open_gtc_orders(session: AsyncSession) -> dict[str, Any]:
    """Fetch all open GTC BUY orders from the gtc_orders table."""
    try:
        result = await session.execute(
            select(GtcOrder).where(
                GtcOrder.status == "OPEN",
                GtcOrder.side == "BUY",
            )
        )
        orders = result.scalars().all()
        return {
            "available": True,
            "orders": [
                {
                    "ticker": o.ticker,
                    "limit_price": float(o.limit_price),
                    "quantity": o.quantity,
                    "notional_usd": float(o.limit_price) * o.quantity,
                }
                for o in orders
            ],
        }
    except Exception as exc:
        logger.warning("F11: GTC orders fetch failed", extra={"error": repr(exc)})
        return {"available": False, "orders": [], "error": repr(exc)}


async def _fetch_gtc_prices(
    tickers: list[str],
    polygon_api_key: str,
    client: httpx.AsyncClient,
) -> dict[str, float | None]:
    """Fetch current prices for GTC tickers from Polygon.io last trade endpoint.

    Returns dict mapping ticker → price (None when unavailable).
    Fetches all tickers in parallel.
    """
    if not tickers:
        return {}

    async def _single(ticker: str) -> tuple[str, float | None]:
        try:
            response = await client.get(
                _POLYGON_LAST_TRADE_URL.format(ticker=ticker.upper()),
                params={"apiKey": polygon_api_key},
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                price = (data.get("results") or {}).get("p")
                return ticker, float(price) if price is not None else None
            return ticker, None
        except Exception:
            return ticker, None

    results = await asyncio.gather(*[_single(t) for t in tickers], return_exceptions=True)
    prices: dict[str, float | None] = {}
    for item in results:
        if isinstance(item, Exception):
            continue
        t, p = item  # type: ignore[misc]
        prices[t] = p
    # Ensure all tickers have an entry (None if failed).
    for t in tickers:
        if t not in prices:
            prices[t] = None
    return prices


async def _fetch_queued_signals(session: AsyncSession) -> list[dict[str, Any]]:
    """Read all QUEUED signals from signal_queue table."""
    try:
        result = await session.execute(
            select(SignalQueueEntry).where(SignalQueueEntry.status == "QUEUED")
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "ticker": r.ticker,
                "action": r.action,
                "score": float(r.score) if r.score is not None else None,
                "queue_reason": r.queue_reason,
                "status": r.status,
                "queued_at": r.queued_at.isoformat() if r.queued_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("F11: signal queue fetch failed", extra={"error": repr(exc)})
        return []


async def _release_queued_signals(session: AsyncSession) -> int:
    """Update all QUEUED signals to RELEASED.

    Called when floor transitions from violated to compliant.
    Returns number of signals released.
    """
    try:
        result = await session.execute(
            update(SignalQueueEntry)
            .where(SignalQueueEntry.status == "QUEUED")
            .values(
                status="RELEASED",
                released_at=datetime.now(tz=timezone.utc),
            )
            .returning(SignalQueueEntry.id)
        )
        released_ids = result.scalars().all()
        await session.flush()
        count = len(released_ids)
        if count > 0:
            logger.info("F11: released %d queued signals (floor restored)", count)
        return count
    except Exception as exc:
        logger.warning("F11: signal release failed", extra={"error": repr(exc)})
        return 0


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def evaluate_framework11(
    session: AsyncSession,
    polygon_api_key: str = "",
    alphavantage_api_key: str = "",
    transcript_api_key: str = "",
    benzinga_api_key: str = "",
    unusual_whales_api_key: str = "",
    sec_api_key: str = "",
) -> Framework11Result:
    """Evaluate the Framework 11 cash floor status.

    Steps
    -----
    1. Return from cache if fresh (< 2 min).
    2. Fetch regime + nav/cash in parallel.
    3. Compute floor percentage from regime.
    4. Check floor compliance.
    5. Calculate GTC window.
    6. Classify each open GTC by proximity.
    7. Check GTC oversubscription.
    8. Read queued signal count.
    9. Release queued signals if floor just restored.
    10. Cache and return result.
    """
    # Step 1 — Cache hit check.
    cached, age_minutes = _cache_get()
    if cached is not None and age_minutes <= _CACHE_TTL_SECONDS / 60.0:
        return Framework11Result(
            **{**cached.model_dump(), "cache_hit": True, "data_age_minutes": int(age_minutes)}
        )

    warnings: list[str] = []
    using_conservative = False

    # Step 2 — Parallel fetch of regime + nav/cash.
    regime_data, nav_cash_data = await asyncio.gather(
        _fetch_regime(
            session,
            polygon_api_key,
            alphavantage_api_key,
            transcript_api_key,
            benzinga_api_key,
            unusual_whales_api_key,
            sec_api_key,
        ),
        _fetch_nav_and_cash(session),
        return_exceptions=True,
    )

    if isinstance(regime_data, Exception):
        regime_data = {"available": False, "rule": None}
    if isinstance(nav_cash_data, Exception):
        nav_cash_data = {"available": False, "current_nav": None, "cash_usd": None, "clear_transition_date": None}

    f2_available: bool = regime_data.get("available", False)
    f30_available: bool = nav_cash_data.get("available", False)

    # Step 3 — Regime and floor.
    regime: str | None = regime_data.get("rule")
    clear_transition_date: date | None = nav_cash_data.get("clear_transition_date")

    if not f2_available or regime is None:
        using_conservative = True
        warnings.append(
            "Framework 2 unavailable — "
            "applying CRISIS HALT floor (30%) as conservative default."
        )

    floor_fraction, floor_source = _get_floor_from_regime(regime, clear_transition_date)
    floor_pct_value = floor_fraction * 100.0  # e.g. 15.0 for 15 %

    if "conservative_default" in floor_source:
        using_conservative = True

    clear_transition_days: int | None = None
    if regime is not None and regime.upper().replace("_", " ") == "CLEAR" and clear_transition_date:
        clear_transition_days = (date.today() - clear_transition_date).days

    # Step 4 — NAV and cash from DB.
    current_nav: float | None = nav_cash_data.get("current_nav")
    cash_usd: float | None = nav_cash_data.get("cash_usd")
    cash_db_available: bool = nav_cash_data.get("available", False)

    if not f30_available or current_nav is None:
        warnings.append(
            "NAV unavailable — cannot calculate cash as % NAV. "
            "Verify manually before any buy."
        )
        result = _build_unknown_result(
            regime=regime,
            floor_pct_value=floor_pct_value,
            floor_source=floor_source,
            using_conservative=using_conservative,
            clear_transition_days=clear_transition_days,
            current_nav=None,
            cash_usd=None,
            f2_available=f2_available,
            f30_available=False,
            cash_db_available=cash_db_available,
            gtc_db_available=False,
            warnings=warnings,
            gap_severity="MAJOR" if f2_available else "CRITICAL",
        )
        _cache_set(result)
        return result

    if not cash_db_available or cash_usd is None:
        warnings.append(
            "Cash balance unavailable — cannot verify floor compliance. "
            "No buys permitted until cash data is restored."
        )
        result = _build_unknown_result(
            regime=regime,
            floor_pct_value=floor_pct_value,
            floor_source=floor_source,
            using_conservative=using_conservative,
            clear_transition_days=clear_transition_days,
            current_nav=current_nav,
            cash_usd=None,
            f2_available=f2_available,
            f30_available=f30_available,
            cash_db_available=False,
            gtc_db_available=False,
            warnings=warnings,
            gap_severity="CRITICAL",
        )
        _cache_set(result)
        return result

    # Step 4 (cont) — Fetch GTC orders in parallel with price lookups.
    gtc_data = await _fetch_open_gtc_orders(session)
    gtc_db_available: bool = gtc_data.get("available", False)
    orders: list[dict[str, Any]] = gtc_data.get("orders", [])

    # Step 5 — Floor compliance check.
    cash_pct = _compute_cash_pct(cash_usd, current_nav)

    floor_violated = cash_pct < floor_pct_value
    shortfall_pct: float | None = None
    shortfall_usd: float | None = None
    buffer_pct: float | None = None
    buffer_usd: float | None = None
    floor_status: F11FloorStatus

    if floor_violated:
        shortfall_pct = round(floor_pct_value - cash_pct, 2)
        shortfall_usd = round((shortfall_pct / 100.0) * current_nav, 2)
        all_buys_blocked = True
        floor_status = F11FloorStatus.VIOLATED
        warnings.append(
            f"CASH FLOOR VIOLATED — "
            f"cash {cash_pct:.1f}% below {floor_pct_value:.0f}% floor. "
            f"Shortfall: ${shortfall_usd:,.0f}. All buy signals queued."
        )
    else:
        buffer_pct = round(cash_pct - floor_pct_value, 2)
        buffer_usd = round((buffer_pct / 100.0) * current_nav, 2)
        all_buys_blocked = False
        floor_status = F11FloorStatus.COMPLIANT

    # Step 6 — GTC window.
    gtc_window_usd_raw = _compute_gtc_window(cash_usd, floor_fraction, current_nav)
    gtc_window_usd = round(gtc_window_usd_raw, 2)
    gtc_window_negative = gtc_window_usd <= 0.0

    if gtc_window_negative:
        warnings.append(
            "GTC window is zero or negative — "
            "cannot safely hold any near-money GTCs at current cash level and floor."
        )

    # Step 7 — Classify GTC orders by proximity.
    gtc_items: list[GTCItem] = []
    gtc_near_money_total = 0.0
    gtc_near_money_count = 0
    gtc_exempt_count = 0
    gtc_price_missing_count = 0

    if orders and polygon_api_key:
        unique_tickers = list({o["ticker"] for o in orders})
        async with httpx.AsyncClient() as client:
            prices = await _fetch_gtc_prices(unique_tickers, polygon_api_key, client)

        for order in orders:
            ticker = order["ticker"]
            limit_price = order["limit_price"]
            quantity = order["quantity"]
            notional = limit_price * quantity
            current_price = prices.get(ticker)
            price_missing = current_price is None

            if price_missing:
                gtc_price_missing_count += 1
                proximity_pct_val: float | None = None
                is_near_money: bool | None = True   # conservative: treat as near-money
                is_exempt: bool | None = False
                gtc_near_money_total += notional
                gtc_near_money_count += 1
                warnings.append(
                    f"{ticker} GTC proximity unknown — price missing. "
                    f"Treated as near-money conservatively."
                )
            else:
                proximity_pct_val, is_near_money, is_exempt_bool = _classify_gtc_proximity(
                    limit_price, current_price
                )
                is_exempt = is_exempt_bool
                if is_near_money:
                    gtc_near_money_total += notional
                    gtc_near_money_count += 1
                else:
                    gtc_exempt_count += 1

            gtc_items.append(
                GTCItem(
                    ticker=ticker,
                    limit_price=limit_price,
                    quantity=quantity,
                    notional_usd=notional,
                    current_price=current_price,
                    proximity_pct=round(proximity_pct_val, 2) if proximity_pct_val is not None else None,
                    is_near_money=is_near_money,
                    is_exempt=is_exempt,
                    price_missing=price_missing,
                    price_missing_reason="Polygon.io price unavailable" if price_missing else None,
                )
            )
    elif orders and not polygon_api_key:
        # No API key — treat all GTCs as near-money (conservative).
        for order in orders:
            ticker = order["ticker"]
            limit_price = order["limit_price"]
            quantity = order["quantity"]
            notional = limit_price * quantity
            gtc_near_money_total += notional
            gtc_near_money_count += 1
            gtc_price_missing_count += 1
            warnings.append(
                f"{ticker} GTC proximity unknown — Polygon API key not configured. "
                f"Treated as near-money conservatively."
            )
            gtc_items.append(
                GTCItem(
                    ticker=ticker,
                    limit_price=limit_price,
                    quantity=quantity,
                    notional_usd=notional,
                    current_price=None,
                    proximity_pct=None,
                    is_near_money=True,
                    is_exempt=False,
                    price_missing=True,
                    price_missing_reason="Polygon API key not configured",
                )
            )

    # Step 8 — GTC oversubscription check.
    gtc_oversubscribed: bool | None = None
    gtc_excess_usd: float | None = None
    gtc_remaining_usd: float | None = None

    if orders:
        if gtc_window_negative:
            gtc_oversubscribed = True
            gtc_excess_usd = round(gtc_near_money_total, 2)
            gtc_remaining_usd = 0.0
        elif gtc_near_money_total > gtc_window_usd:
            gtc_oversubscribed = True
            gtc_excess_usd = round(gtc_near_money_total - gtc_window_usd, 2)
            gtc_remaining_usd = 0.0
            warnings.append(
                f"GTC oversubscribed by ${gtc_excess_usd:,.0f}. "
                f"Reduce GTC shares or raise cash."
            )
        else:
            gtc_oversubscribed = False
            gtc_remaining_usd = round(gtc_window_usd - gtc_near_money_total, 2)
    elif gtc_window_usd is not None:
        gtc_oversubscribed = False
        gtc_remaining_usd = round(gtc_window_usd, 2)

    # Step 9 — Read queued signals.
    queued_signals = await _fetch_queued_signals(session)

    # Step 9b — Release signals if floor just restored.
    prev_violated = _prev_floor_violated.get("value")
    if prev_violated is True and floor_violated is False:
        released_count = await _release_queued_signals(session)
        if released_count > 0:
            warnings.append(
                f"Floor restored — {released_count} queued signal(s) released for re-evaluation."
            )
            # Refresh queued list (should now be empty for released ones).
            queued_signals = await _fetch_queued_signals(session)

    _prev_floor_violated["value"] = floor_violated

    # Step 10 — Data gap severity.
    if not f2_available and not f30_available:
        gap_severity = "CRITICAL"
    elif not f2_available or not f30_available:
        gap_severity = "MAJOR"
    elif not cash_db_available:
        gap_severity = "CRITICAL"
    elif gtc_price_missing_count > 0:
        gap_severity = "PARTIAL"
    elif using_conservative:
        gap_severity = "PARTIAL"
    else:
        gap_severity = "NONE"

    result = Framework11Result(
        floor_status=floor_status,
        floor_violated=floor_violated,
        all_buys_blocked=all_buys_blocked,
        regime=regime,
        floor_pct=floor_pct_value,
        floor_pct_source=floor_source,
        using_conservative_default=using_conservative,
        clear_transition_days=clear_transition_days,
        cash_usd=cash_usd,
        cash_pct=round(cash_pct, 2),
        current_nav=current_nav,
        shortfall_pct=shortfall_pct,
        shortfall_usd=shortfall_usd,
        buffer_pct=buffer_pct,
        buffer_usd=buffer_usd,
        gtc_window_usd=gtc_window_usd,
        gtc_window_negative=gtc_window_negative,
        gtc_near_money_total_usd=round(gtc_near_money_total, 2),
        gtc_oversubscribed=gtc_oversubscribed,
        gtc_excess_usd=gtc_excess_usd,
        gtc_remaining_usd=gtc_remaining_usd,
        gtc_items=gtc_items,
        gtc_near_money_count=gtc_near_money_count,
        gtc_exempt_count=gtc_exempt_count,
        gtc_price_missing_count=gtc_price_missing_count,
        queued_signals_count=len(queued_signals),
        signal_queue=queued_signals,
        f2_available=f2_available,
        f30_available=f30_available,
        cash_db_available=cash_db_available,
        gtc_db_available=gtc_db_available,
        data_gap_severity=gap_severity,
        warning_messages=warnings,
        last_updated=datetime.now(tz=timezone.utc).isoformat(),
        data_age_minutes=0,
        cache_hit=False,
    )

    _cache_set(result)
    return result


# ---------------------------------------------------------------------------
# Helper — build UNKNOWN result with consistent null-filling
# ---------------------------------------------------------------------------


def _build_unknown_result(
    *,
    regime: str | None,
    floor_pct_value: float,
    floor_source: str,
    using_conservative: bool,
    clear_transition_days: int | None,
    current_nav: float | None,
    cash_usd: float | None,
    f2_available: bool,
    f30_available: bool,
    cash_db_available: bool,
    gtc_db_available: bool,
    warnings: list[str],
    gap_severity: str,
) -> Framework11Result:
    """Build a Framework11Result in UNKNOWN state (data unavailable). Pure-ish helper."""
    return Framework11Result(
        floor_status=F11FloorStatus.UNKNOWN,
        floor_violated=None,
        all_buys_blocked=True,
        regime=regime,
        floor_pct=floor_pct_value,
        floor_pct_source=floor_source,
        using_conservative_default=using_conservative,
        clear_transition_days=clear_transition_days,
        cash_usd=cash_usd,
        cash_pct=None,
        current_nav=current_nav,
        shortfall_pct=None,
        shortfall_usd=None,
        buffer_pct=None,
        buffer_usd=None,
        gtc_window_usd=None,
        gtc_window_negative=False,
        gtc_near_money_total_usd=None,
        gtc_oversubscribed=None,
        gtc_excess_usd=None,
        gtc_remaining_usd=None,
        gtc_items=[],
        gtc_near_money_count=0,
        gtc_exempt_count=0,
        gtc_price_missing_count=0,
        queued_signals_count=0,
        signal_queue=[],
        f2_available=f2_available,
        f30_available=f30_available,
        cash_db_available=cash_db_available,
        gtc_db_available=gtc_db_available,
        data_gap_severity=gap_severity,
        warning_messages=warnings,
        last_updated=datetime.now(tz=timezone.utc).isoformat(),
        data_age_minutes=0,
        cache_hit=False,
    )
