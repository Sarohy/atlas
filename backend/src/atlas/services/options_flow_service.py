"""F4 Options Flow service (v2 — 3-tier market-cap anchor scoring).

Data sources:
  1. Unusual Whales — GET /api/darkpool/{ticker}                (dark-pool prints)
  2. Unusual Whales — GET /api/option-trades/flow-alerts        (options flow alerts)
  3. Polygon.io     — GET /v3/reference/tickers/{ticker}         (market cap)

Pipeline (per ticker):
  1. Excluded-ticker check (10 OTC/ADR symbols → DATA_GAP, no API calls).
  2. Three concurrent fetches: market cap, dark-pool prints, flow-alerts.
  3. Tier = LARGE / MID / SMALL from market cap (>$50B / $5B-$50B / <$5B).
  4. Filter prints to the last 5 trading sessions (rolling window).
  5. Classify each dark-pool print as BUY / SELL / SETTLEMENT (NBBO anchored).
     Strip SETTLEMENT. dark_pool_net_flow = sum(BUY $) - sum(SELL $).
  6. Aggregate flow-alert records: net_options_flow = sum(call ask_prem)
     - sum(put ask_prem). Each alert carries total_ask_side_prem / type.
  7. Map each net flow → 0-100 score via the tier's anchor table
     (linear interpolation, clamped 0-100).
  8. Combine: 50/50 average when both available; single source otherwise.
     Neither available → f4_score = 50, DATA_GAP flag.
  9. Derive flow_direction from the sign of the combined net flow.
 10. Compute f4_grade (STRONG BUY / BUY / NEUTRAL / WEAK / AVOID).

Pure helpers (prefix `_`) contain no I/O. Network I/O lives only in the
`_fetch_*` coroutines and the public `compute_options_flow()`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

import httpx

from atlas.schemas.options_flow import OptionsFlowResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint + network configuration
# ---------------------------------------------------------------------------

_TIMEOUT: Final[float] = 10.0
_UW_BASE_URL: Final[str] = "https://api.unusualwhales.com"
_POLYGON_BASE_URL: Final[str] = "https://api.polygon.io"

# In-memory cache: avoids burning through the 120 req/min UW rate limit on
# repeated page refreshes.  Entries expire after 5 minutes.
_F4_CACHE_TTL: Final[timedelta] = timedelta(minutes=5)
_f4_cache: dict[str, tuple[datetime, OptionsFlowResponse]] = {}

# UW pagination cap. 5 sessions x ~200 prints/day ~= 1000 prints for very
# liquid names; a single 500-print batch covers most cases and accepts a
# small chance of truncation for the busiest tickers.
_UW_FETCH_LIMIT: Final[int] = 500

# Rolling window length: F4 v2 always evaluates the last 5 trading sessions.
_F4_LOOKBACK_SESSIONS: Final[int] = 5

# Exceptional Conviction support: dark-pool BUY prints >$1M counted for F9.
_F4_LARGE_DP_BUY_USD: Final[float] = 1_000_000.0

# Grade thresholds (kept identical to legacy F4 + F9 grading).
_GRADE_STRONG_BUY_MIN: Final[int] = 80
_GRADE_BUY_MIN: Final[int] = 60
_GRADE_NEUTRAL_MIN: Final[int] = 40
_GRADE_WEAK_MIN: Final[int] = 20

# Flow-direction labels.
_FLOW_BULLISH: Final[str] = "BULLISH"
_FLOW_BEARISH: Final[str] = "BEARISH"
_FLOW_NEUTRAL: Final[str] = "NEUTRAL"


def _grade_from_score(score: int) -> str:
    """Map an F4 score (0-100) to a grade label."""
    if score >= _GRADE_STRONG_BUY_MIN:
        return "STRONG BUY"
    if score >= _GRADE_BUY_MIN:
        return "BUY"
    if score >= _GRADE_NEUTRAL_MIN:
        return "NEUTRAL"
    if score >= _GRADE_WEAK_MIN:
        return "WEAK"
    return "AVOID"


def _derive_flow_direction(
    dp_net_flow: float | None,
    opt_net_flow: float | None,
) -> str:
    """Derive BULLISH / BEARISH / NEUTRAL from signed net flows.

    Combines the two net flows (treating missing as 0). Positive → BULLISH,
    negative → BEARISH, zero → NEUTRAL.
    """
    combined = (dp_net_flow or 0.0) + (opt_net_flow or 0.0)
    if combined > 0:
        return _FLOW_BULLISH
    if combined < 0:
        return _FLOW_BEARISH
    return _FLOW_NEUTRAL


def _filter_to_recent_sessions(
    prints: list[dict[str, Any]],
    timestamp_key: str = "executed_at",
    n: int = _F4_LOOKBACK_SESSIONS,
) -> list[dict[str, Any]]:
    """Keep only prints whose date belongs to the N most recent unique sessions.

    Parses ISO-8601 timestamps under `timestamp_key`. Prints missing or with
    unparseable timestamps are dropped. Pure function.
    """
    dated: list[tuple[str, dict[str, Any]]] = []
    for rec in prints:
        ts = rec.get(timestamp_key)
        if not isinstance(ts, str):
            continue
        try:
            # Handle trailing 'Z' for compatibility with Python < 3.11.
            iso = ts.replace("Z", "+00:00")
            day = datetime.fromisoformat(iso).astimezone(UTC).date().isoformat()
        except ValueError:
            continue
        dated.append((day, rec))

    if not dated:
        return []

    distinct_days = sorted({d for d, _ in dated}, reverse=True)[:n]
    window = set(distinct_days)
    return [rec for d, rec in dated if d in window]


# ---------------------------------------------------------------------------
# Network I/O — Polygon market cap
# ---------------------------------------------------------------------------


async def _fetch_market_cap(client: httpx.AsyncClient, ticker: str, api_key: str) -> float | None:
    """Fetch market cap (USD) for *ticker* from Polygon.

    Returns None on any error; the caller defaults the tier to SMALL when
    the market cap is unknown (per locked Q1 default).
    """
    if not api_key:
        return None
    try:
        resp = await client.get(
            f"{_POLYGON_BASE_URL}/v3/reference/tickers/{ticker}",
            params={"apiKey": api_key},
        )
        resp.raise_for_status()
        payload: Any = resp.json()
        if not isinstance(payload, dict):
            return None
        results = payload.get("results")
        if not isinstance(results, dict):
            return None
        mcap = results.get("market_cap")
        return float(mcap) if isinstance(mcap, (int, float)) else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Network I/O — UW dark pool prints
# ---------------------------------------------------------------------------


async def _fetch_dark_pool_prints(
    client: httpx.AsyncClient, ticker: str, headers: dict[str, str]
) -> list[dict[str, Any]] | None:
    """Fetch raw dark-pool prints for *ticker* from Unusual Whales.

    Returns a list of dict records (each with `price`, `nbbo_bid`,
    `nbbo_ask`, `sale_cond_codes`, `executed_at`, `size`, `premium`).
    Returns None when the API call fails — caller treats None as
    "dark-pool data unavailable" (DARK_POOL_ONLY / DATA_GAP partial).
    """
    try:
        resp = await client.get(
            f"{_UW_BASE_URL}/api/darkpool/{ticker}",
            params={"limit": _UW_FETCH_LIMIT},
            headers=headers,
        )
        resp.raise_for_status()
        payload: Any = resp.json()
        raw: list[Any] = (
            payload
            if isinstance(payload, list)
            else payload.get("data", payload.get("darkpool", []))
        )
        return [rec for rec in raw if isinstance(rec, dict) and not rec.get("canceled")]
    except (httpx.HTTPError, ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Network I/O — UW flow alerts (replaces the old flow-recent endpoint)
# ---------------------------------------------------------------------------

# Maximum pages to fetch per call. 4 pages × 200 = 800 alerts — enough to
# cover 5 sessions of even the most active large-cap names.
_UW_FLOW_ALERTS_MAX_PAGES: Final[int] = 4


async def _fetch_option_flow_alerts(
    client: httpx.AsyncClient, ticker: str, headers: dict[str, str]
) -> list[dict[str, Any]] | None:
    """Fetch flow-alert records for *ticker* from Unusual Whales.

    Uses /api/option-trades/flow-alerts?ticker_symbol={ticker} — the canonical
    endpoint that replaces the deprecated per-ticker flow-recent tape.  Each
    alert represents an aggregated sweep, block, or repeated-hit event and
    exposes total_ask_side_prem / total_bid_side_prem broken out by call/put.

    Paginates backwards via the ``older_than`` cursor until 5 distinct session
    days are covered or _UW_FLOW_ALERTS_MAX_PAGES pages are exhausted.

    Returns None on API error; returns whatever was collected on partial errors.
    """
    all_alerts: list[dict[str, Any]] = []
    params: dict[str, Any] = {"ticker_symbol": ticker, "limit": 200}

    for _ in range(_UW_FLOW_ALERTS_MAX_PAGES):
        try:
            resp = await client.get(
                f"{_UW_BASE_URL}/api/option-trades/flow-alerts",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload: Any = resp.json()
        except (httpx.HTTPError, ValueError, TypeError):
            # Return whatever we have so far; None only if we have nothing.
            return all_alerts if all_alerts else None

        if not isinstance(payload, dict):
            break
        batch: list[Any] = payload.get("data", [])
        if not isinstance(batch, list) or not batch:
            break

        all_alerts.extend(r for r in batch if isinstance(r, dict))

        # Stop once we have data from at least _F4_LOOKBACK_SESSIONS distinct days.
        distinct_days = {
            r.get("created_at", "")[:10]
            for r in all_alerts
            if r.get("created_at")
        }
        if len(distinct_days) >= _F4_LOOKBACK_SESSIONS:
            break

        # Paginate: request alerts older than the last record in this batch.
        oldest_ts = batch[-1].get("created_at") if batch else None
        if not oldest_ts:
            break
        params = {"ticker_symbol": ticker, "limit": 200, "older_than": oldest_ts}

    return all_alerts if all_alerts else None


# ---------------------------------------------------------------------------
# Aggregation helpers — score dark-pool + options prints
# ---------------------------------------------------------------------------


def _safe_float(value: Any) -> float | None:
    """Best-effort coerce *value* to float. Returns None when not numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _print_premium_usd(rec: dict[str, Any]) -> float:
    """Return the premium of a dark-pool print in USD.

    Prefers an explicit `premium` field; falls back to size * price.
    Returns 0 when neither path yields a usable number.
    """
    raw_prem = _safe_float(rec.get("premium"))
    if raw_prem is not None and raw_prem > 0:
        return raw_prem
    size = _safe_float(rec.get("size")) or 0.0
    price = _safe_float(rec.get("price")) or 0.0
    return size * price


