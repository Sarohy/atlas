"""Framework 29 — Capitulation / Re-Entry AND Gate service.

Five market signals are evaluated; 3 of 5 confirmed fires the GREEN LIGHT.

Signal list (per CLAUDE.md spec, updated 2026-04-29):
  1. VIX touches prior regime-high then declines for ≥3 consecutive sessions
  2. Brent crude closes below $95 for the 2nd consecutive session
  3. Put/call ratio spikes above 1.3 then reverses downward
  4. Breadth: % S&P 500 stocks above 50-DMA falls below 30% then recovers
  5. Operator geopolitical flag set to RESOLVED

Data sources:
  • Yahoo Finance — Signal 1 (VIX daily closes via ^VIX chart API)
  • Yahoo Finance — Signal 2 (Brent daily closes via BZ=F chart API)
  • Unusual Whales /api/market/total-options-volume — Signal 3 (put_volume/call_volume)
  • Polygon.io I:S5O — Signal 4 (breadth index; requires paid plan — stays UNAVAILABLE on Starter)
  • In-memory geo flag (regime_modifier_service) — Signal 5

Caching:
  Results are cached in an in-memory dict for 15 minutes (900 s).

Pure helpers (prefixed with underscore) are I/O-free and unit-testable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, date, datetime, timedelta
from typing import Final

import httpx

from atlas.schemas.framework29 import (
    Framework29GateStatus,
    Framework29Result,
    Framework29Signal,
    SignalStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# In-memory cache TTL in seconds.
_CACHE_TTL_SECONDS: Final[int] = 900  # 15 minutes

# Cache key — F29 is portfolio-level, single entry.
_CACHE_KEY: Final[str] = "f29_result"

# Number of confirmed signals required to pass the AND gate.
_GATE_THRESHOLD: Final[int] = 3

# Signal 1 — VIX regime-high and consecutive decline.
_VIX_LOOKBACK_DAYS: Final[int] = 30       # calendar days for Yahoo Finance range param
_VIX_REGIME_WINDOW: Final[int] = 20       # look back this many sessions to find regime-high
_VIX_DECLINE_SESSIONS: Final[int] = 3     # must decline for 3 consecutive sessions after peak touch

# Signal 2 — Brent hard threshold.
_BRENT_HARD_THRESHOLD: Final[float] = 95.0  # USD per barrel
_BRENT_CONSECUTIVE_SESSIONS: Final[int] = 2 # must be below threshold for 2 consecutive sessions

# Signal 3 — Put/call panic-then-reversal (computed from UW total-options-volume).
_PCR_PANIC_THRESHOLD: Final[float] = 1.3   # spike above this qualifies as panic
_PCR_LOOKBACK_SESSIONS: Final[int] = 10    # sessions to scan for spike + reversal

# Signal 4 — Breadth washout-and-recovery via Polygon I:S5O.
# NOTE: I:S5O requires a Polygon paid plan. Signal stays UNAVAILABLE on Starter plan.
_BREADTH_WASHOUT_THRESHOLD: Final[float] = 30.0   # % stocks above 50-DMA that marks washout
_BREADTH_LOOKBACK_DAYS: Final[int] = 20            # sessions to scan for dip + recovery

# Yahoo Finance chart API URLs.
_YAHOO_VIX_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart/%5EVIX"
_YAHOO_BRENT_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart/BZ%3DF"
_YAHOO_HEADERS: Final[dict[str, str]] = {"User-Agent": "Mozilla/5.0"}

# Polygon breadth ticker (requires plan upgrade — kept for future use).
_POLYGON_BREADTH_TICKER: Final[str] = "I:S5O"  # S&P 500 % above 50-DMA index

# Polygon aggs base URL (breadth only).
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)

# Unusual Whales API base URL.
_UW_BASE_URL: Final[str] = "https://api.unusualwhales.com"

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# In-memory result cache: key -> (result, unix_timestamp)
_cache: dict[str, tuple[Framework29Result, float]] = {}


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get() -> tuple[Framework29Result | None, float]:
    """Return (result, age_minutes) from cache, or (None, 0)."""
    entry = _cache.get(_CACHE_KEY)
    if entry is None:
        return None, 0.0
    result, fetched_at = entry
    age_minutes = (time.time() - fetched_at) / 60.0
    return result, age_minutes


def _cache_set(result: Framework29Result) -> None:
    """Store result in cache with current timestamp."""
    _cache[_CACHE_KEY] = (result, time.time())


def _cache_invalidate() -> None:
    """Remove cached result, forcing next call to fetch fresh data."""
    _cache.pop(_CACHE_KEY, None)


# ---------------------------------------------------------------------------
# Pure signal helpers — no I/O
# ---------------------------------------------------------------------------


def _find_regime_high(closes: list[float], window: int) -> float | None:
    """Return the maximum close over the last *window* sessions.

    Returns None when fewer than *window* values are available.
    """
    if len(closes) < window:
        return None
    return max(closes[-window:])


def _check_signal1_vix(
    closes: list[float],
) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 1: VIX touches prior regime-high then declines >= 3 consecutive sessions.

    Algorithm:
      1. Find regime-high = max VIX in the last _VIX_REGIME_WINDOW sessions.
      2. Confirm the peak occurred at least _VIX_DECLINE_SESSIONS sessions ago
         (i.e., there is room for the 3-session decline to follow the spike).
      3. Confirm the last _VIX_DECLINE_SESSIONS closes are each lower than the one before.

    Pure function -- no I/O.
    """
    if len(closes) < _VIX_REGIME_WINDOW:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient VIX history"}

    regime_window = closes[-_VIX_REGIME_WINDOW:]
    regime_high = max(regime_window)

    # Index of the most recent peak in the regime window.
    # reversed() so that we find the MOST RECENT peak when values repeat.
    peak_offset = next(
        i for i, v in enumerate(reversed(regime_window)) if v == regime_high
    )
    # peak_offset is 0 if the peak is the most recent session.
    sessions_since_peak = peak_offset

    # Need at least _VIX_DECLINE_SESSIONS sessions of room after the peak.
    touched_high = sessions_since_peak >= _VIX_DECLINE_SESSIONS

    # Check 3 consecutive declining sessions at the end of the series.
    tail = closes[-(_VIX_DECLINE_SESSIONS + 1):]
    declining = (
        len(tail) == _VIX_DECLINE_SESSIONS + 1
        and all(tail[i + 1] < tail[i] for i in range(_VIX_DECLINE_SESSIONS))
    )

    confirmed = touched_high and declining
    status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET

    return status, {
        "vix_latest_close": round(closes[-1], 2),
        "vix_regime_high": round(regime_high, 2),
        "vix_touched_regime_high": touched_high,
        "sessions_since_peak": sessions_since_peak,
        "vix_declining_sessions": _VIX_DECLINE_SESSIONS,
        "vix_currently_declining": declining,
        "confirmed": confirmed,
    }


