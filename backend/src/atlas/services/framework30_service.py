"""Framework 30 — Max Drawdown Gate service.

Calculates the portfolio's current drawdown from its 90-day peak NAV and
gates all ADD activity when drawdown exceeds 15%.

Gate states:
  NORMAL     — drawdown < 15%: all activity permitted, normal sizing
  CARVEOUT   — 15% ≤ drawdown < 25%: adds blocked; LEAPS allowed up to 0.5% NAV
  HARD_HALT  — drawdown ≥ 25%: everything halted including LEAPS carve-out
  UNKNOWN    — NAV history unavailable; cannot determine drawdown

NAV source:
  Current NAV = sum(position_value from tickers table) + cash_balance from portfolio_config.
  Peak NAV = MAX(nav_value) from nav_history over last 90 days.
  On each evaluation the current NAV is written to nav_history (upsert by date).

Recovery protocol:
  Once drawdown drops below 15% after a CARVEOUT/HARD_HALT, a 5-day confirmation
  window starts.  If drawdown stays below 15% for 5 consecutive days, NORMAL state
  resumes.  Recovery start date is tracked in a module-level dict (not in the DB).

Caching:
  Results are cached in-memory for 5 minutes (300 s).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Final

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.nav_history import NavHistory
from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.framework30 import (
    DrawdownState,
    Framework30DrawdownState,
    Framework30Result,
    PositionNavItem,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes

# Drawdown thresholds (as percentages, e.g. 15.0 = 15%).
_CARVEOUT_THRESHOLD_PCT: Final[float] = 15.0
_HARD_HALT_THRESHOLD_PCT: Final[float] = 25.0

# Recovery confirmation window in calendar days.
_RECOVERY_DAYS_REQUIRED: Final[int] = 5

# LEAPS position cap during CARVEOUT state (as % of NAV per position).
_LEAPS_CARVEOUT_CAP_PCT: Final[float] = 0.5

# Peak NAV lookback window in days.
_PEAK_LOOKBACK_DAYS: Final[int] = 90

# Polygon aggs URL for live price refresh.
_POLYGON_SNAPSHOT_URL: Final[str] = (
    "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
)

# Price stale threshold — positions last synced more than 30 minutes ago.
_PRICE_STALE_MINUTES: Final[int] = 30

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# In-memory result cache: "f30_result" -> (result, unix_timestamp)
_cache: dict[str, tuple[Framework30Result, float]] = {}

# Recovery protocol: "recovery_start" -> ISO date string (YYYY-MM-DD)
_recovery_state: dict[str, Any] = {}

# Hard halt manual confirmations: date_str -> {confirmed: bool, reason: str}
_hard_halt_confirmations: dict[str, dict[str, Any]] = {}

_CACHE_KEY: Final[str] = "f30_result"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> tuple[Framework30Result | None, float]:
    """Return (result, age_minutes) from cache, or (None, 0)."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None, 0.0
    result, fetched_at = entry
    age_minutes = (time.time() - fetched_at) / 60.0
    return result, age_minutes


def _cache_set(result: Framework30Result) -> None:
    """Store result in cache with current timestamp."""
    _cache[_CACHE_KEY] = (result, time.time())


def _cache_invalidate() -> None:
    """Remove cached result."""
    _cache.pop(_CACHE_KEY, None)


# ---------------------------------------------------------------------------
# Pure calculation helpers
# ---------------------------------------------------------------------------


def _compute_drawdown_pct(current_nav: float, peak_nav: float) -> float:
    """Return drawdown as a positive percentage (e.g. 12.5 = 12.5%).

    Returns 0.0 if current_nav >= peak_nav (no drawdown).
    """
    if peak_nav <= 0:
        return 0.0
    dd = (peak_nav - current_nav) / peak_nav * 100.0
    return max(0.0, dd)


def _determine_drawdown_state(
    drawdown_pct: float | None,
    recovery_active: bool,
) -> DrawdownState:
    """Map drawdown percentage to gate state. Pure function."""
    if drawdown_pct is None:
        return DrawdownState.UNKNOWN

    if drawdown_pct >= _HARD_HALT_THRESHOLD_PCT:
        return DrawdownState.HARD_HALT

    if drawdown_pct >= _CARVEOUT_THRESHOLD_PCT:
        return DrawdownState.CARVEOUT

    # Below 15% — but if recovery protocol is active, treat as CARVEOUT
    # until the full 5-day confirmation window elapses.
    if recovery_active:
        return DrawdownState.CARVEOUT

    return DrawdownState.NORMAL