def _aggregate_dark_pool(
    prints: list[dict[str, Any]],
) -> tuple[float, int, int, float | None]:
    """Aggregate classified dark-pool prints over the window.

    Returns (net_flow_usd, total_prints_count, large_buy_count, largest_buy_usd).
    """
    net_flow = 0.0
    total = 0
    large_buys = 0
    largest_buy: float = 0.0

    for rec in prints:
        price = _safe_float(rec.get("price"))
        if price is None:
            continue
        bid = _safe_float(rec.get("nbbo_bid"))
        ask = _safe_float(rec.get("nbbo_ask"))
        codes_raw = rec.get("sale_cond_codes") or ()
        codes: tuple[str, ...] = (
            tuple(c for c in codes_raw if isinstance(c, str))
            if isinstance(codes_raw, (list, tuple))
            else ()
        )

        cls = _classify_dark_pool_print(price, bid, ask, codes)
        if cls == "SETTLEMENT":
            continue

        prem = _print_premium_usd(rec)
        if prem <= 0:
            continue

        total += 1
        if cls == "BUY":
            net_flow += prem
            if prem > largest_buy:
                largest_buy = prem
            if prem >= _F4_LARGE_DP_BUY_USD:
                large_buys += 1
        else:  # SELL
            net_flow -= prem

    return (
        net_flow,
        total,
        large_buys,
        largest_buy if largest_buy > 0 else None,
    )