def _check_signal2_brent(
    closes: list[float],
) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 2: Brent crude closes below $95 for 2nd consecutive session.

    Pure function — no I/O.
    """
    if len(closes) < _BRENT_CONSECUTIVE_SESSIONS:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient Brent history"}

    tail = closes[-_BRENT_CONSECUTIVE_SESSIONS:]
    all_below = all(c < _BRENT_HARD_THRESHOLD for c in tail)
    status = SignalStatus.CONFIRMED if all_below else SignalStatus.NOT_MET

    return status, {
        "brent_latest_close": round(closes[-1], 2),
        "threshold": _BRENT_HARD_THRESHOLD,
        "consecutive_sessions_required": _BRENT_CONSECUTIVE_SESSIONS,
        "consecutive_closes_below": [round(c, 2) for c in tail],
        "confirmed": all_below,
    }


def _check_signal3_pcr(
    pcr_sessions: list[float],
) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 3: Put/call ratio spikes above 1.3 then reverses downward.

    Algorithm:
      1. Scan last _PCR_LOOKBACK_SESSIONS for a value >= _PCR_PANIC_THRESHOLD.
      2. Confirm the most recent session is LOWER than the session before it
         (i.e., reversal from the spike).

    Pure function — no I/O.
    """
    if len(pcr_sessions) < 3:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient put/call data"}

    window = pcr_sessions[-_PCR_LOOKBACK_SESSIONS:]
    spiked = any(r >= _PCR_PANIC_THRESHOLD for r in window)
    reversing = pcr_sessions[-1] < pcr_sessions[-2]  # latest < previous

    confirmed = spiked and reversing
    status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET

    return status, {
        "pcr_latest": round(pcr_sessions[-1], 3),
        "pcr_previous": round(pcr_sessions[-2], 3),
        "panic_threshold": _PCR_PANIC_THRESHOLD,
        "spike_detected_in_window": spiked,
        "currently_reversing": reversing,
        "confirmed": confirmed,
    }


