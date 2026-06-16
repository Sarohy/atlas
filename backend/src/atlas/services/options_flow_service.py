"""F4 Options Flow service (v2 — 3-tier market-cap anchor scoring).

Data sources:
  1. Unusual Whales — GET /api/darkpool/{ticker}                (dark-pool prints)
  2. Unusual Whales — GET /api/option-trades/flow-alerts        (options flow — PRIMARY)
  3. Unusual Whales — GET /api/stock/{ticker}/flow-recent       (raw tape — fallback only)
  4. Polygon.io     — GET /v3/reference/tickers/{ticker}         (market cap)

F4 score source: the flow-ALERTS feed (source 2) — aggregated sweep/block/
repeated-hit events whose premiums sit at the anchor-table scale, giving
differentiated, calibrated scores. The original "DATA_GAP on most tickers + flat
50" was a labeling bug: a successful-but-EMPTY feed (a quiet name with no
significant flow) was collapsed to None and mislabeled DATA_GAP. An empty feed
is now a genuine neutral (50, OPTIONS_ONLY), and DATA_GAP is reserved for a true
fetch failure. The raw per-trade tape (source 3) is undersampled per call and
not anchor-calibrated, so it is only a fallback when the alerts feed errors.

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
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

import httpx

from atlas.schemas.options_flow import OptionsFlowResponse
from atlas.services.provider_response_cache import cached_call

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

# UW per-page size. 5 sessions x ~200 prints/day ~= 1000 prints for very liquid
# names; both dark-pool and flow-alert fetches paginate backward via the
# `older_than` cursor until 5 distinct session days are covered, so a busy
# mega-cap is no longer truncated at a single batch.
_UW_FETCH_LIMIT: Final[int] = 500
# Max dark-pool pages per call. The UW tape returns ~1 session per 500-print
# batch, so covering the 5-session window needs ~5 pages for normal names and
# up to ~7 for heavily-traded large-caps (e.g. VRT, which sits in the linear
# score range where full coverage actually changes the score). 8 gives margin;
# ultra-liquid mega-caps (NVDA/MU) still cap out but their net flow saturates
# the tier anchor anyway and the partial coverage is surfaced (dark_pool_truncated).
# Pagination stops early as soon as 5 distinct sessions are collected.
_UW_DARK_POOL_MAX_PAGES: Final[int] = 8

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

    Paginates backward via the ``older_than`` cursor (the oldest record's
    ``executed_at``) until 5 distinct session days are covered or
    _UW_DARK_POOL_MAX_PAGES pages are exhausted — so the busiest large-caps are
    no longer truncated at a single 500-print batch.

    Returns None when the first API call fails with nothing collected (caller
    treats None as "dark-pool data unavailable"); returns whatever was gathered
    on a partial/later-page error.
    """
    all_prints: list[dict[str, Any]] = []
    params: dict[str, Any] = {"limit": _UW_FETCH_LIMIT}

    for _ in range(_UW_DARK_POOL_MAX_PAGES):
        try:
            resp = await client.get(
                f"{_UW_BASE_URL}/api/darkpool/{ticker}",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload: Any = resp.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return all_prints if all_prints else None

        raw: list[Any]
        if isinstance(payload, list):
            raw = payload
        elif isinstance(payload, dict):
            data = payload.get("data", payload.get("darkpool", []))
            raw = data if isinstance(data, list) else []
        else:
            raw = []
        if not raw:
            break

        all_prints.extend(
            rec for rec in raw if isinstance(rec, dict) and not rec.get("canceled")
        )

        # Stop once the collected prints span at least 5 distinct session days.
        distinct_days = {
            str(r.get("executed_at", ""))[:10] for r in all_prints if r.get("executed_at")
        }
        if len(distinct_days) >= _F4_LOOKBACK_SESSIONS:
            break

        # Paginate: request prints older than the oldest record in this batch.
        last = raw[-1]
        oldest_ts = last.get("executed_at") if isinstance(last, dict) else None
        if not oldest_ts:
            break
        params = {"limit": _UW_FETCH_LIMIT, "older_than": oldest_ts}

    return all_prints if all_prints else None


async def _fetch_dark_pool_prints_cached(
    client: httpx.AsyncClient, ticker: str, headers: dict[str, str]
) -> list[dict[str, Any]] | None:
    """Cached, single-flight dark-pool fetch shared by F4 and the Washout Overlay.

    One paginated tape fetch per ticker serves both endpoints on a page load
    (and collapses concurrent requests). None/empty results are not cached, so a
    transient failure retries on the next call.
    """
    result: list[dict[str, Any]] | None = await cached_call(
        cache_key=f"uw:darkpool:{ticker.upper()}",
        factory=lambda: _fetch_dark_pool_prints(client, ticker, headers),
        cache_if=lambda r: bool(r),
    )
    return result


# ---------------------------------------------------------------------------
# Network I/O — UW flow alerts (replaces the old flow-recent endpoint)
# ---------------------------------------------------------------------------

# Maximum pages to fetch per call. 4 pages x 200 = 800 alerts - enough to
# cover 5 sessions of even the most active large-cap names.
_UW_FLOW_ALERTS_MAX_PAGES: Final[int] = 4


# ---------------------------------------------------------------------------
# Network I/O — UW fuller per-ticker options tape (primary F4 source)
# ---------------------------------------------------------------------------
#
# The flow-ALERTS feed below only fires on UW-flagged *unusual* activity, so a
# normal liquid name on a quiet week returns zero alerts → the old code mapped
# that to a DATA_GAP and a flat 50.  This tape is the broad per-ticker options
# feed: every name with any options flow produces a real net-flow reading, so
# quiet names get a genuine (often still ~50, but *earned*) score rather than a
# false gap.  The alerts feed is kept only as a fallback when this tape errors.
#
# NOTE: endpoint/field shapes vary by UW plan. The fetch is intentionally
# tolerant (multiple batch keys; timestamp/side/premium normalization) and the
# path is a single constant so it can be swapped against a live sample. If this
# tape hard-errors the service degrades gracefully to the flow-alerts fallback.
_UW_OPTION_TAPE_PATH_TMPL: Final[str] = _UW_BASE_URL + "/api/stock/{ticker}/flow-recent"
_UW_OPTION_TAPE_MAX_PAGES: Final[int] = 6
_UW_OPTION_TAPE_LIMIT: Final[int] = 200
# OCC option symbol: TICKER + YYMMDD + [C|P] + 8-digit strike. The C/P letter
# immediately precedes the trailing 8-digit strike — used to read call/put off
# UW flow-recent records, which omit an explicit `type` field.
_OCC_TYPE_RE: Final[re.Pattern[str]] = re.compile(r"([CP])\d{8}$")
# Options contract multiplier — used only when a record lacks an explicit
# `premium` dollar figure and we must reconstruct it from price * size.
_OPTION_CONTRACT_MULTIPLIER: Final[float] = 100.0


def _extract_tape_batch(payload: Any) -> list[Any]:
    """Pull the record list out of a tape payload across known UW shapes."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "flow", "trades", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _normalize_tape_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Normalize a UW ``flow-recent`` per-trade record for the aggregator.

    The flow-recent tape does NOT carry explicit ``type``/``side`` fields. It
    encodes them as:
      - call/put → the ``[CP]`` letter in the OCC symbol (``option_chain_id`` /
        ``option_chain``), e.g. ``NVDA260617P00202500`` → put;
      - buy/sell side → the ``tags`` list (``"ask_side"`` / ``"bid_side"``),
        with an NBBO-vs-price fallback when tags are absent.

    Populates ``option_type``, ``side``, ``executed_at`` and (if missing) a
    dollar ``premium`` so ``_classify_options_print`` / ``_aggregate_options``
    can read it. Mutates and returns the record (fresh from JSON decoding).
    """
    ts = rec.get("executed_at") or rec.get("created_at") or rec.get("tape_time")
    if isinstance(ts, str):
        rec["executed_at"] = ts

    # option_type (call/put) — explicit field, else the OCC chain symbol's C/P.
    if not (rec.get("option_type") or rec.get("type")):
        chain = (
            rec.get("option_chain")
            or rec.get("option_chain_id")
            or rec.get("option_symbol")
        )
        if isinstance(chain, str):
            m = _OCC_TYPE_RE.search(chain)
            if m:
                rec["option_type"] = "call" if m.group(1) == "C" else "put"

    # side (ASK/BID) — explicit field, else UW tags, else NBBO-vs-price.
    if not rec.get("side"):
        tags = rec.get("tags")
        if isinstance(tags, (list, tuple)):
            tagset = {str(t).lower() for t in tags}
            if "ask_side" in tagset:
                rec["side"] = _UW_SIDE_ASK
            elif "bid_side" in tagset:
                rec["side"] = _UW_SIDE_BID
    if not rec.get("side"):
        price = _safe_float(rec.get("price"))
        ask_raw = rec.get("nbbo_ask") if rec.get("nbbo_ask") is not None else rec.get("ask")
        bid_raw = rec.get("nbbo_bid") if rec.get("nbbo_bid") is not None else rec.get("bid")
        ask = _safe_float(ask_raw)
        bid = _safe_float(bid_raw)
        if price is not None and ask is not None and bid is not None:
            if price >= ask * _F4_AT_OR_ABOVE_ASK_FACTOR:
                rec["side"] = _UW_SIDE_ASK
            elif price <= bid * _F4_AT_OR_BELOW_BID_FACTOR:
                rec["side"] = _UW_SIDE_BID

    if _safe_float(rec.get("premium")) is None:
        size = _safe_float(rec.get("size"))
        price = _safe_float(rec.get("price"))
        if size is not None and price is not None:
            rec["premium"] = size * price * _OPTION_CONTRACT_MULTIPLIER

    return rec


async def _fetch_option_trades_tape(
    client: httpx.AsyncClient, ticker: str, headers: dict[str, str]
) -> list[dict[str, Any]] | None:
    """Fetch the fuller per-ticker options trade tape from Unusual Whales.

    Paginates backward via the ``older_than`` cursor until 5 distinct session
    days are covered or _UW_OPTION_TAPE_MAX_PAGES pages are exhausted.

    Returns:
      - a list of normalized per-trade records (possibly **empty**) on any
        successful HTTP response — an empty list means "no options flow / no
        edge", which is a genuine neutral reading, NOT a data gap;
      - ``None`` only on a hard transport/HTTP error before any successful page,
        so the caller can fall back to the flow-alerts feed.
    """
    all_trades: list[dict[str, Any]] = []
    params: dict[str, Any] = {"limit": _UW_OPTION_TAPE_LIMIT}
    saw_response = False
    url = _UW_OPTION_TAPE_PATH_TMPL.format(ticker=ticker)

    for _ in range(_UW_OPTION_TAPE_MAX_PAGES):
        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload: Any = resp.json()
        except (httpx.HTTPError, ValueError, TypeError):
            # Hard error: None only if we never saw a good page (true gap).
            return all_trades if saw_response else None

        saw_response = True
        batch = _extract_tape_batch(payload)
        if not batch:
            break

        all_trades.extend(
            _normalize_tape_record(rec) for rec in batch if isinstance(rec, dict)
        )

        distinct_days = {
            str(r.get("executed_at", ""))[:10] for r in all_trades if r.get("executed_at")
        }
        if len(distinct_days) >= _F4_LOOKBACK_SESSIONS:
            break

        last = batch[-1] if isinstance(batch[-1], dict) else {}
        oldest_ts = last.get("executed_at") or last.get("created_at")
        if not oldest_ts:
            break
        params = {"limit": _UW_OPTION_TAPE_LIMIT, "older_than": oldest_ts}

    return all_trades  # may be [] on a successful-but-empty fetch (real neutral)


async def _fetch_option_trades_tape_cached(
    client: httpx.AsyncClient, ticker: str, headers: dict[str, str]
) -> list[dict[str, Any]] | None:
    """Cached, single-flight options-tape fetch (one fetch per ticker per load).

    Caches successful results *including the empty list* (a real "no flow"
    reading) so quiet names don't re-hit the API; only hard errors (None) are
    left uncached so they retry.
    """
    result: list[dict[str, Any]] | None = await cached_call(
        cache_key=f"uw:opttape:{ticker.upper()}",
        factory=lambda: _fetch_option_trades_tape(client, ticker, headers),
        cache_if=lambda r: r is not None,
    )
    return result


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

    Returns:
      - a list of alert records (possibly **empty**) on any successful HTTP
        response — an empty list means "no significant options flow this week",
        a genuine neutral reading, NOT a data gap;
      - ``None`` only on a hard transport/HTTP error before any successful page.
    """
    all_alerts: list[dict[str, Any]] = []
    params: dict[str, Any] = {"ticker_symbol": ticker, "limit": 200}
    saw_response = False

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
            # Hard error: None only if we never saw a good page (true gap).
            return all_alerts if saw_response else None

        saw_response = True
        if not isinstance(payload, dict):
            break
        batch: list[Any] = payload.get("data", [])
        if not isinstance(batch, list) or not batch:
            break

        all_alerts.extend(r for r in batch if isinstance(r, dict))

        # Stop once we have data from at least _F4_LOOKBACK_SESSIONS distinct days.
        distinct_days = {r.get("created_at", "")[:10] for r in all_alerts if r.get("created_at")}
        if len(distinct_days) >= _F4_LOOKBACK_SESSIONS:
            break

        # Paginate: request alerts older than the last record in this batch.
        oldest_ts = batch[-1].get("created_at") if batch else None
        if not oldest_ts:
            break
        params = {"ticker_symbol": ticker, "limit": 200, "older_than": oldest_ts}

    return all_alerts  # may be [] on a successful-but-empty fetch (real neutral)


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

        net = sum(call total_ask_side_prem) - sum(put total_ask_side_prem)

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

    net_flow = _apply_strategy_aware_adjustment(alerts, net_flow)

    return net_flow, (largest_bull if largest_bull > 0 else None)


# ---------------------------------------------------------------------------
# Layer 1 — F4 score: options-only, time-decayed ("fading memory")
# ---------------------------------------------------------------------------
#
# F4 is the slow 5-session OPTIONS-flow score (the "resume"). Each session is
# weighted so today counts most and four days ago counts least, so fresh
# conviction moves it within a day while one odd day can't whipsaw it. Weights
# are scaled to sum to the session count, preserving the existing options anchor
# calibration (a flat-weighted 5-session sum and this decay sum share scale).
# Dark-pool/stock-tape data does NOT enter this score — it drives the chips
# (Layer 2) instead.
_F4_DECAY_PCT: Final[tuple[int, ...]] = (40, 25, 15, 10, 10)  # today -> 4 days ago


def _group_by_session(
    records: list[dict[str, Any]], timestamp_key: str
) -> list[list[dict[str, Any]]]:
    """Bucket records into session-day groups, newest day first."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        ts = rec.get(timestamp_key)
        if isinstance(ts, str) and len(ts) >= 10:
            groups[ts[:10]].append(rec)
    return [groups[day] for day in sorted(groups, reverse=True)]


def _options_net_raw(alerts: list[dict[str, Any]]) -> tuple[float, float | None]:
    """Raw options net flow for one session: sum(call ask) - sum(put ask)."""
    net = 0.0
    largest = 0.0
    for rec in alerts:
        opt_type = str(rec.get("type", "")).lower()
        ask = _safe_float(rec.get("total_ask_side_prem")) or 0.0
        total = _safe_float(rec.get("total_premium")) or 0.0
        if opt_type == "call":
            net += ask
            largest = max(largest, total)
        elif opt_type == "put":
            net -= ask
    return net, (largest if largest > 0 else None)


def _decay_weighted_options(
    windowed_opts: list[dict[str, Any]],
) -> tuple[float, float | None]:
    """Time-decay-weighted options net flow over the 5-session window.

    Returns (weighted_net_flow_usd, largest_single_alert_premium_usd).
    """
    sessions = _group_by_session(windowed_opts, "created_at")[:_F4_LOOKBACK_SESSIONS]
    if not sessions:
        return 0.0, None
    daily = [_options_net_raw(day) for day in sessions]  # newest first
    nets = [d[0] for d in daily]
    largest = max((d[1] for d in daily if d[1] is not None), default=None)
    n = len(nets)
    weights = _F4_DECAY_PCT[:n]
    total_w = sum(weights)
    weighted = sum(net * (w / total_w * n) for net, w in zip(nets, weights, strict=True))
    return weighted, largest


def _decay_weighted_tape(
    windowed_trades: list[dict[str, Any]],
) -> tuple[float, float | None]:
    """Time-decay-weighted net flow over the per-trade options tape.

    Same fading-memory weighting as the alerts path, but aggregates the fuller
    per-trade tape via the per-trade classifier (``_aggregate_options``): each
    session's net = sum(new-bull + put-sell premiums) - sum(new-bear premiums),
    with profit-taking and spread crosses stripped. Newest session weighted most.

    Returns (weighted_net_flow_usd, largest_single_bullish_premium_usd).
    """
    sessions = _group_by_session(windowed_trades, "executed_at")[:_F4_LOOKBACK_SESSIONS]
    if not sessions:
        return 0.0, None
    daily = [_aggregate_options(day) for day in sessions]  # newest first
    nets = [d[0] for d in daily]
    largest = max((d[1] for d in daily if d[1] is not None), default=None)
    n = len(nets)
    weights = _F4_DECAY_PCT[:n]
    total_w = sum(weights)
    weighted = sum(net * (w / total_w * n) for net, w in zip(nets, weights, strict=True))
    return weighted, largest


# ---------------------------------------------------------------------------
# Layer 2 — stock tape: per-session state ("chips"), not a score
# ---------------------------------------------------------------------------

_DP_FRESH: Final[str] = "FRESH_ACCUMULATION"
_DP_PERSISTENT: Final[str] = "PERSISTENT_ACCUMULATION"
_DP_NEUTRAL: Final[str] = "NEUTRAL_MIXED"
_DP_FADING: Final[str] = "FADING"
_DP_DISTRIBUTION: Final[str] = "ACTIVE_DISTRIBUTION"
_DP_UNKNOWN: Final[str] = "UNKNOWN"


def _dark_pool_daily_nets(windowed_dp: list[dict[str, Any]]) -> list[float]:
    """Per-session dark-pool net flow (BUY $ - SELL $), newest session first."""
    sessions = _group_by_session(windowed_dp, "executed_at")[:_F4_LOOKBACK_SESSIONS]
    return [_aggregate_dark_pool(day)[0] for day in sessions]


def classify_dark_pool_state(daily_nets_newest_first: list[float]) -> tuple[str, str]:
    """Classify the stock-tape trajectory into one of the five chips.

    Input is per-session net dark-pool flow, newest session first. Pure.
    """
    d = daily_nets_newest_first
    n = len(d)
    if n == 0:
        return _DP_UNKNOWN, "No dark-pool prints in the window."
    total = sum(d)
    buys = sum(1 for x in d if x > 0)

    # Active Distribution: 2+ recent sessions of net selling, window selling-led.
    if n >= 2 and d[0] < 0 and d[1] < 0 and total < 0:
        return _DP_DISTRIBUTION, "Net selling across recent sessions — institutions distributing."
    # Fading: earlier accumulation, now flipping to fresh selling.
    if d[0] < 0 and sum(d[1:]) > 0:
        return _DP_FADING, "Earlier accumulation fading into fresh selling."
    # Persistent Accumulation: net buying sustained across (almost) the whole week.
    if n >= 4 and buys >= 4 and total > 0:
        return _DP_PERSISTENT, "Net buying sustained across the week — conviction-grade."
    # Fresh Accumulation: buying started in the last 1-2 sessions and accelerating.
    if n >= 2 and d[0] > 0 and d[1] > 0 and d[0] >= d[1] and sum(d[2:]) <= 0:
        return _DP_FRESH, "Buying started in the last 1-2 sessions and accelerating."
    return _DP_NEUTRAL, "No clear edge in the stock tape."


# ---------------------------------------------------------------------------
# Layer 3 — clearance: the entry decision (resume x this-week behaviour)
# ---------------------------------------------------------------------------

_CLEARANCE_CLEARED: Final[str] = "CLEARED"
_CLEARANCE_WATCH: Final[str] = "WATCH"
_CLEARANCE_REVOKED: Final[str] = "REVOKED"
_CLEARANCE_F4_MIN: Final[int] = 60  # options flow must be at least BUY-grade to clear
_CLEARANCE_F4_WEAK: Final[int] = 40


def clearance_state(chip: str, f4_score: int) -> tuple[str, str]:
    """Combine the F4 options score (resume) with the stock-tape chip (this week)
    into an entry decision. Pure function."""
    if chip == _DP_DISTRIBUTION:
        return _CLEARANCE_REVOKED, "Active distribution — institutions selling; adds blocked."
    if chip == _DP_FADING:
        return _CLEARANCE_WATCH, "Accumulation fading — no fresh adds; wait for a reset."
    if chip in (_DP_FRESH, _DP_PERSISTENT) and f4_score >= _CLEARANCE_F4_MIN:
        return _CLEARANCE_CLEARED, "Accumulation confirmed and options flow supportive."
    if f4_score < _CLEARANCE_F4_WEAK:
        return _CLEARANCE_WATCH, "Options flow weak/bearish — no fresh adds."
    return _CLEARANCE_WATCH, "No clear edge — hold; no fresh adds."


def _alert_dte_days(rec: dict[str, Any]) -> int | None:
    """Return DTE from alert expiry-like fields when parseable."""
    expiry = rec.get("expiry") or rec.get("expiration") or rec.get("expiry_date")
    if not isinstance(expiry, str):
        return None
    try:
        exp_date = datetime.fromisoformat(expiry.replace("Z", "+00:00")).date()
    except ValueError:
        return None
    return (exp_date - datetime.now(UTC).date()).days


def _apply_strategy_aware_adjustment(alerts: list[dict[str, Any]], raw_net_flow: float) -> float:
    """Neutralize bearish net flow for complex bullish multi-leg structures.

    Relief is applied only when all are present:
    - protective put-spread participation,
    - near-dated covered-call overwriting,
    - long-dated LEAP call accumulation.

    Adjustment cannot flip bullish; cap at neutral (0).
    """
    if raw_net_flow >= 0:
        return raw_net_flow

    put_legs = 0
    put_ask_total = 0.0
    put_bid_total = 0.0
    overwrite_bid_total = 0.0
    leap_call_ask_total = 0.0

    for rec in alerts:
        opt_type = str(rec.get("type", "")).lower()
        ask_prem = _safe_float(rec.get("total_ask_side_prem")) or 0.0
        bid_prem = _safe_float(rec.get("total_bid_side_prem")) or 0.0
        dte = _alert_dte_days(rec)

        if opt_type == "put":
            if ask_prem > 0 and bid_prem > 0:
                put_legs += 1
            put_ask_total += ask_prem
            put_bid_total += bid_prem
            continue

        if opt_type != "call":
            continue

        if (
            dte is not None
            and dte <= _F4_STRAT_NEAR_DTE_MAX_DAYS
            and bid_prem >= ask_prem * _F4_STRAT_OVERWRITE_BID_DOMINANCE
            and bid_prem > 0
        ):
            overwrite_bid_total += bid_prem

        if (
            dte is not None
            and dte >= _F4_STRAT_LEAP_DTE_MIN_DAYS
            and ask_prem > bid_prem
            and ask_prem > 0
        ):
            leap_call_ask_total += ask_prem

    has_protective_put_spread = (
        put_legs >= _F4_STRAT_MIN_PUT_LEGS and put_ask_total > 0 and put_bid_total > 0
    )
    has_covered_call_overwrite = overwrite_bid_total > 0
    has_leap_call_accumulation = leap_call_ask_total > 0

    if not (
        has_protective_put_spread and has_covered_call_overwrite and has_leap_call_accumulation
    ):
        return raw_net_flow

    relief_capacity = (
        put_bid_total
        + leap_call_ask_total
        + overwrite_bid_total * _F4_STRAT_OVERWRITE_RELIEF_WEIGHT
    )
    relief = min(abs(raw_net_flow), relief_capacity)
    return min(0.0, raw_net_flow + relief)


def _dark_pool_settlement_ratio(prints: list[dict[str, Any]]) -> float | None:
    """Return settlement ratio over windowed dark-pool prints.

    Ratio = settlement_count / total_count using the same settlement classifier
    as F4 aggregation. Returns None when no valid prints are present.
    """
    total = 0
    settlements = 0
    for rec in prints:
        price = _safe_float(rec.get("price"))
        if price is None:
            continue
        prem = _print_premium_usd(rec)
        if prem <= 0:
            continue
        bid = _safe_float(rec.get("nbbo_bid"))
        ask = _safe_float(rec.get("nbbo_ask"))
        codes_raw = rec.get("sale_cond_codes") or ()
        codes: tuple[str, ...] = (
            tuple(c for c in codes_raw if isinstance(c, str))
            if isinstance(codes_raw, (list, tuple))
            else ()
        )
        total += 1
        if _classify_dark_pool_print(price, bid, ask, codes) == "SETTLEMENT":
            settlements += 1
    if total == 0:
        return None
    return settlements / total


def _apply_dark_pool_quality_boost(
    dp_score: int | None,
    dp_net_flow: float | None,
    dp_large_buys: int,
    dp_prints: list[dict[str, Any]],
    opt_net_flow: float | None,
) -> int | None:
    """Boost dark-pool score for clean, large-block accumulation sessions."""
    if dp_score is None or dp_net_flow is None or dp_net_flow <= 0:
        return dp_score
    if dp_large_buys < _F4_DP_QUALITY_MIN_LARGE_BUYS:
        return dp_score
    if dp_net_flow < _F4_DP_QUALITY_MIN_NET_FLOW_USD:
        return dp_score
    if opt_net_flow is not None and abs(opt_net_flow) > _F4_DP_QUALITY_MAX_OPTIONS_ABS_USD:
        return dp_score

    settlement_ratio = _dark_pool_settlement_ratio(dp_prints)
    if settlement_ratio is None or settlement_ratio > _F4_DP_QUALITY_SETTLEMENT_MAX:
        return dp_score

    return min(100, dp_score + _F4_DP_QUALITY_BOOST_POINTS)


def _detect_covered_call_posture(alerts: list[dict[str, Any]]) -> bool:
    """Return True when the options flow exhibits a covered-call management posture.

    The pattern requires all three legs:
    1. Protective put spread — at least 2 put legs each with both ask and bid
       side premium (indicating a debit spread, not a naked put write).
    2. Near-dated covered-call overwriting — a call leg whose bid premium
       exceeds its ask premium by at least ``_F4_STRAT_OVERWRITE_BID_DOMINANCE``
       and DTE ≤ ``_F4_STRAT_NEAR_DTE_MAX_DAYS``.
    3. Long-dated LEAP accumulation — a call leg with DTE ≥
       ``_F4_STRAT_LEAP_DTE_MIN_DAYS`` where ask dominates bid (paid up for
       long-dated optionality).

    Pure function — no I/O, no side effects. Used by ``_build_response_v2``
    to populate ``OptionsFlowResponse.options_strategy_type``.
    """
    put_legs_with_both_sides = 0
    put_ask_total = 0.0
    put_bid_total = 0.0
    has_overwrite = False
    has_leap = False

    for rec in alerts:
        opt_type = str(rec.get("type", "")).lower()
        ask_prem = _safe_float(rec.get("total_ask_side_prem")) or 0.0
        bid_prem = _safe_float(rec.get("total_bid_side_prem")) or 0.0
        dte = _alert_dte_days(rec)

        if opt_type == "put":
            if ask_prem > 0 and bid_prem > 0:
                put_legs_with_both_sides += 1
            put_ask_total += ask_prem
            put_bid_total += bid_prem
            continue

        if opt_type != "call":
            continue

        if (
            dte is not None
            and dte <= _F4_STRAT_NEAR_DTE_MAX_DAYS
            and bid_prem >= ask_prem * _F4_STRAT_OVERWRITE_BID_DOMINANCE
            and bid_prem > 0
        ):
            has_overwrite = True

        if (
            dte is not None
            and dte >= _F4_STRAT_LEAP_DTE_MIN_DAYS
            and ask_prem > bid_prem
            and ask_prem > 0
        ):
            has_leap = True

    has_protective_put_spread = (
        put_legs_with_both_sides >= _F4_STRAT_MIN_PUT_LEGS
        and put_ask_total > 0
        and put_bid_total > 0
    )
    return has_protective_put_spread and has_overwrite and has_leap


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
        dark_pool_settlement_ratio=None,
        options_strategy_type=None,
    )


