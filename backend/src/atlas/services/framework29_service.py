"""Framework 29 — Capitulation / Re-Entry AND Gate service.

Five market signals are evaluated; 3 of 5 confirmed fires the GREEN LIGHT.

Signal list:
  1. VIX 5-day SMA declining for ≥2 consecutive sessions
  2. Put/call ratio < 1.2 for the last 3 consecutive sessions
  3. SPY closing above its 200-day SMA for ≥2 consecutive sessions
  4. Net institutional ETF flow turning positive (manual if API unavailable)
  5. Brent crude below its declining 7-day SMA

Data sources:
  • Polygon.io — Signals 1, 3, 5 (VIX aggs via I:VIX, SPY aggs, Brent via BZ)
  • Unusual Whales — Signals 2, 4 (put/call ratio, ETF flow)

Caching:
  Results are cached in an in-memory dict for 15 minutes (900 s).
  Signal 4 manual confirmations are stored in a module-level dict keyed by
  date string (YYYY-MM-DD) and reset automatically on the next calendar day.

Pure helpers (prefixed with underscore) are I/O-free and unit-testable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Final

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

# Signal thresholds.
_VIX_SMA_WINDOW: Final[int] = 5          # 5-day SMA for VIX
_VIX_LOOKBACK_DAYS: Final[int] = 12      # trading days to fetch
_PCR_THRESHOLD: Final[float] = 1.2       # put/call ratio must be below this
_PCR_SESSIONS_REQUIRED: Final[int] = 3   # consecutive sessions below threshold
_SPY_DMA_WINDOW: Final[int] = 200        # 200-day SMA for SPY
_SPY_LOOKBACK_DAYS: Final[int] = 215     # trading days to fetch
_SPY_SESSIONS_REQUIRED: Final[int] = 2   # consecutive closes above DMA
_BRENT_SMA_WINDOW: Final[int] = 7        # 7-day SMA for Brent
_BRENT_LOOKBACK_DAYS: Final[int] = 12    # trading days to fetch

# Polygon tickers.
_POLYGON_VIX_TICKER: Final[str] = "I:VIX"
_POLYGON_SPY_TICKER: Final[str] = "SPY"
_POLYGON_BRENT_TICKER: Final[str] = "BZ"

# Polygon aggs base URL.
_POLYGON_AGGS_URL: Final[str] = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"

# Unusual Whales API base URL.
_UW_BASE_URL: Final[str] = "https://api.unusualwhales.com"

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# In-memory result cache: key -> (result, unix_timestamp)
_cache: dict[str, tuple[Framework29Result, float]] = {}

# Manual signal confirmations: date_str -> {signal: int, confirmed: bool, reason: str}
_manual_confirmations: dict[str, dict[str, Any]] = {}


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
# Manual confirmation helpers
# ---------------------------------------------------------------------------


def set_manual_confirmation(signal: int, confirmed: bool, reason: str) -> None:
    """Store a manual confirmation for Signal 4 (institutional ETF flow).

    Keyed by today's date so it auto-expires at midnight.
    Only Signal 4 supports manual confirmation in V1.
    """
    today = date.today().isoformat()
    _manual_confirmations[today] = {
        "signal": signal,
        "confirmed": confirmed,
        "reason": reason,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    _cache_invalidate()


def _get_today_manual_confirmation() -> dict[str, Any] | None:
    """Return today's manual confirmation dict if set, otherwise None."""
    today = date.today().isoformat()
    return _manual_confirmations.get(today)


# ---------------------------------------------------------------------------
# Pure calculation helpers
# ---------------------------------------------------------------------------


def _compute_sma(closes: list[float], window: int) -> list[float]:
    """Compute a simple moving average over closes. Returns a list of SMA values.

    The result has the same length as closes; the first (window-1) values are NaN
    (represented as 0.0 here, but callers must check index >= window-1 before use).
    """
    sma: list[float] = []
    for i, _ in enumerate(closes):
        if i < window - 1:
            sma.append(0.0)
        else:
            sma.append(sum(closes[i - window + 1 : i + 1]) / window)
    return sma


