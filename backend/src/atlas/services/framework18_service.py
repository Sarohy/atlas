"""Framework 18 — 4-Week Trend Gate service.

Single source of truth for the SPY weekly trend gate.

Trigger condition:
    SPY weekly closing price must be lower than the previous week's close
    for >= f18_consecutive_weeks_threshold consecutive weeks.

Data sources (single-source-of-truth rules):
    Polygon.io   — ONLY source for SPY weekly closes.
                   Ticker: SPY, weekly aggregates endpoint.
                   NO database storage of price data.
                   NO dummy data under any condition.
    atlas_config — ONLY source for threshold values.
                   Keys: f18_consecutive_weeks_threshold, f18_add_reduction_pct
                   weeks_to_fetch is DERIVED as threshold + 1 — NOT stored.

Cache:
    Module-level dict with 900-second TTL (15 minutes).
    No Redis in V1 — matches pattern of F12, F15, F17, F29.
    Stale cache: separate module-level dict stores the last successful
    Polygon.io result as a fallback when the live call fails.
    Cache is the SAFETY NET only — never the primary data source.

Week boundary handling:
    A weekly candle is only complete after Friday 16:00 ET.
    Candles for the current (incomplete) week are excluded.
    Polygon weekly candle timestamp = Monday open (milliseconds UTC).

NO DATA rules (never return false results):
    Polygon unavailable AND no stale cache → f18_active = None (UNKNOWN).
    Config keys missing → f18_active = None (CRITICAL error).
    Insufficient completed candles → f18_active = None (UNKNOWN).
    Always use null, never false positive or false negative.

Consuming frameworks:
    Framework 6  (conviction_action_service) — reads get_f18_simple()
    Framework 4  (tranche_sizing_service)    — reads get_f18_simple()
    Framework 16 (master sync)               — reads get_f18_simple()
    Factor 9     (regime fit)                — reads get_f18_simple()
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Final

import httpx
import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.models.atlas_config import AtlasConfig
from atlas.schemas.framework18 import (
    F18Status,
    Framework18Actions,
    Framework18Result,
    Framework18SimpleResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — all spec-defined names; values come from atlas_config or Polygon
# ---------------------------------------------------------------------------

# Cache TTL: 900 seconds = 15 minutes.
# Weekly closes do not change intraday; short enough to catch week boundaries.
_CACHE_TTL_SECONDS: Final[int] = 900

# Module-level result cache: key → (Framework18Result, expiry_monotonic)
_CACHE_KEY: Final[str] = "f18_result"
_cache: dict[str, tuple[Framework18Result, float]] = {}

# Stale cache: stores last successful Polygon result for fallback.
# Key: "spy_closes" → {"closes": [...], "candle_dates": [...], "fetched_at": float}
_stale_cache: dict[str, dict] = {}

# Config DB key names — only key strings are constants; values come from DB.
_CONFIG_KEY_THRESHOLD: Final[str] = "f18_consecutive_weeks_threshold"
_CONFIG_KEY_REDUCTION_PCT: Final[str] = "f18_add_reduction_pct"

# Polygon.io SPY weekly aggregates endpoint.
# Range: 1/week. Sorted desc (newest first). adjusted=true.
_POLYGON_SPY_WEEKLY_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/SPY/range/1/week/{from_date}/{to_date}"
)

# Eastern Time timezone — used for Friday close detection.
_ET_TZ: Final = pytz.timezone("America/New_York")

# Friday is weekday 4 (Mon=0 ... Fri=4).
_FRIDAY_WEEKDAY: Final[int] = 4

# Market close hour in ET (16:00).
_MARKET_CLOSE_HOUR_ET: Final[int] = 16

# Request timeout for Polygon.io calls (seconds).
_POLYGON_TIMEOUT_SECONDS: Final[float] = 10.0


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> Framework18Result | None:
    """Return the cached result if not expired, else None."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _cache[_CACHE_KEY]
        return None
    return result


def _cache_set(result: Framework18Result) -> None:
    """Store result with TTL expiry."""
    _cache[_CACHE_KEY] = (result, time.monotonic() + _CACHE_TTL_SECONDS)


def cache_invalidate() -> None:
    """Invalidate the F18 result cache.

    Called by POST /framework18/refresh to force a fresh Polygon.io fetch.
    """
    _cache.pop(_CACHE_KEY, None)


def _stale_set(closes: list[float], candle_dates: list[str]) -> None:
    """Save a successful Polygon result to the stale fallback cache."""
    _stale_cache["spy_closes"] = {
        "closes": closes,
        "candle_dates": candle_dates,
        "fetched_at": time.monotonic(),
    }


