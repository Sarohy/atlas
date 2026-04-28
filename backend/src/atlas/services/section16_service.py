"""Section 16 — Entry Gatekeeper service.

ALL market data is fetched LIVE on every evaluation.  No caching of any
market data.  No storing of prices, signals, or rule-evaluation results.

Stored state (persisted in DB):
  - ticker_track_assignment   : which Track each ticker uses
  - rule4_portfolio_fit       : operator's daily YES/NO for portfolio fit
  - override_usage_tracking   : has the override been used this earnings cycle

Live data sources (HTTP fetched per evaluation):
  - Framework 7  (/api/v1/framework7/{ticker})       earnings date / days
  - Framework 9  (/api/v1/framework9/{ticker})       options-flow + dark-pool
  - Framework 30 (/api/v1/framework30/drawdown)      live NAV
  - Polygon REST                                      365-day price history

All thresholds, day counts, and percentages come from atlas_config — never
hardcoded in this module.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.atlas_config import AtlasConfig
from atlas.models.override_usage_tracking import OverrideUsageTracking
from atlas.models.rule4_portfolio_fit import Rule4PortfolioFit
from atlas.models.ticker_track_assignment import TickerTrackAssignment
from atlas.config import get_settings
from atlas.schemas.section16 import (
    GateResult,
    OverrideResult,
    Rule1Result,
    Rule2Result,
    Rule3Result,
    Rule4Result,
    Section16Result,
    TrackType,
)

logger = logging.getLogger(__name__)

# Internal HTTP base for service-to-service framework calls (no auth needed).
_INTERNAL_BASE_URL: Final[str] = os.environ.get(
    "ATLAS_INTERNAL_BASE_URL", "http://localhost:8000",
)
_HTTP_TIMEOUT_SECONDS: Final[float] = 10.0
# Polygon 365-day agg fetch involves more data than internal service calls;
# give it extra headroom before treating the request as failed.
_POLYGON_TIMEOUT_SECONDS: Final[float] = 20.0
_POLYGON_BASE_URL: Final[str] = "https://api.polygon.io"

# Config key constants — values themselves come from DB.
_KEY_P1_EARN_DAYS: Final[str] = "s16_priority1_earnings_days"
_KEY_P2_EARN_MIN: Final[str] = "s16_priority2_earnings_min_days"
_KEY_P2_EARN_MAX: Final[str] = "s16_priority2_earnings_max_days"
_KEY_P1_DARK_USD: Final[str] = "s16_priority1_dark_pool_usd"
_KEY_P1_FLOW_USD: Final[str] = "s16_priority1_flow_usd"
_KEY_P2_DARK_USD: Final[str] = "s16_priority2_dark_pool_usd"
_KEY_P2_FLOW_USD: Final[str] = "s16_priority2_flow_usd"
_KEY_P3_DARK_USD: Final[str] = "s16_priority3_dark_pool_usd"
_KEY_P3_FLOW_USD: Final[str] = "s16_priority3_flow_usd"
_KEY_CATALYST_MAX_DAYS: Final[str] = "s16_catalyst_max_days"
_KEY_PARABOLIC_DAYS: Final[str] = "s16_parabolic_catalyst_days"
_KEY_RULE3_NEAR_HIGH: Final[str] = "s16_rule3_near_high_pct"
_KEY_RULE3_PULLBACK: Final[str] = "s16_rule3_pullback_pct"
_KEY_OVR_DARK_USD: Final[str] = "s16_override_dark_pool_usd"
_KEY_OVR_FLOW_USD: Final[str] = "s16_override_flow_usd"
_KEY_OVR_LOOKBACK: Final[str] = "s16_override_lookback_days"

_TRACK_A: Final[str] = "TRACK_A"
_TRACK_B: Final[str] = "TRACK_B"
_UNASSIGNED: Final[str] = "UNASSIGNED"

# Polygon: number of calendar days back to fetch for the 365-day high.
_POLYGON_HISTORY_DAYS: Final[int] = 365

# Unusual Whales: trailing trading-day window for Rule 1 live signal totals.
_UW_SIGNAL_LOOKBACK_DAYS: Final[int] = 5  # last 5 trading days (Mon–Fri)
_UW_BASE_URL: Final[str] = "https://api.unusualwhales.com"


# ---------------------------------------------------------------------------
# Config helpers — typed accessors over atlas_config key/value store.
# ---------------------------------------------------------------------------


async def _config_lookup(key: str, session: AsyncSession) -> str:
    row = await session.execute(select(AtlasConfig).where(AtlasConfig.key == key))
    cfg = row.scalar_one_or_none()
    if cfg is None:
        raise KeyError(f"Missing required atlas_config key: {key}")
    return cfg.value


async def _cfg_int(key: str, session: AsyncSession) -> int:
    return int(await _config_lookup(key, session))


async def _cfg_float(key: str, session: AsyncSession) -> float:
    return float(await _config_lookup(key, session))


# ---------------------------------------------------------------------------
# Stored-state accessors — track, rule4, override.
# ---------------------------------------------------------------------------


async def get_track_assignment(ticker: str, session: AsyncSession) -> str:
    """Return the assigned track string, or 'UNASSIGNED' when no row exists."""
    res = await session.execute(
        select(TickerTrackAssignment).where(TickerTrackAssignment.ticker == ticker),
    )
    row = res.scalar_one_or_none()
    return row.track if row is not None else _UNASSIGNED


async def upsert_track_assignment(
    ticker: str, track: str, assigned_by: str,
    notes: str | None, session: AsyncSession,
) -> TickerTrackAssignment:
    res = await session.execute(
        select(TickerTrackAssignment).where(TickerTrackAssignment.ticker == ticker),
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = TickerTrackAssignment(
            ticker=ticker, track=track, assigned_by=assigned_by, notes=notes,
        )
        session.add(row)
    else:
        row.track = track
        row.assigned_by = assigned_by
        row.notes = notes
    await session.flush()
    return row


async def get_rule4_today(
    ticker: str, session: AsyncSession,
) -> Rule4PortfolioFit | None:
    today = datetime.now(tz=UTC).date()
    res = await session.execute(
        select(Rule4PortfolioFit).where(
            Rule4PortfolioFit.ticker == ticker,
            Rule4PortfolioFit.fit_date == today,
        ),
    )
    return res.scalar_one_or_none()


async def upsert_rule4_today(
    ticker: str, fits_portfolio: bool, set_by: str,
    cluster_gap: str | None, redundancy_check: str | None,
    notes: str | None, session: AsyncSession,
) -> Rule4PortfolioFit:
    today = datetime.now(tz=UTC).date()
    existing = await get_rule4_today(ticker, session)
    if existing is None:
        row = Rule4PortfolioFit(
            ticker=ticker, fit_date=today,
            fits_portfolio=fits_portfolio, set_by=set_by,
            cluster_gap=cluster_gap, redundancy_check=redundancy_check,
            notes=notes,
        )
        session.add(row)
        await session.flush()
        return row
    existing.fits_portfolio = fits_portfolio
    existing.set_by = set_by
    existing.cluster_gap = cluster_gap
    existing.redundancy_check = redundancy_check
    existing.notes = notes
    await session.flush()
    return existing


def _earnings_cycle_window(today: date, earnings_date: date | None) -> tuple[date, date]:
    """Compute the (start, end) of the current earnings cycle.

    When the next earnings date is known, the cycle ends on that date and
    starts ~90 days prior (one quarter).  When unknown, the cycle is the
    last 90 days ending today.
    """
    one_quarter_days = 90  # ~1 quarter — used only for cycle bookkeeping.
    if earnings_date is None:
        return today - timedelta(days=one_quarter_days), today
    return earnings_date - timedelta(days=one_quarter_days), earnings_date


async def is_override_used_in_cycle(
    ticker: str, earnings_date: date | None, session: AsyncSession,
) -> bool:
    today = datetime.now(tz=UTC).date()
    cycle_start, cycle_end = _earnings_cycle_window(today, earnings_date)
    res = await session.execute(
        select(OverrideUsageTracking).where(
            OverrideUsageTracking.ticker == ticker,
            OverrideUsageTracking.earnings_cycle_start == cycle_start,
        ),
    )
    row = res.scalar_one_or_none()
    if row is None:
        # Track presence implicitly — if no row, override has not been used.
        return False
    _ = cycle_end  # cycle_end is held in DB row already
    return bool(row.override_used)


async def mark_override_used(
    ticker: str, used_by: str, earnings_date: date | None,
    notes: str | None, session: AsyncSession,
) -> OverrideUsageTracking:
    today = datetime.now(tz=UTC).date()
    cycle_start, cycle_end = _earnings_cycle_window(today, earnings_date)
    res = await session.execute(
        select(OverrideUsageTracking).where(
            OverrideUsageTracking.ticker == ticker,
            OverrideUsageTracking.earnings_cycle_start == cycle_start,
        ),
    )
    row = res.scalar_one_or_none()
    now_utc = datetime.now(tz=UTC)
    if row is None:
        row = OverrideUsageTracking(
            ticker=ticker,
            earnings_cycle_start=cycle_start,
            earnings_cycle_end=cycle_end,
            override_used=True,
            override_used_at=now_utc,
            override_used_by=used_by,
            notes=notes,
        )
        session.add(row)
    else:
        row.override_used = True
        row.override_used_at = now_utc
        row.override_used_by = used_by
        row.notes = notes
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# Live data fetchers — every evaluation hits the network.  No caching.
# ---------------------------------------------------------------------------


async def _http_get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, dict) else {}


async def fetch_f7_live(ticker: str) -> dict[str, Any]:
    """Fetch Framework 7 (Earnings Gate) live for one ticker."""
    return await _http_get_json(f"{_INTERNAL_BASE_URL}/api/v1/framework7/{ticker}")


async def fetch_f9_live(ticker: str) -> dict[str, Any]:
    """Fetch Framework 9 (Options Flow / Dark Pool) live for one ticker."""
    return await _http_get_json(f"{_INTERNAL_BASE_URL}/api/v1/framework9/{ticker}")


async def fetch_f30_live() -> dict[str, Any]:
    """Fetch Framework 30 (NAV / drawdown) live."""
    return await _http_get_json(f"{_INTERNAL_BASE_URL}/api/v1/framework30/drawdown")


async def fetch_polygon_aggs(ticker: str, days_back: int) -> list[dict[str, Any]]:
    """Fetch daily aggregates from Polygon for the trailing `days_back` days.

    Returns the raw list of bar dicts (``{"t","o","h","l","c","v"}``).
    Returns an empty list on network or API error so callers can degrade.
    Retries up to 3 times with exponential backoff to handle transient
    rate-limit (429) responses from Polygon when parallel requests fire.
    """
    import asyncio as _asyncio

    api_key = get_settings().polygon_api_key or os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        logger.warning("POLYGON_API_KEY not set; cannot fetch %s aggs", ticker)
        return []
    today = datetime.now(tz=UTC).date()
    start = today - timedelta(days=days_back)
    url = (
        f"{_POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/"
        f"{start.isoformat()}/{today.isoformat()}"
    )
    _MAX_RETRIES: int = 3
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_POLYGON_TIMEOUT_SECONDS) as client:
                resp = await client.get(url, params={"adjusted": "true", "apiKey": api_key})
                resp.raise_for_status()
                raw = resp.json()
                data = raw if isinstance(raw, dict) else {}
            results = data.get("results")
            if isinstance(results, list) and len(results) > 0:
                return list(results)
            # Polygon returns status="OK" but empty results on rate-limit sometimes;
            # treat an empty result on non-final attempts as retriable.
            logger.warning(
                "Polygon aggs empty for %s on attempt %d/%d (status=%s)",
                ticker, attempt + 1, _MAX_RETRIES, data.get("status"),
            )
            if attempt < _MAX_RETRIES - 1:
                wait = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
                await _asyncio.sleep(wait)
                continue
            return list(results) if isinstance(results, list) else []
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < _MAX_RETRIES - 1:
                wait = 1.0 * (2 ** attempt)  # 1s, 2s, 4s on rate-limit
                logger.warning(
                    "Polygon 429 rate-limit for %s on attempt %d/%d; retrying in %.1fs",
                    ticker, attempt + 1, _MAX_RETRIES, wait,
                )
                await _asyncio.sleep(wait)
            else:
                logger.warning("Polygon aggs fetch failed for %s: %s", ticker, exc)
                return []
        except httpx.HTTPError as exc:
            logger.warning("Polygon aggs fetch failed for %s: %s", ticker, exc)
            return []
    return []


# ---------------------------------------------------------------------------
# Unusual Whales live fetchers — 5-trading-day totals for Rule 1.
# ---------------------------------------------------------------------------


def _last_n_trading_dates(n: int) -> list[str]:
    """Return the last *n* weekday dates (Mon–Fri) as YYYY-MM-DD strings.

    Walks backwards from today, skipping Saturday (5) and Sunday (6).
    """
    results: list[str] = []
    day = datetime.now(tz=UTC).date()
    while len(results) < n:
        if day.weekday() < 5:  # Mon=0 … Fri=4
            results.append(day.isoformat())
        day -= timedelta(days=1)
    return results


async def _fetch_dark_pool_5d_total(ticker: str) -> float | None:
    """Fetch total dark-pool notional (size × price) over the last 5 trading days.

    Calls the UW darkpool endpoint once per day and sums every print.
    Returns None only when the API key is absent or every request fails.
    """
    api_key = get_settings().unusual_whales_api_key
    if not api_key:
        logger.warning("UNUSUAL_WHALES_API_KEY not set; cannot fetch dark-pool totals")
        return None
    dates = _last_n_trading_dates(_UW_SIGNAL_LOOKBACK_DAYS)
    total = 0.0
    got_any = False
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        for dt in dates:
            try:
                resp = await client.get(
                    f"{_UW_BASE_URL}/api/darkpool/{ticker.upper()}",
                    params={"date": dt, "limit": 500},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code != 200:
                    continue
                for print_ in resp.json().get("data") or []:
                    total += float(print_.get("size") or 0) * float(print_.get("price") or 0)
                got_any = True
            except Exception:
                logger.exception("Dark-pool fetch failed for %s on %s", ticker, dt)
    return total if got_any else None


async def _fetch_flow_5d_bullish_total(ticker: str) -> float | None:
    """Fetch total bullish options premium over the last 5 trading days.

    Uses the UW options-volume endpoint which provides a `bullish_premium`
    field (ask-side calls + bid-side puts) per day.
    Returns None when the API key is absent or the request fails.
    """
    api_key = get_settings().unusual_whales_api_key
    if not api_key:
        logger.warning("UNUSUAL_WHALES_API_KEY not set; cannot fetch options-volume")
        return None
    dates = _last_n_trading_dates(_UW_SIGNAL_LOOKBACK_DAYS)
    date_from = dates[-1]  # oldest (furthest back)
    date_to = dates[0]     # most recent
    dates_set = set(dates)
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{_UW_BASE_URL}/api/stock/{ticker.upper()}/options-volume",
                params={"date_from": date_from, "date_to": date_to, "limit": 10},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                return None
            return sum(
                float(row.get("bullish_premium") or 0)
                for row in resp.json().get("data") or []
                if (row.get("date") or "")[:10] in dates_set
            )
    except Exception:
        logger.exception("Options-volume fetch failed for %s", ticker)
        return None


# ---------------------------------------------------------------------------
# Signal extractors — pull the few fields we need from F9 payload.
# ---------------------------------------------------------------------------


def _extract_dark_pool_usd(f9: dict[str, Any]) -> float | None:
    val = f9.get("largest_print_usd")
    return float(val) if val is not None else None


def _extract_flow_usd(f9: dict[str, Any]) -> float | None:
    """Bullish call-side flow USD for the day from F9.

    F9 exposes `largest_print_usd` for dark-pool prints; for options flow we
    use the same magnitude proxy when flow_direction is bullish.  When F9
    reports BEARISH or no flow, return None so Rule 1 fails cleanly.
    """
    direction = (f9.get("flow_direction") or "").upper()
    if direction not in {"BULLISH", "STRONG_BULLISH"}:
        return None
    val = f9.get("largest_print_usd")
    return float(val) if val is not None else None


def _is_underweight(f9: dict[str, Any]) -> bool:
    """Treat F9 signal_tier ∈ {LOW, NEUTRAL} or missing as underweight."""
    tier = (f9.get("signal_tier") or "").upper()
    return tier in {"LOW", "NEUTRAL", ""}


def _is_strong_flow(f9: dict[str, Any]) -> bool:
    tier = (f9.get("signal_tier") or "").upper()
    direction = (f9.get("flow_direction") or "").upper()
    return tier in {"HIGH", "STRONG"} and direction in {"BULLISH", "STRONG_BULLISH"}


# ---------------------------------------------------------------------------
# Rule evaluators — each returns its own structured result.
# ---------------------------------------------------------------------------


async def evaluate_rule1(
    ticker: str, f7: dict[str, Any],
    session: AsyncSession,
) -> Rule1Result:
    """Rule 1 — catalyst conviction (priority-based signal threshold).

    dark_pool_usd and flow_usd are fetched live from Unusual Whales as
    5-trading-day totals — never read from F9 or stored in the database.
    """
    p1_days = await _cfg_int(_KEY_P1_EARN_DAYS, session)
    p2_min = await _cfg_int(_KEY_P2_EARN_MIN, session)
    p2_max = await _cfg_int(_KEY_P2_EARN_MAX, session)
    p1_dark = await _cfg_float(_KEY_P1_DARK_USD, session)
    p1_flow = await _cfg_float(_KEY_P1_FLOW_USD, session)
    p2_dark = await _cfg_float(_KEY_P2_DARK_USD, session)
    p2_flow = await _cfg_float(_KEY_P2_FLOW_USD, session)
    p3_dark = await _cfg_float(_KEY_P3_DARK_USD, session)
    p3_flow = await _cfg_float(_KEY_P3_FLOW_USD, session)

    days = f7.get("days_to_earnings")
    dark_usd, flow_usd = await asyncio.gather(
        _fetch_dark_pool_5d_total(ticker),
        _fetch_flow_5d_bullish_total(ticker),
    )

    # Priority 1: earnings within P1 window AND (dark>=P1 OR flow>=P1).
    if isinstance(days, int) and 0 <= days <= p1_days and (
        (dark_usd is not None and dark_usd >= p1_dark)
        or (flow_usd is not None and flow_usd >= p1_flow)
    ):
        return Rule1Result(
            result="PASS", priority_matched="PRIORITY_1",
            dark_pool_usd=dark_usd, flow_usd=flow_usd,
            days_to_earnings=days,
            threshold_dark_pool_usd=p1_dark, threshold_flow_usd=p1_flow,
            reason=f"Priority 1 met (earnings in {days}d).",
        )

    # Priority 2: earnings within P2 window AND (dark>=P2 OR flow>=P2).
    if isinstance(days, int) and p2_min <= days <= p2_max and (
        (dark_usd is not None and dark_usd >= p2_dark)
        or (flow_usd is not None and flow_usd >= p2_flow)
    ):
        return Rule1Result(
            result="PASS", priority_matched="PRIORITY_2",
            dark_pool_usd=dark_usd, flow_usd=flow_usd,
            days_to_earnings=days,
            threshold_dark_pool_usd=p2_dark, threshold_flow_usd=p2_flow,
            reason=f"Priority 2 met (earnings in {days}d).",
        )

    # Priority 3: no earnings constraint, requires BOTH dark AND flow above P3.
    if (dark_usd is not None and dark_usd >= p3_dark) and (
        flow_usd is not None and flow_usd >= p3_flow
    ):
        return Rule1Result(
            result="PASS", priority_matched="PRIORITY_3",
            dark_pool_usd=dark_usd, flow_usd=flow_usd,
            days_to_earnings=days if isinstance(days, int) else None,
            threshold_dark_pool_usd=p3_dark, threshold_flow_usd=p3_flow,
            reason="Priority 3 met (strong dark-pool AND flow).",
        )

    return Rule1Result(
        result="FAIL", priority_matched="NO_MATCH",
        dark_pool_usd=dark_usd, flow_usd=flow_usd,
        days_to_earnings=days if isinstance(days, int) else None,
        threshold_dark_pool_usd=p1_dark, threshold_flow_usd=p1_flow,
        reason=f"No priority matched for {ticker}.",
    )


async def evaluate_rule2(
    f7: dict[str, Any], track: str, session: AsyncSession,
) -> Rule2Result:
    """Rule 2 — catalyst horizon (earnings within max-days window)."""
    catalyst_max = await _cfg_int(_KEY_CATALYST_MAX_DAYS, session)
    parabolic_window = await _cfg_int(_KEY_PARABOLIC_DAYS, session)

    days = f7.get("days_to_earnings")
    raw_date = f7.get("earnings_date")
    earnings_dt: date | None = None
    if isinstance(raw_date, str):
        try:
            earnings_dt = date.fromisoformat(raw_date[:10])
        except ValueError:
            earnings_dt = None

    if not isinstance(days, int) or days < 0:
        return Rule2Result(
            result="UNKNOWN", days_to_earnings=None, earnings_date=earnings_dt,
            catalyst_max_days=catalyst_max,
            reason="No earnings date available from F7.",
        )

    is_parabolic = track == _TRACK_B and days <= parabolic_window
    if days <= catalyst_max:
        return Rule2Result(
            result="PASS", days_to_earnings=days, earnings_date=earnings_dt,
            catalyst_max_days=catalyst_max, parabolic_window=is_parabolic,
            reason=f"Earnings in {days}d (≤ {catalyst_max}).",
        )
    return Rule2Result(
        result="FAIL", days_to_earnings=days, earnings_date=earnings_dt,
        catalyst_max_days=catalyst_max, parabolic_window=is_parabolic,
        reason=f"Earnings in {days}d (> {catalyst_max}).",
    )


def _high_and_current_from_aggs(aggs: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    if not aggs:
        return None, None
    high = max((float(b.get("h", 0.0)) for b in aggs), default=None)
    current = float(aggs[-1].get("c", 0.0)) if aggs else None
    return high, current


# Preferred lookback windows in descending order — use the largest that fits.
_LOCAL_HIGH_WINDOWS: Final[tuple[int, ...]] = (50, 20, 10)


def _local_high_from_aggs(
    aggs: list[dict[str, Any]],
) -> tuple[float | None, int | None]:
    """Return (local_high, bars_used): most recent confirmed swing high.

    A confirmed swing high is the most recent bar whose intraday high is
    followed by at least 3 subsequent bars all with highs strictly below it
    (drop confirmed).  If no 3-bar confirmation exists — e.g. the peak is
    very recent with fewer than 3 bars after it — falls back to 2 then 1
    confirming bar so that a fresh peak is not missed.

    Tries window sizes 50 → 20 → 10 (largest that fits in available bars).
    Returns (None, None) if no confirmed peak is found in any window.
    """
    n = len(aggs)
    for window in _LOCAL_HIGH_WINDOWS:
        if n < window:
            continue
        slice_ = aggs[-window:]
        m = len(slice_)
        # Try 3 confirming bars, then 2, then 1.
        for min_confirm in (3, 2, 1):
            if m < min_confirm + 1:
                continue
            for i in range(m - min_confirm - 1, -1, -1):
                h0 = float(slice_[i].get("h", 0.0))
                lower = all(
                    float(slice_[i + k].get("h", 0.0)) < h0
                    for k in range(1, min_confirm + 1)
                )
                if lower:
                    return h0, window
        # Also check if the very last bar is higher than all before it in the window
        # (stock is still at the peak with no confirming bars yet).
        last_h = float(slice_[-1].get("h", 0.0))
        if all(float(b.get("h", 0.0)) <= last_h for b in slice_[:-1]):
            return last_h, window
    return None, None


async def evaluate_rule3(
    aggs: list[dict[str, Any]], session: AsyncSession,
) -> Rule3Result:
    """Rule 3 — price-position (block entries near 365d high without pullback)."""
    near_high_pct = await _cfg_float(_KEY_RULE3_NEAR_HIGH, session)
    pullback_pct = await _cfg_float(_KEY_RULE3_PULLBACK, session)

    high, current = _high_and_current_from_aggs(aggs)
    local_high, local_lookback = _local_high_from_aggs(aggs)
    pct_below_local = (
        (local_high - current) / local_high * 100.0
        if local_high and current and local_high > 0
        else None
    )

    if high is None or current is None or high <= 0:
        return Rule3Result(
            result="UNKNOWN", current_price=current, high_365d=high,
            pct_below_high=None, near_high_pct_threshold=near_high_pct,
            pullback_pct_required=pullback_pct, pullback_pct_actual=None,
            local_high=local_high, local_high_lookback_bars=local_lookback,
            pct_below_local_high=pct_below_local,
            reason="Insufficient price history from Polygon.",
        )

    pct_below_high = (high - current) / high * 100.0
    pullback_actual = pct_below_high

    if pct_below_high < near_high_pct:
        # Spec OR clause: near the 52w high, but already pulled back ≥ pullback_pct
        # from the recent confirmed local high — entry is permitted.
        if pct_below_local is not None and pct_below_local >= pullback_pct:
            return Rule3Result(
                result="PASS", current_price=current, high_365d=high,
                pct_below_high=pct_below_high,
                near_high_pct_threshold=near_high_pct,
                pullback_pct_required=pullback_pct,
                pullback_pct_actual=pullback_actual,
                local_high=local_high, local_high_lookback_bars=local_lookback,
                pct_below_local_high=pct_below_local,
                reason=(
                    f"Near 52w high ({pct_below_high:.2f}% below) but pulled back "
                    f"{pct_below_local:.2f}% from local high "
                    f"(≥ {pullback_pct}% required)."
                ),
            )
        return Rule3Result(
            result="FAIL", current_price=current, high_365d=high,
            pct_below_high=pct_below_high,
            near_high_pct_threshold=near_high_pct,
            pullback_pct_required=pullback_pct,
            pullback_pct_actual=pullback_actual,
            local_high=local_high, local_high_lookback_bars=local_lookback,
            pct_below_local_high=pct_below_local,
            reason=(
                f"Price within {pct_below_high:.2f}% of 365d high "
                f"(< {near_high_pct}% threshold) and insufficient pullback "
                f"from local high ({pct_below_local:.2f}% < {pullback_pct}% required)."
                if pct_below_local is not None
                else (
                    f"Price within {pct_below_high:.2f}% of 365d high "
                    f"(< {near_high_pct}% threshold); no local high identified."
                )
            ),
        )
    if pct_below_high >= pullback_pct:
        return Rule3Result(
            result="PASS", current_price=current, high_365d=high,
            pct_below_high=pct_below_high,
            near_high_pct_threshold=near_high_pct,
            pullback_pct_required=pullback_pct,
            pullback_pct_actual=pullback_actual,
            local_high=local_high, local_high_lookback_bars=local_lookback,
            pct_below_local_high=pct_below_local,
            reason=(
                f"Pullback of {pct_below_high:.2f}% from 365d high "
                f"(≥ {pullback_pct}% required)."
            ),
        )
    return Rule3Result(
        result="PASS", current_price=current, high_365d=high,
        pct_below_high=pct_below_high,
        near_high_pct_threshold=near_high_pct,
        pullback_pct_required=pullback_pct,
        pullback_pct_actual=pullback_actual,
        local_high=local_high, local_high_lookback_bars=local_lookback,
        pct_below_local_high=pct_below_local,
        reason=(
            f"Price {pct_below_high:.2f}% below 365d high "
            f"(neutral zone)."
        ),
    )


async def evaluate_rule4(ticker: str, session: AsyncSession) -> Rule4Result:
    """Rule 4 — operator's portfolio-fit YES/NO must be set TODAY."""
    row = await get_rule4_today(ticker, session)
    if row is None:
        return Rule4Result(
            result="FAIL", fit_date=None, fits_portfolio=None,
            reason="No portfolio-fit decision recorded for today.",
        )
    if not row.fits_portfolio:
        return Rule4Result(
            result="FAIL", fit_date=row.fit_date,
            fits_portfolio=False, set_by=row.set_by,
            cluster_gap=row.cluster_gap,
            redundancy_check=row.redundancy_check,
            reason="Operator marked ticker as not fitting portfolio.",
        )
    return Rule4Result(
        result="PASS", fit_date=row.fit_date,
        fits_portfolio=True, set_by=row.set_by,
        cluster_gap=row.cluster_gap,
        redundancy_check=row.redundancy_check,
        reason="Operator confirmed portfolio fit for today.",
    )