def _is_sma_declining(sma_values: list[float], window: int, sessions: int = 2) -> bool:
    """Return True if the SMA has declined for the last 'sessions' periods.

    Requires at least (window + sessions) values so the SMA is valid.
    """
    if len(sma_values) < window + sessions:
        return False
    valid = sma_values[window - 1 :]  # first valid SMA values
    if len(valid) < sessions + 1:
        return False
    # Check each consecutive pair in the last (sessions + 1) entries.
    tail = valid[-(sessions + 1) :]
    for i in range(sessions):
        if tail[i + 1] >= tail[i]:
            return False
    return True


def _check_signal1_vix(closes: list[float]) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 1: VIX 5-day SMA declining for ≥2 sessions. Pure function."""
    if len(closes) < _VIX_SMA_WINDOW + 2:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient VIX history"}

    sma = _compute_sma(closes, _VIX_SMA_WINDOW)
    declining = _is_sma_declining(sma, _VIX_SMA_WINDOW, sessions=2)
    latest_close = closes[-1]
    latest_sma = sma[-1]
    prev_sma = sma[-2]

    status = SignalStatus.CONFIRMED if declining else SignalStatus.NOT_MET
    return status, {
        "vix_latest_close": round(latest_close, 2),
        "vix_5d_sma": round(latest_sma, 3),
        "vix_5d_sma_prev": round(prev_sma, 3),
        "declining": declining,
    }


def _check_signal2_pcr(pcr_sessions: list[float]) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 2: Put/call ratio < 1.2 for last 3 sessions. Pure function."""
    if len(pcr_sessions) < _PCR_SESSIONS_REQUIRED:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient put/call data"}

    tail = pcr_sessions[-_PCR_SESSIONS_REQUIRED:]
    all_below = all(r < _PCR_THRESHOLD for r in tail)
    status = SignalStatus.CONFIRMED if all_below else SignalStatus.NOT_MET
    return status, {
        "sessions_checked": _PCR_SESSIONS_REQUIRED,
        "threshold": _PCR_THRESHOLD,
        "values": [round(r, 3) for r in tail],
        "all_below_threshold": all_below,
    }


def _check_signal3_spy_dma(closes: list[float]) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 3: SPY close above 200-DMA for ≥2 consecutive sessions. Pure function."""
    if len(closes) < _SPY_DMA_WINDOW + 2:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient SPY history (need 202+ days)"}

    sma = _compute_sma(closes, _SPY_DMA_WINDOW)
    valid_sma = sma[_SPY_DMA_WINDOW - 1 :]
    valid_closes = closes[_SPY_DMA_WINDOW - 1 :]

    if len(valid_sma) < _SPY_SESSIONS_REQUIRED:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient SPY data after SMA warmup"}

    tail_sma = valid_sma[-_SPY_SESSIONS_REQUIRED:]
    tail_closes = valid_closes[-_SPY_SESSIONS_REQUIRED:]
    above = [c > s for c, s in zip(tail_closes, tail_sma)]
    confirmed = all(above)

    status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET
    return status, {
        "spy_latest_close": round(closes[-1], 2),
        "spy_200d_sma": round(sma[-1], 3),
        "consecutive_sessions_above": sum(1 for a in reversed(above) if a),
        "sessions_required": _SPY_SESSIONS_REQUIRED,
        "confirmed": confirmed,
    }


def _check_signal4_etf_flow(
    net_flow_usd: float | None,
    manual: dict[str, Any] | None,
) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 4: Institutional ETF flow net positive, or manual confirmation.

    If API data is available and net_flow_usd > 0 → CONFIRMED.
    If net_flow_usd ≤ 0 → NOT_MET (with manual override possible).
    If API unavailable → check manual confirmation, else MANUAL_REQUIRED.
    """
    if net_flow_usd is not None:
        if manual and manual.get("confirmed") and net_flow_usd <= 0:
            # Manual override of negative flow.
            return SignalStatus.CONFIRMED, {
                "net_flow_usd": round(net_flow_usd, 0),
                "manual_override": True,
                "manual_reason": manual.get("reason"),
            }
        positive = net_flow_usd > 0
        status = SignalStatus.CONFIRMED if positive else SignalStatus.NOT_MET
        return status, {
            "net_flow_usd": round(net_flow_usd, 0),
            "positive": positive,
            "manual_override": False,
        }

    # API unavailable — use manual confirmation if today's is set.
    if manual is not None:
        confirmed = bool(manual.get("confirmed", False))
        status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET
        return status, {
            "net_flow_usd": None,
            "api_unavailable": True,
            "manual_confirmed": confirmed,
            "manual_reason": manual.get("reason"),
        }

    return SignalStatus.MANUAL_REQUIRED, {
        "net_flow_usd": None,
        "api_unavailable": True,
        "manual_required": True,
    }