def _build_response_v2(
    *,
    ticker: str,
    market_cap: float | None,
    dp_prints: list[dict[str, Any]] | None,
    opt_trades: list[dict[str, Any]] | None = None,
    opt_tape: list[dict[str, Any]] | None = None,
) -> OptionsFlowResponse:
    """Build the F4 v2 response from raw fetched data.

    Options-score source priority (F4 is options-only):
      1. ``opt_trades`` — the flow-alerts feed (PRIMARY). These are aggregated
         sweep/block/repeated-hit events whose premiums sit at the anchor-table
         scale, so they give differentiated, calibrated scores. A non-None value
         *including an empty list* is a real reading: empty = no significant flow
         = a genuine neutral 50, NOT a data gap.
      2. ``opt_tape`` — the raw per-trade tape (fallback only, when alerts
         hard-error). It is undersampled per call and not anchor-calibrated, so
         it is a last resort rather than the primary signal.
      3. Neither available (both None) → DATA_GAP, score withheld at 50.

    ``None`` for ``dp_prints`` signals "dark-pool unavailable" and nullifies the
    (informational-only) dark-pool sub-score and chips.
    """
    tier = _pick_tier(market_cap)

    # Dark-pool branch ----------------------------------------------------
    dp_score: int | None
    dp_net_flow: float | None
    dp_count = 0
    dp_large_buys = 0
    largest_dp_buy: float | None = None
    windowed_dp: list[dict[str, Any]] = []
    dp_sessions_covered: int | None = None
    dp_truncated = False
    if dp_prints is None:
        dp_score = None
        dp_net_flow = None
    else:
        windowed_dp = _filter_to_recent_sessions(dp_prints)
        dp_net_flow, dp_count, dp_large_buys, largest_dp_buy = _aggregate_dark_pool(windowed_dp)
        dp_score = _map_net_flow_to_score(dp_net_flow, tier)
        dp_sessions_covered = len(
            {str(p.get("executed_at", ""))[:10] for p in windowed_dp if p.get("executed_at")}
        )
        # Truncation = we pulled the full page-cap of prints yet still span fewer
        # than the lookback window (a very high-volume name). Surfaced, never silent.
        dp_truncated = (
            len(dp_prints) >= _UW_DARK_POOL_MAX_PAGES * _UW_FETCH_LIMIT
            and dp_sessions_covered < _F4_LOOKBACK_SESSIONS
        )

    # Options branch (Layer 1 — the F4 score, options-only + fading memory) -----
    # Primary source is the flow-alerts feed (calibrated to the anchor scale);
    # the raw per-trade tape is a fallback only. An empty primary feed
    # (opt_trades == []) is a REAL neutral reading, not a gap — only "no source
    # at all" (both None) is a DATA_GAP.
    opt_score: int | None
    opt_net_flow: float | None
    largest_opt_buy: float | None = None
    opt_window_empty = False
    if opt_trades is not None:
        windowed_opts = _filter_to_recent_sessions(opt_trades, timestamp_key="created_at")
        opt_window_empty = not windowed_opts
        opt_net_flow, largest_opt_buy = _decay_weighted_options(windowed_opts)
        # Protective-structure relief (covered-call / put-spread) still applies to
        # the weighted net — this is legitimate net-flow handling, distinct from
        # the removed (broken) covered-call display tag.
        opt_net_flow = _apply_strategy_aware_adjustment(windowed_opts, opt_net_flow)
        opt_score = _map_net_flow_to_score(opt_net_flow, tier)
    elif opt_tape is not None:
        windowed_tape = _filter_to_recent_sessions(opt_tape, timestamp_key="executed_at")
        opt_window_empty = not windowed_tape
        opt_net_flow, largest_opt_buy = _decay_weighted_tape(windowed_tape)
        opt_score = _map_net_flow_to_score(opt_net_flow, tier)
    else:
        opt_score = None
        opt_net_flow = None

    # F4 is now OPTIONS-ONLY. Dark-pool no longer enters the 0-100 (it drives the
    # chips/clearance below). data_source reflects the score's single source.
    if opt_score is None:
        f4_raw, source = _F4_NEUTRAL_SCORE, _F4_SOURCE_DATA_GAP
    else:
        f4_raw, source = opt_score, _F4_SOURCE_OPT_ONLY
    direction = _derive_flow_direction(None, opt_net_flow)

    # Layer 2 — stock-tape state ("chips") from per-session dark-pool flow.
    dp_daily = _dark_pool_daily_nets(windowed_dp) if windowed_dp else []
    dp_state, dp_state_reason = classify_dark_pool_state(dp_daily)

    # Layer 3 — clearance: resume (F4) x this-week behaviour (chip).
    clr_state, clr_reason = clearance_state(dp_state, f4_raw)

    gap_reason: str | None = None
    if source == _F4_SOURCE_DATA_GAP:
        gap_reason = "Options flow unavailable — F4 score withheld (DATA_GAP)."
    elif opt_window_empty:
        # Real reading, not a gap: the tape was fetched but no options flow
        # landed in the 5-session window → genuinely neutral.
        gap_reason = "No options flow in the 5-session window — neutral (not a data gap)."
    if dp_truncated:
        note = (
            f"Dark-pool covers {dp_sessions_covered} of {_F4_LOOKBACK_SESSIONS} sessions "
            "(high-volume truncation); the chip understates the full window."
        )
        gap_reason = f"{gap_reason} {note}" if gap_reason else note

    # Settlement ratio — computed from the same windowed set used for the chips.
    dp_settlement_ratio: float | None = (
        _dark_pool_settlement_ratio(windowed_dp) if windowed_dp else None
    )

    # NOTE: dark_pool_score is retained for transparency only — it is NOT blended
    # into f4_score. The broken covered-call "sentiment tag" has been removed.
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
        dark_pool_sessions_covered=dp_sessions_covered,
        dark_pool_truncated=dp_truncated,
        dark_pool_large_buy_count=dp_large_buys,
        largest_dark_pool_buy_usd=largest_dp_buy,
        largest_options_buy_usd=largest_opt_buy,
        dark_pool_settlement_ratio=dp_settlement_ratio,
        options_strategy_type=None,
        dark_pool_state=dp_state,
        dark_pool_state_reason=dp_state_reason,
        clearance=clr_state,
        clearance_reason=clr_reason,
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
                logger.debug(
                    "[F4] %s served from cache (age=%s)", ticker, datetime.now(UTC) - cached_at
                )
                return cached_response

        # Step 2: three concurrent fetches — market cap, dark-pool tape, and the
        # OPTIONS FLOW-ALERTS feed (the F4 score's primary, anchor-calibrated
        # source). An empty alerts list ([]) is a real "no significant flow"
        # reading, not an error.
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            market_cap, dp_prints, opt_alerts = await asyncio.gather(
                _fetch_market_cap(client, ticker, self._polygon_api_key),
                _fetch_dark_pool_prints_cached(client, ticker, self._uw_headers),
                _fetch_option_flow_alerts(client, ticker, self._uw_headers),
            )

        # Retry whichever UW call HARD-errored (None). An empty list ([]) is a
        # real reading, not an error, so it is never retried.
        if dp_prints is None or opt_alerts is None:
            await asyncio.sleep(1.0)
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if dp_prints is None:
                    dp_prints = await _fetch_dark_pool_prints_cached(
                        client, ticker, self._uw_headers
                    )
                if opt_alerts is None:
                    opt_alerts = await _fetch_option_flow_alerts(
                        client, ticker, self._uw_headers
                    )

        # Fallback: only when the alerts feed hard-errored do we reach for the
        # raw per-trade tape (undersampled/uncalibrated) so a transient alerts
        # outage degrades to a coarse reading instead of a flat DATA_GAP.
        opt_tape: list[dict[str, Any]] | None = None
        if opt_alerts is None:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                opt_tape = await _fetch_option_trades_tape_cached(
                    client, ticker, self._uw_headers
                )

        # Step 3: aggregate + score + build response.
        result = _build_response_v2(
            ticker=ticker,
            market_cap=market_cap,
            dp_prints=dp_prints,
            opt_trades=opt_alerts,
            opt_tape=opt_tape,
        )

        # Cache only real data (not data-gap fallbacks) to avoid caching stale 50s.
        if dp_prints is not None or opt_alerts is not None or opt_tape is not None:
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
MarketCapTier = Literal["MEGA", "LARGE", "MID", "SMALL"]

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