def _check_signal4_breadth(
    breadth_values: list[float],
) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 4: % S&P 500 stocks above 50-DMA dips below 30% then recovers.

    Algorithm:
      1. Scan last _BREADTH_LOOKBACK_DAYS for a value <= _BREADTH_WASHOUT_THRESHOLD.
      2. Confirm the most recent session is ABOVE the washout threshold (recovery).

    Data source: Polygon index I:S5O (S&P 500 % above 50-DMA).
    Pure function — no I/O.
    """
    if len(breadth_values) < 3:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient breadth history (I:S5O)"}

    window = breadth_values[-_BREADTH_LOOKBACK_DAYS:]
    washout_occurred = any(v <= _BREADTH_WASHOUT_THRESHOLD for v in window)
    recovered = breadth_values[-1] > _BREADTH_WASHOUT_THRESHOLD

    confirmed = washout_occurred and recovered
    status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET

    return status, {
        "breadth_latest_pct": round(breadth_values[-1], 2),
        "washout_threshold_pct": _BREADTH_WASHOUT_THRESHOLD,
        "washout_occurred_in_window": washout_occurred,
        "currently_recovered": recovered,
        "data_source": "Polygon I:S5O",
        "confirmed": confirmed,
    }


def _check_signal5_geo_flag(
    geo_flag: str,
) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 5: Operator geopolitical flag set in Framework 2 (any non-NONE value).

    Reads the in-memory geo flag written by the regime modifier endpoint
    (Framework 2). Confirms whenever Framework 2 has recorded any active
    geopolitical state i.e. geo_flag is not "NONE". Pure function -- no I/O.
    """
    normalized = geo_flag.strip().upper()
    confirmed = normalized != "NONE" and normalized != ""
    status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET

    return status, {
        "geo_flag_current": geo_flag,
        "geo_flag_source": "Framework 2 (regime modifier)",
        "confirmed": confirmed,
    }


def _determine_gate_status(
    confirmed: int,
    unavailable: int,
    total: int = 5,
) -> tuple[bool, str, str]:
    """Compute gate state and message. Pure function.

    Returns (gate_passed, gate_status, gate_message).
    """
    remaining = _GATE_THRESHOLD - confirmed
    skipped = unavailable

    if confirmed >= _GATE_THRESHOLD:
        return True, "GREEN_LIGHT", (
            f"AND gate open — {confirmed}/{total} signals confirmed "
            f"({skipped} unavailable). Capitulation conditions met. Deploy cash."
        )

    return False, "BLOCKED", (
        f"AND gate blocked — {confirmed}/{total} confirmed, need {_GATE_THRESHOLD}. "
        f"{remaining} more signal(s) required. ({skipped} unavailable.)"
    )


def _data_gap_severity(unavailable: int) -> str:
    """Classify data gap severity by number of unavailable signals."""
    if unavailable == 0:
        return "NONE"
    if unavailable == 1:
        return "LOW"
    if unavailable == 2:
        return "MEDIUM"
    return "HIGH"


def _unavailable(reason: str) -> tuple[SignalStatus, dict[str, object]]:
    """Return a typed (UNAVAILABLE, detail) pair for use in the evaluation pipeline."""
    return SignalStatus.UNAVAILABLE, {"reason": reason}



async def _fetch_yahoo_daily_closes(
    url: str,
    range_str: str,
    client: httpx.AsyncClient,
) -> list[float] | None:
    """Fetch daily close prices from Yahoo Finance chart API.

    Args:
        url: Pre-encoded Yahoo Finance chart URL for the symbol.
        range_str: Yahoo range parameter e.g. ``"1mo"``, ``"3mo"``.

    Returns ascending chronological list of close floats, or None on error.
    Null entries (holidays/halts) are filtered out.
    """
    try:
        response = await client.get(
            url,
            params={"interval": "1d", "range": range_str},
            headers=_YAHOO_HEADERS,
            timeout=10.0,
        )
        if response.status_code != 200:
            logger.warning(
                "Yahoo Finance non-200",
                extra={"url": url, "status": response.status_code},
            )
            return None

        data = response.json()
        result_list = (data.get("chart") or {}).get("result")
        if not result_list:
            return None

        quotes = result_list[0].get("indicators", {}).get("quote", [{}])
        closes_raw = quotes[0].get("close", []) if quotes else []
        closes = [float(c) for c in closes_raw if c is not None]
        return closes if closes else None

    except Exception as exc:
        logger.warning(
            "Yahoo Finance fetch failed",
            extra={"url": url, "error": repr(exc)},
        )
        return None