def _compute_recovery_progress(
    recovery_start_iso: str,
) -> tuple[int, int]:
    """Return (days_elapsed, days_remaining) for the recovery window."""
    start = date.fromisoformat(recovery_start_iso)
    today = date.today()
    elapsed = (today - start).days
    remaining = max(0, _RECOVERY_DAYS_REQUIRED - elapsed)
    return elapsed, remaining


def _build_drawdown_state_response(
    result: Framework30Result,
) -> Framework30DrawdownState:
    """Build the lightweight drawdown state from a full result. Pure function."""
    return Framework30DrawdownState(
        drawdown_state=result.drawdown_state,
        drawdown_pct=result.drawdown_pct,
        adds_permitted=result.adds_permitted,
        leaps_permitted=result.leaps_permitted,
        leaps_position_cap_pct=result.leaps_position_cap_pct,
        sizing_multiplier=result.sizing_multiplier,
        hard_halt_active=result.hard_halt_active,
        data_complete=result.nav_data_complete,
    )


def _state_to_permissions(
    state: DrawdownState,
) -> tuple[bool, bool, float | None, bool, bool, float | None]:
    """Return (adds_permitted, leaps_permitted, leaps_cap_pct, all_halted, hard_halt, sizing_mult).

    Pure function — maps state to gate flags.
    """
    if state == DrawdownState.NORMAL:
        return True, True, None, False, False, 1.0
    if state == DrawdownState.CARVEOUT:
        return False, True, _LEAPS_CARVEOUT_CAP_PCT, False, False, 0.5
    if state == DrawdownState.HARD_HALT:
        return False, False, None, True, True, 0.0
    # UNKNOWN — conservative default: block adds, allow nothing definitive
    return False, False, None, False, False, None


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