def _stale_get() -> dict | None:
    """Return the last successful Polygon result, or None if never fetched."""
    return _stale_cache.get("spy_closes")


# ---------------------------------------------------------------------------
# Public sync accessor for consuming frameworks
# ---------------------------------------------------------------------------


def get_f18_simple() -> Framework18SimpleResult | None:
    """Return lightweight F18 status from cache (no DB or HTTP call).

    Returns None when the cache is empty or expired.
    Consuming frameworks (F6, F4, Factor 9, F16) call this — never
    evaluate_framework18 directly.
    F18 is the single source of truth for f18_active.
    Treat None as BLOCKED (same as f18_active=None = UNKNOWN).
    """
    cached = _cache_get()
    if cached is None:
        return None
    return Framework18SimpleResult(
        f18_status=cached.f18_status,
        f18_active=cached.f18_active,
        consecutive_weeks_down=cached.consecutive_weeks_down,
        consecutive_threshold=cached.consecutive_threshold,
        add_reduction_pct=cached.add_reduction_pct,
        no_speculative_starters=(
            cached.actions.no_speculative_starters if cached.actions else False
        ),
        tier3_adds_blocked=(
            cached.actions.tier3_adds_blocked if cached.actions else False
        ),
        data_gap_severity=cached.data_gap_severity,
        spy_data_available=cached.spy_data_available,
    )


# ---------------------------------------------------------------------------
# Config readers
# ---------------------------------------------------------------------------


async def _get_config_str(key: str, session: AsyncSession) -> str:
    """Read a string value from atlas_config. Raises RuntimeError if missing."""
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
# Pure computation helpers (no I/O)
# ---------------------------------------------------------------------------


def calculate_consecutive_down(closes: list[float]) -> int:
    """Count consecutive declining weeks from most recent backwards.

    closes[0] = most recent completed week (newest)
    closes[-1] = oldest week

    Only counts the unbroken streak from the most recent week.
    A single up week resets the count to zero at that point.

    Pure sync function — no I/O, fully unit-testable without mocks.

    Examples:
        [5050, 5100, 5200, 5350] → 3   (all down)
        [5050, 5100, 5150, 5200] → 2   (streak breaks at index 2)
        [5050, 5100, 5050, 5200] → 2   (W3<W4 is UP → break at index 2)
        [5400, 5350, 5300, 5250] → 0   (all up)
    """
    if len(closes) < 2:
        return 0

    consecutive = 0
    for i in range(len(closes) - 1):
        # closes[i] is more recent, closes[i+1] is older.
        if closes[i] < closes[i + 1]:
            consecutive += 1
        else:
            # Streak broken — stop counting. Do NOT count non-consecutive declines.
            break

    return consecutive


def _is_candle_complete(
    candle_ts_ms: int,
    now_et: datetime,
) -> bool:
    """Return True if the weekly candle's Friday close has already passed.

    Polygon weekly candle timestamp = Monday open of that week, in UTC milliseconds.
    A candle is only complete after Friday 16:00 ET of the same week.
    """
    candle_dt_utc = datetime.fromtimestamp(candle_ts_ms / 1000, tz=timezone.utc)
    candle_dt_et = candle_dt_utc.astimezone(_ET_TZ)

    # Days until Friday from the candle's Monday start (Monday=0, Friday=4).
    days_to_friday = _FRIDAY_WEEKDAY - candle_dt_et.weekday()
    if days_to_friday < 0:
        # Should not happen for a Monday-start candle, but guard anyway.
        days_to_friday += 7

    friday_date = (candle_dt_et + timedelta(days=days_to_friday)).date()
    friday_close_et = _ET_TZ.localize(  # type: ignore[attr-defined]
        datetime(
            friday_date.year,
            friday_date.month,
            friday_date.day,
            _MARKET_CLOSE_HOUR_ET,
            0,
            0,
        )
    )

    return now_et >= friday_close_et


# ---------------------------------------------------------------------------
# Polygon.io data fetcher
# ---------------------------------------------------------------------------