def _aggregate_options(
    trades: list[dict[str, Any]],
) -> tuple[float, float | None]:
    """Aggregate classified option trades over the window.

    Returns (net_flow_usd, largest_bullish_premium_usd).
    Net flow = sum(NEW_BULL + PUT_SELL) - sum(NEW_BEAR). PROFIT_TAKING and
    SPREAD_CROSS are stripped.
    """
    net_flow = 0.0
    largest_bull: float = 0.0
    today = datetime.now(UTC).date()

    for rec in trades:
        side = rec.get("side") if isinstance(rec.get("side"), str) else None
        opt_type = rec.get("option_type") or rec.get("type") or ""
        if not isinstance(opt_type, str):
            continue

        delta = _safe_float(rec.get("delta"))
        dte: int | None = None
        expiry = rec.get("expiry") or rec.get("expiration") or rec.get("expiry_date")
        if isinstance(expiry, str):
            try:
                exp_date = datetime.fromisoformat(expiry.replace("Z", "+00:00")).date()
                dte = (exp_date - today).days
            except ValueError:
                dte = None

        cls = _classify_options_print(side=side, option_type=opt_type, dte=dte, delta=delta)
        if cls in ("PROFIT_TAKING", "SPREAD_CROSS"):
            continue

        prem = _safe_float(rec.get("premium")) or 0.0
        if prem <= 0:
            continue

        if cls in ("NEW_BULL", "PUT_SELL"):
            net_flow += prem
            if prem > largest_bull:
                largest_bull = prem
        elif cls == "NEW_BEAR":
            net_flow -= prem

    return net_flow, (largest_bull if largest_bull > 0 else None)