async def _fetch_live_price(
    ticker: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> float | None:
    """Fetch the latest trade price from Polygon snapshot endpoint."""
    try:
        response = await client.get(
            _POLYGON_SNAPSHOT_URL.format(ticker=ticker.upper()),
            params={"apiKey": api_key},
            timeout=8.0,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        snapshot = data.get("ticker", {})
        day = snapshot.get("day", {})
        last_trade = snapshot.get("lastTrade", {})
        price = (
            last_trade.get("p")
            or day.get("c")
            or snapshot.get("prevDay", {}).get("c")
        )
        return float(price) if price else None
    except Exception as exc:
        logger.warning("Polygon snapshot failed", extra={"ticker": ticker, "error": repr(exc)})
        return None


async def _write_nav_snapshot(
    session: AsyncSession,
    nav_value: float,
) -> None:
    """Write current NAV to nav_history (upsert by date)."""
    today = date.today()
    today_decimal = Decimal(str(round(nav_value, 2)))

    # Compute peak_90d.
    ninety_days_ago = today - timedelta(days=_PEAK_LOOKBACK_DAYS)
    peak_result = await session.execute(
        select(func.max(NavHistory.nav_value)).where(
            NavHistory.date >= ninety_days_ago
        )
    )
    peak_row = peak_result.scalar()
    peak_decimal: Decimal | None = (
        Decimal(str(peak_row)) if peak_row is not None else None
    )
    effective_peak = max(today_decimal, peak_decimal) if peak_decimal else today_decimal

    drawdown_decimal: Decimal | None = None
    if effective_peak > 0:
        dd = (effective_peak - today_decimal) / effective_peak * 100
        drawdown_decimal = Decimal(str(round(float(dd), 4)))

    # Upsert: update if date exists, insert otherwise.
    existing = await session.execute(
        select(NavHistory).where(NavHistory.date == today)
    )
    row = existing.scalar_one_or_none()

    if row is not None:
        row.nav_value = today_decimal
        row.peak_90d = effective_peak
        row.drawdown_pct = drawdown_decimal
    else:
        new_row = NavHistory(
            date=today,
            nav_value=today_decimal,
            peak_90d=effective_peak,
            drawdown_pct=drawdown_decimal,
        )
        session.add(new_row)

    await session.commit()


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def evaluate_framework30(
    session: AsyncSession,
    polygon_api_key: str = "",
    refresh_prices: bool = False,
) -> Framework30Result:
    """Evaluate portfolio drawdown and return gate status.

    Args:
        session: Async DB session for reading tickers, portfolio_config, nav_history.
        polygon_api_key: Polygon API key (used for live price refresh when refresh_prices=True).
        refresh_prices: When True, fetch current prices from Polygon for all positions.
    """
    cached, age_minutes = _cache_get()
    if cached is not None and age_minutes <= _CACHE_TTL_SECONDS / 60.0 and not refresh_prices:
        return Framework30Result(
            **{**cached.model_dump(), "cache_hit": True}
        )

    warning_messages: list[str] = []
    position_nav_items: list[PositionNavItem] = []
    stale_positions: list[str] = []
    missing_positions: list[str] = []

    # 1. Read all tickers from DB.
    tickers_result = await session.execute(select(Ticker))
    tickers: list[Ticker] = list(tickers_result.scalars().all())

    # 2. Read portfolio config (cash balance).
    config_result = await session.execute(
        select(PortfolioConfig).where(PortfolioConfig.id == PORTFOLIO_CONFIG_ROW_ID)
    )
    config = config_result.scalar_one_or_none()
    cash_balance = float(config.cash_balance) if config else 0.0
    if config is None:
        warning_messages.append("Portfolio config unavailable — cash balance assumed 0.")

    # 3. Optionally refresh prices from Polygon.
    live_prices: dict[str, float] = {}
    if refresh_prices and polygon_api_key:
        async with httpx.AsyncClient() as client:
            price_tasks = [
                _fetch_live_price(t.ticker, polygon_api_key, client)
                for t in tickers
            ]
            prices_raw = await asyncio.gather(*price_tasks, return_exceptions=True)
        for ticker_model, price_raw in zip(tickers, prices_raw):
            if isinstance(price_raw, float):
                live_prices[ticker_model.ticker] = price_raw

    # 4. Build per-position NAV items.
    current_nav_total = 0.0
    nav_data_complete = True

    for t in tickers:
        shares_val = float(t.shares) if t.shares is not None else None
        live_price = live_prices.get(t.ticker)
        stored_price = float(t.current_price) if t.current_price is not None else None
        price = live_price or stored_price

        price_stale = live_price is None  # If we used stored price it may be stale
        value_usd: float | None = None
        excluded = False
        exclude_reason: str | None = None

        if shares_val is not None and price is not None:
            value_usd = shares_val * price
            current_nav_total += value_usd
        elif shares_val is None:
            excluded = True
            exclude_reason = "Missing shares data"
            missing_positions.append(t.ticker)
            nav_data_complete = False
        elif price is None:
            excluded = True
            exclude_reason = "Missing price data"
            missing_positions.append(t.ticker)
            nav_data_complete = False
            warning_messages.append(f"{t.ticker}: price unavailable, excluded from NAV.")

        if price_stale and price is not None:
            stale_positions.append(t.ticker)

        position_nav_items.append(
            PositionNavItem(
                ticker=t.ticker,
                shares=shares_val,
                price=price,
                price_stale=price_stale,
                price_age_min=None,  # V1: not tracking update timestamps
                value_usd=value_usd,
                excluded=excluded,
                exclude_reason=exclude_reason,
            )
        )

    current_nav = current_nav_total + cash_balance

    # 5. Get peak NAV from nav_history.
    ninety_days_ago = date.today() - timedelta(days=_PEAK_LOOKBACK_DAYS)
    peak_result = await session.execute(
        select(
            func.max(NavHistory.nav_value),
            NavHistory.date,
        ).where(NavHistory.date >= ninety_days_ago).group_by(NavHistory.date)
    )
    peak_rows = peak_result.all()

    peak_nav_90d: float | None = None
    peak_nav_date: str | None = None

    if peak_rows:
        # Find the row with the maximum value.
        best = max(peak_rows, key=lambda r: r[0])
        peak_nav_90d = float(best[0])
        peak_nav_date = best[1].isoformat()

    # 6. Compute drawdown.
    drawdown_pct: float | None = None
    drawdown_usd: float | None = None
    peak_data_source = "nav_history"

    if peak_nav_90d is not None:
        drawdown_pct = _compute_drawdown_pct(current_nav, peak_nav_90d)
        drawdown_usd = peak_nav_90d - current_nav
    else:
        peak_data_source = "unavailable"
        warning_messages.append(
            "No 90-day NAV history found — drawdown state is UNKNOWN. "
            "NAV snapshots accumulate automatically on each F30 evaluation."
        )

    # 7. Recovery protocol.
    recovery_start = _recovery_state.get("recovery_start")
    recovery_active = False
    recovery_days_elapsed: int | None = None
    recovery_days_remaining: int | None = None

    if recovery_start is not None:
        elapsed, remaining = _compute_recovery_progress(recovery_start)
        recovery_days_elapsed = elapsed
        recovery_days_remaining = remaining
        if remaining > 0:
            recovery_active = True
        else:
            # Recovery window complete — clear state.
            _recovery_state.clear()

    # 8. Determine state.
    state = _determine_drawdown_state(drawdown_pct, recovery_active)

    # Track recovery start when dropping below CARVEOUT from a previous halt.
    prev_result, _ = _cache_get()
    if prev_result is not None:
        prev_state = prev_result.drawdown_state
        if (
            prev_state in (DrawdownState.CARVEOUT, DrawdownState.HARD_HALT)
            and state == DrawdownState.NORMAL
            and not recovery_active
        ):
            _recovery_state["recovery_start"] = date.today().isoformat()
            recovery_active = True
            recovery_days_elapsed = 0
            recovery_days_remaining = _RECOVERY_DAYS_REQUIRED
            state = DrawdownState.CARVEOUT

    (
        adds_permitted,
        leaps_permitted,
        leaps_position_cap_pct,
        all_signals_halted,
        hard_halt_active,
        sizing_multiplier,
    ) = _state_to_permissions(state)

    limit_orders_cancel = hard_halt_active

    # 9. Write nav snapshot to DB (best-effort, non-blocking on failure).
    if current_nav > 0:
        try:
            await _write_nav_snapshot(session, current_nav)
        except Exception as exc:
            logger.warning("NAV snapshot write failed", extra={"error": repr(exc)})

    now = datetime.now(tz=timezone.utc)
    result = Framework30Result(
        current_nav=round(current_nav, 2) if current_nav > 0 else None,
        peak_nav_90d=round(peak_nav_90d, 2) if peak_nav_90d else None,
        peak_nav_date=peak_nav_date,
        drawdown_pct=round(drawdown_pct, 4) if drawdown_pct is not None else None,
        drawdown_usd=round(drawdown_usd, 2) if drawdown_usd is not None else None,
        drawdown_state=state,
        adds_permitted=adds_permitted,
        leaps_permitted=leaps_permitted,
        leaps_position_cap_pct=leaps_position_cap_pct,
        all_signals_halted=all_signals_halted,
        hard_halt_active=hard_halt_active,
        limit_orders_cancel=limit_orders_cancel,
        recovery_active=recovery_active if recovery_start else None,
        recovery_start_date=recovery_start,
        recovery_days_elapsed=recovery_days_elapsed,
        recovery_days_remaining=recovery_days_remaining,
        sizing_multiplier=sizing_multiplier,
        position_nav_items=position_nav_items,
        stale_positions=stale_positions,
        missing_positions=missing_positions,
        nav_data_complete=nav_data_complete and len(missing_positions) == 0,
        peak_data_source=peak_data_source,
        data_age_minutes=0,
        warning_messages=warning_messages,
        cache_hit=False,
    )

    _cache_set(result)
    return result


def get_drawdown_state() -> Framework30DrawdownState | None:
    """Return lightweight drawdown state from cache without triggering fetch.

    Returns None if no cached result exists.
    """
    cached, _ = _cache_get()
    if cached is None:
        return None
    return _build_drawdown_state_response(cached)


def set_hard_halt_confirmed(confirmed: bool, reason: str) -> None:
    """Record a manual hard-halt confirmation.  Keyed by today's date."""
    today = date.today().isoformat()
    _hard_halt_confirmations[today] = {"confirmed": confirmed, "reason": reason}
    _cache_invalidate()