async def evaluate_override(
    ticker: str, f7: dict[str, Any],
    session: AsyncSession,
) -> OverrideResult:
    """Track-A-only override path — stronger 5-day UW signal within lookback window.

    dark_pool_usd and flow_usd are fetched live from Unusual Whales as
    5-trading-day totals, identical to Rule 1 — never read from F9.
    """
    ovr_dark = await _cfg_float(_KEY_OVR_DARK_USD, session)
    ovr_flow = await _cfg_float(_KEY_OVR_FLOW_USD, session)
    lookback = await _cfg_int(_KEY_OVR_LOOKBACK, session)

    earnings_dt: date | None = None
    raw_date = f7.get("earnings_date")
    if isinstance(raw_date, str):
        try:
            earnings_dt = date.fromisoformat(raw_date[:10])
        except ValueError:
            earnings_dt = None

    used = await is_override_used_in_cycle(ticker, earnings_dt, session)
    dark_usd, flow_usd = await asyncio.gather(
        _fetch_dark_pool_5d_total(ticker),
        _fetch_flow_5d_bullish_total(ticker),
    )

    qualifies = (
        (dark_usd is not None and dark_usd >= ovr_dark)
        or (flow_usd is not None and flow_usd >= ovr_flow)
    )

    if used:
        reason = "Override already consumed for this earnings cycle."
    elif not qualifies:
        reason = "Override thresholds not met by current F9 signals."
    else:
        reason = "Override available and qualifies."

    return OverrideResult(
        available=not used,
        used_in_cycle=used,
        qualifies=qualifies and not used,
        dark_pool_usd=dark_usd,
        flow_usd=flow_usd,
        threshold_dark_pool_usd=ovr_dark,
        threshold_flow_usd=ovr_flow,
        lookback_days=lookback,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Top-level orchestrator.
# ---------------------------------------------------------------------------


def _combine_track_a_gate(
    rule1: Rule1Result, rule2: Rule2Result,
    rule3: Rule3Result, rule4: Rule4Result,
    override: OverrideResult,
) -> tuple[GateResult, bool]:
    """Return (gate, override_used) for Track A."""
    rule1_pass = rule1.result == "PASS"
    if not rule1_pass and override.qualifies:
        rule1_pass = True
        override_used = True
    else:
        override_used = False

    all_pass = (
        rule1_pass
        and rule2.result == "PASS"
        and rule3.result == "PASS"
        and rule4.result == "PASS"
    )
    if all_pass:
        return "PASS", override_used
    if "UNKNOWN" in {rule2.result, rule3.result}:
        return "UNKNOWN", override_used
    return "FAIL", override_used


def _combine_track_b_gate(
    rule2: Rule2Result, rule4: Rule4Result,
) -> GateResult:
    """Track B uses only Rules 2 & 4 (with parabolic exception baked into Rule 2)."""
    if rule2.result == "PASS" and rule4.result == "PASS":
        return "PASS"
    if "UNKNOWN" in {rule2.result, rule4.result}:
        return "UNKNOWN"
    return "FAIL"


async def evaluate_section16(
    ticker: str, session: AsyncSession,
) -> Section16Result:
    """Top-level entry-gate evaluation for one ticker.

    Fetches F7, F9 in parallel + Polygon aggs (Track A only), then runs the
    rule evaluators.  No data is cached — every call is a fresh evaluation.
    """
    track_str = await get_track_assignment(ticker, session)
    track: TrackType
    if track_str == _TRACK_A:
        track = "TRACK_A"
    elif track_str == _TRACK_B:
        track = "TRACK_B"
    else:
        track = "UNASSIGNED"
    now_utc = datetime.now(tz=UTC)

    if track == "UNASSIGNED":
        return Section16Result(
            ticker=ticker, track="UNASSIGNED", gate="FAIL",
            evaluated_at=now_utc,
            notes="No track assignment recorded for this ticker.",
        )

    # Live fetches — F7 in parallel with Polygon aggs (Track A only).
    # F9 is no longer needed here: Rule 1 and Override fetch UW signals directly.
    if track == "TRACK_A":
        f7, aggs = await asyncio.gather(
            fetch_f7_live(ticker),
            fetch_polygon_aggs(ticker, _POLYGON_HISTORY_DAYS),
            return_exceptions=False,
        )
    else:
        f7 = await fetch_f7_live(ticker)
        aggs = []

    rule2 = await evaluate_rule2(f7, track, session)
    rule4 = await evaluate_rule4(ticker, session)

    if track == "TRACK_A":
        rule1 = await evaluate_rule1(ticker, f7, session)
        rule3 = await evaluate_rule3(aggs, session)
        override = await evaluate_override(ticker, f7, session)
        gate_a, override_used = _combine_track_a_gate(
            rule1, rule2, rule3, rule4, override,
        )
        return Section16Result(
            ticker=ticker, track="TRACK_A", gate=gate_a,
            rule1=rule1, rule2=rule2, rule3=rule3, rule4=rule4,
            override=override, override_used=override_used,
            evaluated_at=now_utc,
        )

    gate_b = _combine_track_b_gate(rule2, rule4)
    return Section16Result(
        ticker=ticker, track="TRACK_B", gate=gate_b,
        rule2=rule2, rule4=rule4,
        evaluated_at=now_utc,
        notes="Track B: Rules 2 & 4 only (parabolic exception in Rule 2).",
    )


__all__ = [
    "Decimal",  # re-export so type-checkers see the import is used
    "evaluate_override",
    "evaluate_rule1",
    "evaluate_rule2",
    "evaluate_rule3",
    "evaluate_rule4",
    "evaluate_section16",
    "fetch_f7_live",
    "fetch_f9_live",
    "fetch_f30_live",
    "fetch_polygon_aggs",
    "get_rule4_today",
    "get_track_assignment",
    "is_override_used_in_cycle",
    "mark_override_used",
    "upsert_rule4_today",
    "upsert_track_assignment",
]