async def _fetch_spy_weekly_closes(weeks_to_fetch: int) -> dict:
    """Fetch live SPY weekly closes from Polygon.io.

    No database storage. No dummy data. No assumptions.

    Returns a dict with keys:
        available (bool)     — whether usable closes were obtained
        closes (list[float]) — newest-first completed weekly closes
        candle_dates (list[str]) — ISO date of each candle's Monday open
        stale (bool)         — True when data came from stale cache
        polygon_available (bool) — True when live Polygon data was used
        reason (str | None)  — human-readable reason when available=False

    Rule 5 — Week boundary: current incomplete week is excluded.
    Rule 4 — Stale cache is safety net only, never primary source.
    Rule 6 — Returns null/unavailable when data is insufficient.
    """
    settings = get_settings()
    api_key = settings.polygon_api_key

    # Calculate date range.
    # Polygon's DELAYED tier returns sparse weekly aggregates on narrow date
    # windows — empirically returns only 2–3 candles for a 35-day range.
    # Use a 180-day lookback so we always retrieve enough completed candles.
    # We still only consume the most recent `weeks_to_fetch` after filtering;
    # extra candles are harmless.
    now_et = datetime.now(_ET_TZ)
    today_et = now_et.date()
    from_date = (today_et - timedelta(days=180)).isoformat()
    to_date = today_et.isoformat()

    url = _POLYGON_SPY_WEEKLY_URL.format(from_date=from_date, to_date=to_date)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={
                    "adjusted": "true",
                    "sort": "desc",
                    # Wider limit to match the wider lookback window.
                    "limit": max(weeks_to_fetch + 2, 30),
                    "apiKey": api_key,
                },
                timeout=_POLYGON_TIMEOUT_SECONDS,
            )

        # Handle rate limiting (HTTP 429).
        if response.status_code == 429:
            stale = _stale_get()
            if stale and len(stale["closes"]) >= weeks_to_fetch:
                logger.warning(
                    "f18_polygon_rate_limited_cache_fallback",
                    extra={"weeks_needed": weeks_to_fetch},
                )
                return {
                    "available": True,
                    "closes": stale["closes"][:weeks_to_fetch],
                    "candle_dates": stale["candle_dates"][:weeks_to_fetch],
                    "stale": True,
                    "polygon_available": False,
                    "reason": "Polygon.io rate limited — using cached SPY data",
                }
            return {
                "available": False,
                "closes": [],
                "candle_dates": [],
                "stale": False,
                "polygon_available": False,
                "reason": "Polygon.io rate limited — no cached data available",
            }

        # Handle non-200 responses.
        if response.status_code != 200:
            stale = _stale_get()
            if stale and len(stale["closes"]) >= weeks_to_fetch:
                logger.warning(
                    "f18_polygon_error_cache_fallback",
                    extra={
                        "status_code": response.status_code,
                        "weeks_needed": weeks_to_fetch,
                    },
                )
                return {
                    "available": True,
                    "closes": stale["closes"][:weeks_to_fetch],
                    "candle_dates": stale["candle_dates"][:weeks_to_fetch],
                    "stale": True,
                    "polygon_available": False,
                    "reason": (
                        f"Polygon.io returned HTTP {response.status_code} — "
                        "using cached SPY data"
                    ),
                }
            return {
                "available": False,
                "closes": [],
                "candle_dates": [],
                "stale": False,
                "polygon_available": False,
                "reason": f"Polygon.io returned HTTP {response.status_code}",
            }

        results = response.json().get("results", [])

        if not results:
            stale = _stale_get()
            if stale and len(stale["closes"]) >= weeks_to_fetch:
                return {
                    "available": True,
                    "closes": stale["closes"][:weeks_to_fetch],
                    "candle_dates": stale["candle_dates"][:weeks_to_fetch],
                    "stale": True,
                    "polygon_available": False,
                    "reason": (
                        "Polygon.io returned empty results for SPY weekly data — "
                        "using cached data"
                    ),
                }
            return {
                "available": False,
                "closes": [],
                "candle_dates": [],
                "stale": False,
                "polygon_available": False,
                "reason": "Polygon.io returned empty results for SPY weekly data",
            }

        # Filter to completed weekly candles only (Rule 5 — week boundary).
        completed: list[dict] = []
        for r in results:
            candle_ts = r.get("t")
            close_price = r.get("c")
            if candle_ts is None or close_price is None:
                continue
            if _is_candle_complete(int(candle_ts), now_et):
                # Extract the ISO date of this candle's Monday open.
                candle_dt_et = datetime.fromtimestamp(
                    int(candle_ts) / 1000, tz=timezone.utc
                ).astimezone(_ET_TZ)
                completed.append({
                    "close": float(close_price),
                    "date": candle_dt_et.date().isoformat(),
                })

        if len(completed) < weeks_to_fetch:
            stale = _stale_get()
            if stale and len(stale["closes"]) >= weeks_to_fetch:
                logger.info(
                    "f18_insufficient_completed_candles_cache_fallback",
                    extra={
                        "completed": len(completed),
                        "needed": weeks_to_fetch,
                    },
                )
                return {
                    "available": True,
                    "closes": stale["closes"][:weeks_to_fetch],
                    "candle_dates": stale["candle_dates"][:weeks_to_fetch],
                    "stale": True,
                    "polygon_available": False,
                    "reason": (
                        f"SPY weekly data unavailable — only {len(completed)} of "
                        f"{weeks_to_fetch} weeks. Treating F18 as UNKNOWN per spec. "
                        "Using cached data."
                    ),
                }
            return {
                "available": False,
                "closes": [],
                "candle_dates": [],
                "stale": False,
                "polygon_available": False,
                "reason": (
                    f"SPY weekly data unavailable — only {len(completed)} of "
                    f"{weeks_to_fetch} weeks. Treating F18 as UNKNOWN per spec."
                ),
            }

        # Polygon returns results sorted desc (newest first) — take exactly weeks_to_fetch.
        candles = completed[:weeks_to_fetch]
        closes = [c["close"] for c in candles]
        dates = [c["date"] for c in candles]

        # Persist to stale cache as safety net for next call if Polygon fails.
        _stale_set(closes, dates)

        return {
            "available": True,
            "closes": closes,
            "candle_dates": dates,
            "stale": False,
            "polygon_available": True,
            "reason": None,
        }

    except Exception as exc:
        logger.warning(
            "f18_polygon_exception",
            extra={"error": str(exc)},
        )
        stale = _stale_get()
        if stale and len(stale["closes"]) >= weeks_to_fetch:
            return {
                "available": True,
                "closes": stale["closes"][:weeks_to_fetch],
                "candle_dates": stale["candle_dates"][:weeks_to_fetch],
                "stale": True,
                "polygon_available": False,
                "reason": (
                    f"Polygon.io exception: {exc!s} — using cached SPY data"
                ),
            }
        return {
            "available": False,
            "closes": [],
            "candle_dates": [],
            "stale": False,
            "polygon_available": False,
            "reason": str(exc),
        }


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------