def _check_signal5_brent(closes: list[float]) -> tuple[SignalStatus, dict[str, object]]:
    """Signal 5: Brent crude below its declining 7-day SMA. Pure function."""
    if len(closes) < _BRENT_SMA_WINDOW + 2:
        return SignalStatus.UNAVAILABLE, {"reason": "Insufficient Brent history"}

    sma = _compute_sma(closes, _BRENT_SMA_WINDOW)
    latest_close = closes[-1]
    latest_sma = sma[-1]
    declining = _is_sma_declining(sma, _BRENT_SMA_WINDOW, sessions=2)
    below = latest_close < latest_sma
    confirmed = below and declining

    status = SignalStatus.CONFIRMED if confirmed else SignalStatus.NOT_MET
    return status, {
        "brent_latest_close": round(latest_close, 2),
        "brent_7d_sma": round(latest_sma, 3),
        "price_below_sma": below,
        "sma_declining": declining,
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
    skipped = unavailable  # UNAVAILABLE / MANUAL_REQUIRED signals are not counted
    effective_total = total - skipped

    if confirmed >= _GATE_THRESHOLD:
        return True, "GREEN_LIGHT", (
            f"AND gate open — {confirmed}/{total} signals confirmed "
            f"({skipped} unavailable, {effective_total} evaluated). "
            "Capitulation conditions met."
        )

    remaining = _GATE_THRESHOLD - confirmed
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


# ---------------------------------------------------------------------------
# Async data fetchers
# ---------------------------------------------------------------------------


async def _fetch_polygon_closes(
    ticker: str,
    lookback_days: int,
    api_key: str,
    client: httpx.AsyncClient,
) -> list[float] | None:
    """Fetch daily close prices from Polygon aggs endpoint.

    Returns a list of close prices (ascending chronological order) or None on error.
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
            params={"apiKey": api_key, "sort": "asc", "limit": lookback_days + 20},
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


async def _fetch_uw_put_call_ratio(
    api_key: str,
    client: httpx.AsyncClient,
) -> list[float] | None:
    """Fetch the last N sessions of put/call ratio from Unusual Whales.

    Returns a list of ratio values (ascending chronological) or None on error.
    """
    try:
        response = await client.get(
            f"{_UW_BASE_URL}/api/market/put-call-ratio",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": _PCR_SESSIONS_REQUIRED + 2},
            timeout=10.0,
        )

        if response.status_code != 200:
            logger.warning(
                "UW put/call ratio non-200",
                extra={"status": response.status_code},
            )
            return None

        data = response.json()
        # UW returns { "data": [{"date": "...", "ratio": 1.05}, ...] }
        entries = data.get("data", []) if isinstance(data, dict) else data
        if not entries:
            return None

        ratios = [float(e["ratio"]) for e in entries if "ratio" in e]
        return ratios if ratios else None

    except Exception as exc:
        logger.warning(
            "UW put/call ratio fetch failed",
            extra={"error": repr(exc)},
        )
        return None


async def _fetch_uw_etf_flow(
    api_key: str,
    client: httpx.AsyncClient,
) -> float | None:
    """Fetch net institutional ETF flow from Unusual Whales.

    Returns net flow in USD (positive = bullish, negative = bearish) or None.
    We aggregate net_flow for QQQ, SMH, SOXX, XLK as a proxy for tech institutions.
    """
    # Monitored ETFs for institutional tech flow.
    _ETF_TICKERS: Final[list[str]] = ["QQQ", "SMH", "SOXX", "XLK"]

    try:
        response = await client.get(
            f"{_UW_BASE_URL}/api/etf/flow",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"tickers": ",".join(_ETF_TICKERS)},
            timeout=10.0,
        )

        if response.status_code != 200:
            logger.warning(
                "UW ETF flow non-200",
                extra={"status": response.status_code},
            )
            return None

        data = response.json()
        entries = data.get("data", []) if isinstance(data, dict) else data
        if not entries:
            return None

        # Sum net flow across monitored ETFs.
        net_flow = sum(float(e.get("net_flow", 0)) for e in entries if "net_flow" in e)
        return net_flow

    except Exception as exc:
        logger.warning(
            "UW ETF flow fetch failed",
            extra={"error": repr(exc)},
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
        # Parallel fetch all external data.
        vix_closes_raw, pcr_raw, spy_closes_raw, etf_flow_raw, brent_closes_raw = (
            await asyncio.gather(
                _fetch_polygon_closes(_POLYGON_VIX_TICKER, _VIX_LOOKBACK_DAYS, polygon_api_key, _client),
                _fetch_uw_put_call_ratio(uw_api_key, _client),
                _fetch_polygon_closes(_POLYGON_SPY_TICKER, _SPY_LOOKBACK_DAYS, polygon_api_key, _client),
                _fetch_uw_etf_flow(uw_api_key, _client),
                _fetch_polygon_closes(_POLYGON_BRENT_TICKER, _BRENT_LOOKBACK_DAYS, polygon_api_key, _client),
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
    pcr_sessions: list[float] | None = _unwrap(pcr_raw)  # type: ignore[assignment]
    spy_closes: list[float] | None = _unwrap(spy_closes_raw)  # type: ignore[assignment]
    etf_flow: float | None = _unwrap(etf_flow_raw)  # type: ignore[assignment]
    brent_closes: list[float] | None = _unwrap(brent_closes_raw)  # type: ignore[assignment]

    manual = _get_today_manual_confirmation()

    # Evaluate each signal.
    s1_status, s1_vals = (
        _check_signal1_vix(vix_closes)
        if vix_closes
        else (SignalStatus.UNAVAILABLE, {"reason": "VIX data unavailable"})
    )
    s2_status, s2_vals = (
        _check_signal2_pcr(pcr_sessions)
        if pcr_sessions
        else (SignalStatus.UNAVAILABLE, {"reason": "Put/call data unavailable"})
    )
    s3_status, s3_vals = (
        _check_signal3_spy_dma(spy_closes)
        if spy_closes
        else (SignalStatus.UNAVAILABLE, {"reason": "SPY data unavailable"})
    )
    s4_status, s4_vals = _check_signal4_etf_flow(etf_flow, manual)
    s5_status, s5_vals = (
        _check_signal5_brent(brent_closes)
        if brent_closes
        else (SignalStatus.UNAVAILABLE, {"reason": "Brent data unavailable"})
    )

    signals_data = [
        (s1_status, "VIX 5-day SMA Declining", s1_vals, {"sessions_declining": 2, "sma_window": _VIX_SMA_WINDOW}),
        (s2_status, "Put/Call Ratio < 1.2 (3 sessions)", s2_vals, {"threshold": _PCR_THRESHOLD, "sessions": _PCR_SESSIONS_REQUIRED}),
        (s3_status, "SPY Above 200-DMA (2 sessions)", s3_vals, {"sma_window": _SPY_DMA_WINDOW, "sessions": _SPY_SESSIONS_REQUIRED}),
        (s4_status, "Institutional ETF Flow Net Positive", s4_vals, {"manual_eligible": True}),
        (s5_status, "Brent Below Declining 7-Day SMA", s5_vals, {"sma_window": _BRENT_SMA_WINDOW}),
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
    if s4_status == SignalStatus.MANUAL_REQUIRED:
        warning_messages.append(
            "Signal 4 (ETF flow) requires manual confirmation — "
            "POST /framework29/signals/confirm to set."
        )

    signals_out = [
        Framework29Signal(
            signal_number=i + 1,
            signal_name=name,
            status=s,
            confirmed=(s == SignalStatus.CONFIRMED),
            data_missing=(s in unavailable_statuses),
            missing_reason=vals.get("reason") if s in unavailable_statuses else None,
            current_values={k: v for k, v in vals.items() if k != "reason"},
            threshold=threshold,
        )
        for i, (s, name, vals, threshold) in enumerate(signals_data)
    ]

    now = datetime.now(tz=timezone.utc)
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