async def _fetch_uw_pcr_from_options_volume(
    api_key: str,
    client: httpx.AsyncClient,
) -> list[float] | None:
    """Compute put/call ratio history from UW /api/market/total-options-volume.

    Each day's PCR = put_volume / call_volume.
    Returns ascending chronological list of PCR floats, or None on error.
    """
    try:
        response = await client.get(
            f"{_UW_BASE_URL}/api/market/total-options-volume",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": _PCR_LOOKBACK_SESSIONS + 2},
            timeout=10.0,
        )
        if response.status_code != 200:
            logger.warning(
                "UW total-options-volume non-200",
                extra={"status": response.status_code},
            )
            return None

        data = response.json()
        entries = data.get("data", []) if isinstance(data, dict) else data
        if not entries:
            return None

        ratios: list[float] = []
        # Entries come back most-recent-first; reverse for ascending order.
        for entry in reversed(entries):
            call_vol = float(entry.get("call_volume", 0) or 0)
            put_vol = float(entry.get("put_volume", 0) or 0)
            if call_vol > 0:
                ratios.append(round(put_vol / call_vol, 4))

        return ratios if ratios else None

    except Exception as exc:
        logger.warning(
            "UW total-options-volume fetch failed",
            extra={"error": repr(exc)},
        )
        return None