async def evaluate_framework18(session: AsyncSession) -> Framework18Result:
    """Evaluate the 4-Week Trend Gate and return the full result.

    Reads atlas_config for thresholds.
    Fetches SPY weekly closes live from Polygon.io.
    Does NOT store price data in the database.
    Does NOT return dummy data or false results under any condition.
    """
    warnings: list[str] = []
    now_utc = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Read config — fail hard if keys are missing ──────────────
    try:
        threshold = int(await _get_config_str(_CONFIG_KEY_THRESHOLD, session))
        reduction_pct = await _get_config_float(_CONFIG_KEY_REDUCTION_PCT, session)
    except RuntimeError as exc:
        missing_msg = str(exc)
        logger.error("f18_config_missing", extra={"error": missing_msg})
        result = Framework18Result(
            f18_status=F18Status.UNKNOWN,
            f18_active=None,
            consecutive_weeks_down=None,
            consecutive_threshold=None,
            add_reduction_pct=None,
            weeks_fetched=None,
            spy_weekly_closes=[],
            candle_dates=[],
            spy_data_available=False,
            spy_data_stale=False,
            polygon_available=False,
            actions=None,
            factor9_contribution=None,
            data_gap_severity="CRITICAL",
            warning_messages=[
                f"Missing atlas_config keys: {missing_msg}. "
                "Cannot evaluate Framework 18. "
                "Run 'alembic upgrade head' to seed required config values."
            ],
            last_updated=now_utc,
            cache_hit=False,
        )
        return result
    except Exception as exc:
        logger.error("f18_config_db_error", extra={"error": str(exc)})
        result = Framework18Result(
            f18_status=F18Status.UNKNOWN,
            f18_active=None,
            consecutive_weeks_down=None,
            consecutive_threshold=None,
            add_reduction_pct=None,
            weeks_fetched=None,
            spy_weekly_closes=[],
            candle_dates=[],
            spy_data_available=False,
            spy_data_stale=False,
            polygon_available=False,
            actions=None,
            factor9_contribution=None,
            data_gap_severity="CRITICAL",
            warning_messages=[
                f"atlas_config DB error: {exc!s}. "
                "Cannot evaluate Framework 18."
            ],
            last_updated=now_utc,
            cache_hit=False,
        )
        return result

    # weeks_to_fetch is DERIVED from threshold — NOT stored or hardcoded.
    weeks_to_fetch: int = threshold + 1

    # ── Step 2: Fetch live SPY weekly closes from Polygon.io ─────────────
    spy_result = await _fetch_spy_weekly_closes(weeks_to_fetch)

    spy_available: bool = spy_result["available"]
    spy_stale: bool = spy_result.get("stale", False)
    closes: list[float] = spy_result.get("closes", [])
    candle_dates: list[str] = spy_result.get("candle_dates", [])
    polygon_available: bool = spy_result.get("polygon_available", False)

    if not spy_available:
        reason = spy_result.get("reason", "unknown error")
        warnings.append(
            f"{reason} All consuming frameworks treating F18 as UNKNOWN."
        )
        result = Framework18Result(
            f18_status=F18Status.UNKNOWN,
            f18_active=None,
            consecutive_weeks_down=None,
            consecutive_threshold=threshold,
            add_reduction_pct=reduction_pct,
            weeks_fetched=weeks_to_fetch,
            spy_weekly_closes=[],
            candle_dates=[],
            spy_data_available=False,
            spy_data_stale=False,
            polygon_available=False,
            actions=None,
            factor9_contribution=None,
            data_gap_severity="CRITICAL",
            warning_messages=warnings,
            last_updated=now_utc,
            cache_hit=False,
        )
        return result

    if spy_stale:
        reason = spy_result.get("reason", "stale cache used")
        warnings.append(
            f"SPY data is stale — {reason}. "
            "Result is based on cached data. "
            "Verify manually if this decision is critical."
        )

    # ── Step 3: Verify we have enough candles ─────────────────────────────
    if len(closes) < weeks_to_fetch:
        warnings.append(
            f"Insufficient completed weekly closes: "
            f"got {len(closes)}, need {weeks_to_fetch}. "
            "Cannot determine trend direction."
        )
        result = Framework18Result(
            f18_status=F18Status.UNKNOWN,
            f18_active=None,
            consecutive_weeks_down=None,
            consecutive_threshold=threshold,
            add_reduction_pct=reduction_pct,
            weeks_fetched=weeks_to_fetch,
            spy_weekly_closes=closes,
            candle_dates=candle_dates,
            spy_data_available=True,
            spy_data_stale=spy_stale,
            polygon_available=polygon_available,
            actions=None,
            factor9_contribution=None,
            data_gap_severity="MAJOR",
            warning_messages=warnings,
            last_updated=now_utc,
            cache_hit=False,
        )
        return result

    # ── Step 4: Calculate consecutive down weeks (pure function, no I/O) ─
    consecutive_down = calculate_consecutive_down(closes)

    # ── Step 5: Determine gate state ──────────────────────────────────────
    # Gate fires at >= threshold (not just >).
    f18_active: bool = consecutive_down >= threshold
    f18_status = F18Status.ACTIVE if f18_active else F18Status.CLEAR

    # ── Step 6: Build actions (only when active) ──────────────────────────
    actions: Framework18Actions | None = None
    if f18_active:
        actions = Framework18Actions(
            reduce_aggressive_adds=True,
            add_reduction_pct=reduction_pct,
            prioritize_quality_only=True,
            min_tier_for_new_adds="TIER_1",
            no_speculative_starters=True,
            tier3_adds_blocked=True,
        )

    # ── Step 7: Factor 9 contribution ─────────────────────────────────────
    factor9_contribution: str | None = (
        "NEGATIVE — F18 active reduces Factor 9 Regime Fit score (7% weight)"
        if f18_active
        else "NEUTRAL — F18 not active, no Factor 9 penalty"
    )

    # ── Step 8: Data gap severity ─────────────────────────────────────────
    if not spy_available:
        gap_severity = "CRITICAL"
    elif spy_stale:
        gap_severity = "PARTIAL"
    else:
        gap_severity = "NONE"

    # ── Step 9: Build, cache, and return result ───────────────────────────
    result = Framework18Result(
        f18_status=f18_status,
        f18_active=f18_active,
        consecutive_weeks_down=consecutive_down,
        consecutive_threshold=threshold,
        add_reduction_pct=reduction_pct,
        weeks_fetched=weeks_to_fetch,
        spy_weekly_closes=closes,
        candle_dates=candle_dates,
        spy_data_available=spy_available,
        spy_data_stale=spy_stale,
        polygon_available=polygon_available,
        actions=actions,
        factor9_contribution=factor9_contribution,
        data_gap_severity=gap_severity,
        warning_messages=warnings,
        last_updated=now_utc,
        cache_hit=False,
    )
    _cache_set(result)

    logger.info(
        "f18_evaluated",
        extra={
            "f18_active": f18_active,
            "consecutive_down": consecutive_down,
            "threshold": threshold,
            "weeks_fetched": weeks_to_fetch,
            "spy_stale": spy_stale,
            "polygon_available": polygon_available,
        },
    )

    return result