# Market-cap tier thresholds (USD). MEGA > $500B; LARGE $50B-$500B;
# MID $5B-$50B; SMALL < $5B. MEGA was split out of LARGE because a single
# $50B-$5T band is too wide: flow that is meaningful for a $74B name (e.g. LITE)
# is noise for a $5T name (NVDA). MEGA keeps the old wide LARGE band; LARGE is
# tightened so $50-500B names move off the neutral plateau on real flow.
_F4_MEGA_CAP_FLOOR: Final[float] = 500_000_000_000.0
_F4_LARGE_CAP_FLOOR: Final[float] = 50_000_000_000.0
_F4_MID_CAP_FLOOR: Final[float] = 5_000_000_000.0

# Net-flow anchor tables — (net_flow_usd_anchor, score_anchor) ordered
# monotonically increasing in net_flow. Linear interpolation between adjacent
# anchors; flat extrapolation outside the endpoints (clamped to [0, 100]).
# Inside the ±neutral band both anchors map to score 50 → flat neutral plateau.
# MEGA (>$500B): the original wide LARGE calibration — mega-cap flow is huge.
_F4_DP_ANCHORS_MEGA: Final[tuple[tuple[float, int], ...]] = (
    (-100_000_000.0, 0),
    (-25_000_000.0, 25),
    (-5_000_000.0, 50),
    (5_000_000.0, 50),
    (25_000_000.0, 75),
    (100_000_000.0, 100),
)
# LARGE ($50B-$500B): tightened — ±$2M neutral band, knees at $10M/$30M, so a
# few-million-dollar net imbalance on a $50-200B name registers a real reading.
_F4_DP_ANCHORS_LARGE: Final[tuple[tuple[float, int], ...]] = (
    (-30_000_000.0, 0),
    (-10_000_000.0, 25),
    (-2_000_000.0, 50),
    (2_000_000.0, 50),
    (10_000_000.0, 75),
    (30_000_000.0, 100),
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

# Strategy-aware options adjustment constants.
_F4_STRAT_LEAP_DTE_MIN_DAYS: Final[int] = 180
_F4_STRAT_NEAR_DTE_MAX_DAYS: Final[int] = 400
_F4_STRAT_OVERWRITE_BID_DOMINANCE: Final[float] = 1.2
_F4_STRAT_OVERWRITE_RELIEF_WEIGHT: Final[float] = 0.5
_F4_STRAT_MIN_PUT_LEGS: Final[int] = 2

# Dark-pool quality boost constants.
_F4_DP_QUALITY_SETTLEMENT_MAX: Final[float] = 0.20
_F4_DP_QUALITY_MIN_LARGE_BUYS: Final[int] = 3
_F4_DP_QUALITY_MIN_NET_FLOW_USD: Final[float] = 10_000_000.0
_F4_DP_QUALITY_MAX_OPTIONS_ABS_USD: Final[float] = 5_000_000.0
_F4_DP_QUALITY_BOOST_POINTS: Final[int] = 10

# Weighted DP/options blend constants.
# Applied when dark_pool_score ≥ _F4_DP_DOMINANT_SCORE_MIN AND options_flow_score
# falls inside the neutral band [_F4_OPT_NEUTRAL_LOW, _F4_OPT_NEUTRAL_HIGH].
# Rationale: a neutral options score does NOT indicate bearish conviction — it
# often reflects a covered-call management posture (overwriting + LEAP
# accumulation) where the net premium flows cancel.  Letting a truly neutral
# options score drag a 100-point DP reading down 25 pts misrepresents signal
# quality.  The 65/35 weighting reflects that DP block activity from a single
# counterparty is a higher-conviction institutional signal than mixed options flow.
_F4_DP_DOMINANT_SCORE_MIN: Final[int] = 80
_F4_OPT_NEUTRAL_BAND_LOW: Final[int] = 45
_F4_OPT_NEUTRAL_BAND_HIGH: Final[int] = 55
_F4_DP_DOMINANT_WEIGHT: Final[float] = 0.65
_F4_OPT_DOMINANT_WEIGHT: Final[float] = 0.35

# Options strategy type labels.
_F4_STRATEGY_COVERED_CALL_POSTURE: Final[str] = "COVERED_CALL_POSTURE"

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
    """Map market cap → MEGA | LARGE | MID | SMALL.

    MEGA: > $500B ; LARGE: $50B-$500B ; MID: $5B-$50B (inclusive at $5B) ;
    SMALL: < $5B or unknown. Unknown market cap (None) defaults to SMALL (most
    conservative anchors).
    """
    if market_cap_usd is None:
        return "SMALL"
    if market_cap_usd > _F4_MEGA_CAP_FLOOR:
        return "MEGA"
    if market_cap_usd > _F4_LARGE_CAP_FLOOR:
        return "LARGE"
    if market_cap_usd >= _F4_MID_CAP_FLOOR:
        return "MID"
    return "SMALL"


def _anchors_for_tier(tier: MarketCapTier) -> tuple[tuple[float, int], ...]:
    """Return the anchor table for a tier."""
    if tier == "MEGA":
        return _F4_DP_ANCHORS_MEGA
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
    """Combine dark-pool + options scores into a single F4_raw + source label.

    When both sources are available the default is a 50/50 average.  One
    exception applies: when the dark-pool score is strong (≥ 80) and the
    options score is genuinely neutral (45–55) the blend shifts to 65/35
    (DP / options).  A neutral options reading in that regime most often
    reflects a covered-call management posture rather than a lack of
    conviction, so giving it equal weight would systematically understate
    the institutional block-buying signal.
    """
    if dp_score is not None and opt_score is not None:
        if (
            dp_score >= _F4_DP_DOMINANT_SCORE_MIN
            and _F4_OPT_NEUTRAL_BAND_LOW <= opt_score <= _F4_OPT_NEUTRAL_BAND_HIGH
        ):
            blended = round(
                dp_score * _F4_DP_DOMINANT_WEIGHT + opt_score * _F4_OPT_DOMINANT_WEIGHT
            )
            return (blended, _F4_SOURCE_BOTH)
        return (round((dp_score + opt_score) / 2), _F4_SOURCE_BOTH)
    if dp_score is not None:
        return (dp_score, _F4_SOURCE_DP_ONLY)
    if opt_score is not None:
        return (opt_score, _F4_SOURCE_OPT_ONLY)
    return (_F4_NEUTRAL_SCORE, _F4_SOURCE_DATA_GAP)