async def _fetch_polygon_closes(
    ticker: str,
    lookback_days: int,
    api_key: str,
    client: httpx.AsyncClient,
) -> list[float] | None:
    """Fetch daily close prices from Polygon aggs endpoint.

    Used for Signal 4 breadth index (I:S5O). Requires a Polygon paid plan.
    Returns ascending chronological list of close floats, or None on error.
    """
    to_date = date.today()
    from_date = to_date - timedelta(days=lookback_days * 2)  # buffer for weekends/holidays

    url = _POLYGON_AGGS_URL.format(
        ticker=ticker,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
    )

    try:
        response = await client.get(
            url,
            params={"apiKey": api_key, "sort": "asc", "limit": lookback_days + 30},
            timeout=10.0,
        )

        if response.status_code != 200:
            logger.warning(
                "Polygon aggs non-200",
                extra={"ticker": ticker, "status": response.status_code},
            )
            return None

        data = response.json()
        results = data.get("results", [])
        if not results:
            return None

        closes = [float(bar["c"]) for bar in results if "c" in bar]
        return closes if closes else None

    except Exception as exc:
        logger.warning(
            "Polygon aggs fetch failed",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return None




# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def evaluate_framework29(
    polygon_api_key: str,
    uw_api_key: str,
    client: httpx.AsyncClient | None = None,
) -> Framework29Result:
    """Evaluate all 5 Framework 29 signals and return the gate status.

    Results are cached for _CACHE_TTL_SECONDS.  Pass client=None to let the
    function manage its own httpx.AsyncClient (tests may inject a mock).
    """
    cached, age_minutes = _cache_get()
    if cached is not None and age_minutes <= _CACHE_TTL_SECONDS / 60.0:
        return Framework29Result(
            **{**cached.model_dump(), "cache_hit": True}
        )

    _client: httpx.AsyncClient = client if client is not None else httpx.AsyncClient()

    try:
        # Parallel fetch: VIX (Yahoo), Brent (Yahoo), PCR (UW options vol), breadth (Polygon).
        vix_closes_raw, brent_closes_raw, pcr_raw, breadth_raw = (
            await asyncio.gather(
                _fetch_yahoo_daily_closes(_YAHOO_VIX_URL, "3mo", _client),
                _fetch_yahoo_daily_closes(_YAHOO_BRENT_URL, "1mo", _client),
                _fetch_uw_pcr_from_options_volume(uw_api_key, _client),
                _fetch_polygon_closes(
                    _POLYGON_BREADTH_TICKER, _BREADTH_LOOKBACK_DAYS, polygon_api_key, _client
                ),
                return_exceptions=True,
            )
        )
    finally:
        if client is None:
            await _client.aclose()

    # Coerce exceptions to None.
    def _unwrap(v: object) -> object:
        return None if isinstance(v, BaseException) else v

    vix_closes: list[float] | None = _unwrap(vix_closes_raw)  # type: ignore[assignment]
    brent_closes: list[float] | None = _unwrap(brent_closes_raw)  # type: ignore[assignment]
    pcr_sessions: list[float] | None = _unwrap(pcr_raw)  # type: ignore[assignment]
    breadth_values: list[float] | None = _unwrap(breadth_raw)  # type: ignore[assignment]

    # Signal 5: read the in-memory geo flag (no network I/O).
    from atlas.services.regime_modifier_service import get_geo_flag_current
    geo_flag = get_geo_flag_current()

    # Evaluate each signal.
    s1_status, s1_vals = (
        _check_signal1_vix(vix_closes)
        if vix_closes
        else _unavailable("VIX data unavailable")
    )
    s2_status, s2_vals = (
        _check_signal2_brent(brent_closes)
        if brent_closes
        else _unavailable("Brent data unavailable")
    )
    s3_status, s3_vals = (
        _check_signal3_pcr(pcr_sessions)
        if pcr_sessions
        else _unavailable("Put/call data unavailable")
    )
    s4_status, s4_vals = (
        _check_signal4_breadth(breadth_values)
        if breadth_values
        else _unavailable("Breadth data unavailable (I:S5O)")
    )
    s5_status, s5_vals = _check_signal5_geo_flag(geo_flag)

    signals_data: list[tuple[SignalStatus, str, dict[str, object], dict[str, object]]] = [
        (
            s1_status,
            "VIX touches regime-high then declines 3 sessions",
            s1_vals,
            {
                "regime_window": _VIX_REGIME_WINDOW,
                "decline_sessions_required": _VIX_DECLINE_SESSIONS,
            },
        ),
        (
            s2_status,
            "Brent below $95 for 2 consecutive sessions",
            s2_vals,
            {
                "threshold_usd": _BRENT_HARD_THRESHOLD,
                "consecutive_sessions": _BRENT_CONSECUTIVE_SESSIONS,
            },
        ),
        (
            s3_status,
            "Put/call ratio spikes above 1.3 then reverses",
            s3_vals,
            {
                "panic_threshold": _PCR_PANIC_THRESHOLD,
                "lookback_sessions": _PCR_LOOKBACK_SESSIONS,
            },
        ),
        (
            s4_status,
            "S&P 500 breadth dips below 30% above 50-DMA then recovers",
            s4_vals,
            {
                "washout_threshold_pct": _BREADTH_WASHOUT_THRESHOLD,
                "lookback_days": _BREADTH_LOOKBACK_DAYS,
            },
        ),
        (
            s5_status,
            "Framework 2 geopolitical flag set (any non-NONE value)",
            s5_vals,
            {"confirmed_when": "geo_flag != NONE", "source": "Framework 2"},
        ),
    ]

    unavailable_statuses = {SignalStatus.UNAVAILABLE, SignalStatus.MANUAL_REQUIRED}
    signals_confirmed = sum(1 for s, *_ in signals_data if s == SignalStatus.CONFIRMED)
    signals_unavailable = sum(1 for s, *_ in signals_data if s in unavailable_statuses)

    gate_passed, gate_status_str, gate_message = _determine_gate_status(
        signals_confirmed, signals_unavailable
    )

    warning_messages: list[str] = []
    if signals_unavailable > 0:
        warning_messages.append(
            f"{signals_unavailable} signal(s) could not be evaluated due to missing data."
        )

    signals_out = [
        Framework29Signal(
            signal_number=i + 1,
            signal_name=name,
            status=s,
            confirmed=(s == SignalStatus.CONFIRMED),
            data_missing=(s in unavailable_statuses),
            missing_reason=(
                str(vals["reason"]) if s in unavailable_statuses and "reason" in vals else None
            ),
            current_values={k: v for k, v in vals.items() if k != "reason"},
            threshold=threshold,
        )
        for i, (s, name, vals, threshold) in enumerate(signals_data)
    ]

    now = datetime.now(tz=UTC)
    result = Framework29Result(
        signals_confirmed=signals_confirmed,
        signals_unavailable=signals_unavailable,
        and_gate_passed=gate_passed,
        gate_status=gate_status_str,
        gate_message=gate_message,
        signals=signals_out,
        data_gap_severity=_data_gap_severity(signals_unavailable),
        warning_messages=warning_messages,
        last_updated=now.isoformat(),
        data_age_minutes=0,
        cache_hit=False,
    )

    _cache_set(result)
    return result


def get_gate_status() -> Framework29GateStatus | None:
    """Return lightweight gate status from cache without triggering a fetch.

    Returns None if no cached result exists.
    """
    cached, _age = _cache_get()
    if cached is None:
        return None
    return Framework29GateStatus(
        and_gate_passed=cached.and_gate_passed,
        signals_confirmed=cached.signals_confirmed,
        signals_unavailable=cached.signals_unavailable,
        gate_status=cached.gate_status,
        data_gap_severity=cached.data_gap_severity,
    )