def _aggregate_flow_alerts(
    alerts: list[dict[str, Any]],
) -> tuple[float, float | None]:
    """Aggregate flow-alert records into an options net-flow figure.

    Each alert carries ``total_ask_side_prem`` (bullish) and ``type``
    (``"call"`` / ``"put"``).  Net flow is:

        net = sum(call total_ask_side_prem) − sum(put total_ask_side_prem)

    Positive → net call buying (bullish); negative → net put buying (bearish).

    Returns ``(net_flow_usd, largest_single_alert_premium_usd)``.
    """
    net_flow = 0.0
    largest_bull: float = 0.0

    for rec in alerts:
        opt_type = str(rec.get("type", "")).lower()
        ask_prem = _safe_float(rec.get("total_ask_side_prem")) or 0.0
        total_prem = _safe_float(rec.get("total_premium")) or 0.0

        if opt_type == "call":
            net_flow += ask_prem
            if total_prem > largest_bull:
                largest_bull = total_prem
        elif opt_type == "put":
            net_flow -= ask_prem

    return net_flow, (largest_bull if largest_bull > 0 else None)


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def _build_excluded_response(ticker: str) -> OptionsFlowResponse:
    """Return the canonical DATA_GAP response for excluded OTC/ADR tickers."""
    return OptionsFlowResponse(
        ticker=ticker,
        f4_score=_F4_NEUTRAL_SCORE,
        f4_grade=_grade_from_score(_F4_NEUTRAL_SCORE),
        dark_pool_score=None,
        options_flow_score=None,
        dark_pool_net_flow_usd=None,
        options_net_flow_usd=None,
        market_cap_usd=None,
        market_cap_tier=_pick_tier(None),
        flow_direction=_FLOW_NEUTRAL,
        data_source=_F4_SOURCE_DATA_GAP,
        data_gap_reason="Ticker on F4 OTC/ADR exclusion list — no upstream API calls.",
        lookback_sessions=_F4_LOOKBACK_SESSIONS,
        dark_pool_prints_count=0,
        dark_pool_large_buy_count=0,
        largest_dark_pool_buy_usd=None,
        largest_options_buy_usd=None,
    )


def _build_response_v2(
    *,
    ticker: str,
    market_cap: float | None,
    dp_prints: list[dict[str, Any]] | None,
    opt_trades: list[dict[str, Any]] | None,
) -> OptionsFlowResponse:
    """Build the F4 v2 response from raw fetched data.

    None for dp_prints / opt_trades signals "data source unavailable" and
    propagates into the data_source label + sub-score nullification.
    """
    tier = _pick_tier(market_cap)

    # Dark-pool branch ----------------------------------------------------
    dp_score: int | None
    dp_net_flow: float | None
    dp_count = 0
    dp_large_buys = 0
    largest_dp_buy: float | None = None
    if dp_prints is None:
        dp_score = None
        dp_net_flow = None
    else:
        windowed_dp = _filter_to_recent_sessions(dp_prints)
        dp_net_flow, dp_count, dp_large_buys, largest_dp_buy = _aggregate_dark_pool(windowed_dp)
        dp_score = _map_net_flow_to_score(dp_net_flow, tier)

    # Options branch ------------------------------------------------------
    opt_score: int | None
    opt_net_flow: float | None
    largest_opt_buy: float | None = None
    if opt_trades is None:
        opt_score = None
        opt_net_flow = None
    else:
        windowed_opts = _filter_to_recent_sessions(opt_trades, timestamp_key="created_at")
        opt_net_flow, largest_opt_buy = _aggregate_flow_alerts(windowed_opts)
        opt_score = _map_net_flow_to_score(opt_net_flow, tier)

    f4_raw, source = _combine_f4_scores(dp_score, opt_score)
    direction = _derive_flow_direction(dp_net_flow, opt_net_flow)

    gap_reason: str | None = None
    if source == _F4_SOURCE_DATA_GAP:
        gap_reason = "Both dark-pool and options data unavailable."
    elif source == _F4_SOURCE_DP_ONLY:
        gap_reason = "Options trades unavailable — score based on dark-pool only."
    elif source == _F4_SOURCE_OPT_ONLY:
        gap_reason = "Dark-pool data unavailable — score based on options only."

    return OptionsFlowResponse(
        ticker=ticker,
        f4_score=f4_raw,
        f4_grade=_grade_from_score(f4_raw),
        dark_pool_score=dp_score,
        options_flow_score=opt_score,
        dark_pool_net_flow_usd=dp_net_flow,
        options_net_flow_usd=opt_net_flow,
        market_cap_usd=market_cap,
        market_cap_tier=tier,
        flow_direction=direction,
        data_source=source,
        data_gap_reason=gap_reason,
        lookback_sessions=_F4_LOOKBACK_SESSIONS,
        dark_pool_prints_count=dp_count,
        dark_pool_large_buy_count=dp_large_buys,
        largest_dark_pool_buy_usd=largest_dp_buy,
        largest_options_buy_usd=largest_opt_buy,
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class OptionsFlowService:
    """Compute the F4 Options Flow score from Unusual Whales + Polygon."""

    def __init__(self, api_key: str, polygon_api_key: str | None = None) -> None:
        self._uw_api_key = api_key
        # Lazy import to avoid touching settings during module import (tests
        # construct the service with explicit keys).
        if polygon_api_key is None:
            try:
                from atlas.config import get_settings

                polygon_api_key = get_settings().polygon_api_key
            except Exception:
                polygon_api_key = ""
        self._polygon_api_key = polygon_api_key or ""
        self._uw_headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    @classmethod
    def from_env(cls) -> OptionsFlowService:
        return cls(
            api_key=os.environ.get("UNUSUAL_WHALES_API_KEY", ""),
            polygon_api_key=os.environ.get("POLYGON_API_KEY", ""),
        )

    async def compute_options_flow(self, ticker: str) -> OptionsFlowResponse:
        """Fetch UW + Polygon data and return the F4 v2 response."""
        ticker = ticker.upper()

        # Step 1: excluded-ticker short-circuit.
        if _is_excluded_ticker(ticker):
            return _build_excluded_response(ticker)

        # Step 1b: return cached result if still fresh.
        cached = _f4_cache.get(ticker)
        if cached is not None:
            cached_at, cached_response = cached
            if datetime.now(UTC) - cached_at < _F4_CACHE_TTL:
                logger.debug("[F4] %s served from cache (age=%s)", ticker,
                             datetime.now(UTC) - cached_at)
                return cached_response

        # Step 2: three concurrent fetches — retry UW calls once on failure.
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            market_cap, dp_prints, opt_trades = await asyncio.gather(
                _fetch_market_cap(client, ticker, self._polygon_api_key),
                _fetch_dark_pool_prints(client, ticker, self._uw_headers),
                _fetch_option_flow_alerts(client, ticker, self._uw_headers),
            )

        # Retry whichever UW call returned None — single retry with 1s backoff.
        if dp_prints is None or opt_trades is None:
            await asyncio.sleep(1.0)
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if dp_prints is None and opt_trades is None:
                    dp_prints, opt_trades = await asyncio.gather(
                        _fetch_dark_pool_prints(client, ticker, self._uw_headers),
                        _fetch_option_flow_alerts(client, ticker, self._uw_headers),
                    )
                elif dp_prints is None:
                    dp_prints = await _fetch_dark_pool_prints(client, ticker, self._uw_headers)
                else:
                    opt_trades = await _fetch_option_flow_alerts(client, ticker, self._uw_headers)

        # Step 3: aggregate + score + build response.
        result = _build_response_v2(
            ticker=ticker,
            market_cap=market_cap,
            dp_prints=dp_prints,
            opt_trades=opt_trades,
        )

        # Cache only real data (not data-gap fallbacks) to avoid caching stale 50s.
        if dp_prints is not None or opt_trades is not None:
            _f4_cache[ticker] = (datetime.now(UTC), result)

        return result


# ===========================================================================
# F4 v2 — new spec (3-tier market-cap-based net-flow anchor scoring).
#
# The functions below are the new pure scoring primitives. Phase 2 will wire
# them into compute_options_flow() and delete the legacy v7.3.4 helpers above.
# They live here (rather than a new module) per the in-place repurpose plan.
# ===========================================================================

# Net-flow direction classifications --------------------------------------
DPClassification = Literal["BUY", "SELL", "SETTLEMENT"]
OptionsClassification = Literal["NEW_BULL", "PUT_SELL", "NEW_BEAR", "PROFIT_TAKING", "SPREAD_CROSS"]
MarketCapTier = Literal["LARGE", "MID", "SMALL"]

# OTC / ADR exclusion list (per locked Q3). These tickers return F4 = 50
# with a DATA_GAP flag and skip all upstream API calls.
_F4_EXCLUDED_TICKERS: Final[frozenset[str]] = frozenset(
    {
        "LSRCF",
        "LPKFF",
        "SLOIF",
        "AIXXF",
        "BESIY",
        "SIVE",
        "TOELY",
        "AJINF",
        "SHECY",
        "ATEYY",
    }
)

# Market-cap tier thresholds (USD). LARGE > $50B; MID $5B-$50B; SMALL < $5B.
_F4_LARGE_CAP_FLOOR: Final[float] = 50_000_000_000.0
_F4_MID_CAP_FLOOR: Final[float] = 5_000_000_000.0

# Net-flow anchor tables — (net_flow_usd_anchor, score_anchor) ordered
# monotonically increasing in net_flow. Linear interpolation between adjacent
# anchors; flat extrapolation outside the endpoints (clamped to [0, 100]).
# Inside the ±neutral band both anchors map to score 50 → flat neutral plateau.
_F4_DP_ANCHORS_LARGE: Final[tuple[tuple[float, int], ...]] = (
    (-100_000_000.0, 0),
    (-25_000_000.0, 25),
    (-5_000_000.0, 50),
    (5_000_000.0, 50),
    (25_000_000.0, 75),
    (100_000_000.0, 100),
)
_F4_DP_ANCHORS_MID: Final[tuple[tuple[float, int], ...]] = (
    (-20_000_000.0, 0),
    (-5_000_000.0, 25),
    (-1_000_000.0, 50),
    (1_000_000.0, 50),
    (5_000_000.0, 75),
    (20_000_000.0, 100),
)
_F4_DP_ANCHORS_SMALL: Final[tuple[tuple[float, int], ...]] = (
    (-3_000_000.0, 0),
    (-750_000.0, 25),
    (-150_000.0, 50),
    (150_000.0, 50),
    (750_000.0, 75),
    (3_000_000.0, 100),
)

# Dark pool BUY/SELL classification (NBBO-anchored).
# price >= ask * 0.999 -> BUY ; price <= bid * 1.001 -> SELL ; else by midpoint.
_F4_AT_OR_ABOVE_ASK_FACTOR: Final[float] = 0.999
_F4_AT_OR_BELOW_BID_FACTOR: Final[float] = 1.001

# Sale-condition codes that mark a print as a settlement / non-directional
# print (stripped from the net-flow calculation entirely).
_F4_SETTLEMENT_CODES: Final[frozenset[str]] = frozenset(
    {
        "average_price",
        "prior_reference",
        "qualified_contingent",
    }
)

# Options PROFIT_TAKING detection (per locked Q2): call sold on BID AND
# (DTE ≤ 14 OR |delta| ≥ 0.8). Long-dated OTM calls sold on BID are also
# stripped (caller responsibility — see Q2 default).
_F4_NEAR_DATED_DTE: Final[int] = 14
_F4_DEEP_ITM_DELTA: Final[float] = 0.8

# UW 'side' field literals (set by Unusual Whales option-trades endpoint).
_UW_SIDE_ASK: Final[str] = "ASK"
_UW_SIDE_BID: Final[str] = "BID"
_UW_SIDE_NONE: Final[str] = "NONE"

# Output constants ---------------------------------------------------------
_F4_NEUTRAL_SCORE: Final[int] = 50
_F4_DISPLAY_DIVISOR: Final[int] = 100
_F4_DISPLAY_MAX: Final[int] = 15

# Data-source labels for F4 response.
_F4_SOURCE_BOTH: Final[str] = "BOTH"
_F4_SOURCE_DP_ONLY: Final[str] = "DARK_POOL_ONLY"
_F4_SOURCE_OPT_ONLY: Final[str] = "OPTIONS_ONLY"
_F4_SOURCE_DATA_GAP: Final[str] = "DATA_GAP"


def _is_excluded_ticker(ticker: str) -> bool:
    """Return True when the ticker is on the hard-coded OTC/ADR exclusion list.

    Excluded tickers return F4 = 50 with a DATA_GAP flag without hitting any
    upstream API. Comparison is case-insensitive.
    """
    return ticker.upper() in _F4_EXCLUDED_TICKERS


def _pick_tier(market_cap_usd: float | None) -> MarketCapTier:
    """Map market cap → LARGE | MID | SMALL.

    LARGE: > $50B ; MID: $5B-$50B (inclusive at $5B) ; SMALL: < $5B or unknown.
    Unknown market cap (None) defaults to SMALL (most conservative anchors).
    """
    if market_cap_usd is None:
        return "SMALL"
    if market_cap_usd > _F4_LARGE_CAP_FLOOR:
        return "LARGE"
    if market_cap_usd >= _F4_MID_CAP_FLOOR:
        return "MID"
    return "SMALL"


def _anchors_for_tier(tier: MarketCapTier) -> tuple[tuple[float, int], ...]:
    """Return the anchor table for a tier."""
    if tier == "LARGE":
        return _F4_DP_ANCHORS_LARGE
    if tier == "MID":
        return _F4_DP_ANCHORS_MID
    return _F4_DP_ANCHORS_SMALL


def _map_net_flow_to_score(net_flow_usd: float, tier: MarketCapTier) -> int:
    """Map a signed net-flow USD value to a 0-100 score for the given tier.

    Linear interpolation between adjacent anchors; clamps to [0, 100] outside
    the endpoints. Inside the neutral band both anchors are 50 → flat plateau.
    """
    anchors = _anchors_for_tier(tier)
    # Clamp below the lowest anchor.
    if net_flow_usd <= anchors[0][0]:
        return anchors[0][1]
    # Clamp above the highest anchor.
    if net_flow_usd >= anchors[-1][0]:
        return anchors[-1][1]
    # Linear interpolation between the two surrounding anchors.
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= net_flow_usd <= x1:
            if x1 == x0:  # Identical x — should not occur; defensive.
                return y0
            ratio = (net_flow_usd - x0) / (x1 - x0)
            interpolated = y0 + ratio * (y1 - y0)
            return max(0, min(100, round(interpolated)))
    return _F4_NEUTRAL_SCORE  # Unreachable; defensive fallback.


def _classify_dark_pool_print(
    price: float,
    bid: float | None,
    ask: float | None,
    sale_cond_codes: tuple[str, ...] = (),
) -> DPClassification:
    """Classify a single dark pool print as BUY / SELL / SETTLEMENT.

    Settlement codes win first; then NBBO-anchored BUY/SELL bands; then
    midpoint-relative fallback. Missing bid/ask falls back to BUY.
    """
    # 1. Settlement code overrides everything.
    if any(code in _F4_SETTLEMENT_CODES for code in sale_cond_codes):
        return "SETTLEMENT"
    # 4/5. No NBBO data — conservative fallback.
    if bid is None or ask is None:
        return "BUY"
    # 2. At/above ask → BUY.
    if price >= ask * _F4_AT_OR_ABOVE_ASK_FACTOR:
        return "BUY"
    # 3. At/below bid → SELL.
    if price <= bid * _F4_AT_OR_BELOW_BID_FACTOR:
        return "SELL"
    # 4/5. Midpoint split.
    midpoint = (bid + ask) / 2.0
    return "BUY" if price >= midpoint else "SELL"


def _classify_options_print(
    side: str | None,
    option_type: str,
    dte: int | None,
    delta: float | None,
) -> OptionsClassification:
    """Classify an options print using UW 'side' + option_type + DTE + delta."""
    if side is None or side.upper() == _UW_SIDE_NONE:
        return "SPREAD_CROSS"
    side_up = side.upper()
    opt = option_type.lower()
    if opt == "call" and side_up == _UW_SIDE_ASK:
        return "NEW_BULL"
    if opt == "put" and side_up == _UW_SIDE_BID:
        return "PUT_SELL"
    if opt == "put" and side_up == _UW_SIDE_ASK:
        return "NEW_BEAR"
    if opt == "call" and side_up == _UW_SIDE_BID:
        # Call sold on BID — always PROFIT_TAKING per locked Q2 (near-dated,
        # deep-ITM, OR long-dated OTM all collapse to PROFIT_TAKING / strip).
        return "PROFIT_TAKING"
    return "SPREAD_CROSS"


def _combine_f4_scores(
    dp_score: int | None,
    opt_score: int | None,
) -> tuple[int, str]:
    """Combine dark-pool + options scores into a single F4_raw + source label."""
    if dp_score is not None and opt_score is not None:
        return (round((dp_score + opt_score) / 2), _F4_SOURCE_BOTH)
    if dp_score is not None:
        return (dp_score, _F4_SOURCE_DP_ONLY)
    if opt_score is not None:
        return (opt_score, _F4_SOURCE_OPT_ONLY)
    return (_F4_NEUTRAL_SCORE, _F4_SOURCE_DATA_GAP)
