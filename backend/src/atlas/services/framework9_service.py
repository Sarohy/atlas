"""Framework 9 — Options Flow Signal Hierarchy service.

Produces the F4 Options Flow score (0-100) fed into Framework 1 at 15% weight.

Three data sources in priority order:
  1. Unusual Whales  — whale blocks, flow direction, put/call ratio
  2. Polygon.io      — dark pool prints, spread position, options volume
  3. Alpha Vantage   — options volume fallback, put/call backup

Signal tier hierarchy (checked in priority order, stop at first match):
  TIER_1_WHALE         — Single print > $10M confirmed by UW           (score 88-92)
  TIER_2_INSTITUTIONAL — Dark pool > $500K + spread > 0.6 + vol > 2%  (score 78-87)
  TIER_3_UNUSUAL       — Options volume > 2x 30d ADV + P/C reversal   (score 65-77)
  TIER_4_WEAK          — Volume elevated, below 2x ADV                 (score 50-64)
  TIER_5_NONE          — No qualifying signal                           (score 55)

Caching:
  Unusual Whales and dark pool data are cached in an in-memory dict with a
  15-minute TTL (900 s).  Stale threshold is 240 minutes.
  (Swap for Redis with the same TTL keys in production — see comments below.)

Pure helpers (prefixed with underscore) contain zero I/O and are unit-testable
without mocks.  All network I/O is confined to the three async fetch functions
and the main evaluate_framework9 coroutine.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from atlas.schemas.framework9 import (
    DataGapDetail,
    DataSourceStatus,
    FlowDirection,
    Framework9Result,
    SignalTier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# In-memory cache TTL in seconds (swap for Redis.setex in production).
_CACHE_TTL_SECONDS: Final[int] = 900  # 15 minutes

# Stale threshold: data older than this is flagged as STALE.
_STALE_THRESHOLD_MINUTES: Final[float] = 240.0

# Signal tier score defaults.
_SCORE_TIER1_BULLISH: Final[float] = 92.0
_SCORE_TIER1_BEARISH: Final[float] = 30.0
_SCORE_TIER2_BASE: Final[float] = 82.0
_SCORE_TIER3_BASE: Final[float] = 70.0
_SCORE_TIER4_BASE: Final[float] = 57.0
_SCORE_TIER5_BASELINE: Final[float] = 55.0

# Low liquidity ADV threshold.
_LOW_LIQUIDITY_ADV: Final[float] = 100_000.0
_LOW_LIQUIDITY_CAP: Final[float] = 70.0

# Minimum print thresholds for signal validation.
_MIN_PRINTS_COUNT: Final[int] = 10
_MIN_ADV_FRACTION: Final[float] = 0.02   # 2% of ADV
_MIN_SESSION_USD: Final[float] = 500_000.0

# Whale / institutional thresholds.
_WHALE_THRESHOLD_USD: Final[float] = 10_000_000.0
_INST_DARK_POOL_USD: Final[float] = 500_000.0

# Score grades.
_GRADE_STRONG_BUY_MIN: Final[int] = 80
_GRADE_BUY_MIN: Final[int] = 60
_GRADE_NEUTRAL_MIN: Final[int] = 40
_GRADE_WEAK_MIN: Final[int] = 20

# ---------------------------------------------------------------------------
# In-memory cache (swap for Redis in production)
# ---------------------------------------------------------------------------

# cache: key -> (data_dict, unix_timestamp_of_fetch)
_cache: dict[str, tuple[dict[str, Any], float]] = {}


def _cache_get(key: str) -> tuple[dict[str, Any] | None, float]:
    """Return (data, age_minutes) from the in-memory cache, or (None, 0)."""
    entry = _cache.get(key)
    if entry is None:
        return None, 0.0
    data, fetched_at = entry
    age_minutes = (time.time() - fetched_at) / 60.0
    return data, age_minutes


def _cache_set(key: str, data: dict[str, Any]) -> None:
    """Store data in the in-memory cache with current timestamp."""
    _cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Pure helpers — no I/O
# ---------------------------------------------------------------------------


def _grade_from_score(score: float) -> str:
    """Return the grade label for a given F4 score. Pure function."""
    if score >= _GRADE_STRONG_BUY_MIN:
        return "STRONG BUY"
    if score >= _GRADE_BUY_MIN:
        return "BUY"
    if score >= _GRADE_NEUTRAL_MIN:
        return "NEUTRAL"
    if score >= _GRADE_WEAK_MIN:
        return "WEAK"
    return "AVOID"


def _resolve_spread_position(
    price: float | None,
    bid: float | None,
    ask: float | None,
) -> tuple[float | None, dict[str, bool]]:
    """Calculate (price - bid) / (ask - bid) with explicit gap flags.

    Returns (spread_position, flags).  Flags keys:
      dark_pool_price_missing, dark_pool_bid_missing,
      dark_pool_ask_missing, zero_spread_detected.

    Pure function — no I/O.
    """
    flags: dict[str, bool] = {
        "dark_pool_price_missing": False,
        "dark_pool_bid_missing": False,
        "dark_pool_ask_missing": False,
        "zero_spread_detected": False,
    }
    if price is None:
        flags["dark_pool_price_missing"] = True
        return None, flags
    if bid is None:
        flags["dark_pool_bid_missing"] = True
        return None, flags
    if ask is None:
        flags["dark_pool_ask_missing"] = True
        return None, flags

    spread = ask - bid
    if spread == 0.0:
        flags["zero_spread_detected"] = True
        return 0.5, flags  # neutral — division by zero protection

    return (price - bid) / spread, flags


def build_data_gap_details(
    uw_status: DataSourceStatus,
    polygon_status: DataSourceStatus,
    av_status: DataSourceStatus,
    uw_data: dict[str, Any],
    dp_data: dict[str, Any],
    vol_data: dict[str, Any],
) -> tuple[list[DataGapDetail], str, str | None, str | None, str | None]:
    """Build the data gap list and F1 propagation fields.

    Returns (gaps, severity, f1_badge, f1_message, f1_tooltip).
    Severity is one of 'NONE' | 'PARTIAL' | 'MAJOR' | 'CRITICAL'.

    Pure function — no I/O.
    """
    gaps: list[DataGapDetail] = []
    severity = "NONE"

    # ── Unusual Whales gaps ─────────────────────────────────────────────────
    if uw_status == DataSourceStatus.OFFLINE:
        gaps.append(
            DataGapDetail(
                field="whale_block",
                source="Unusual Whales",
                reason="API unavailable",
                impact="Tier 1 whale detection blocked. Max tier: Tier 2.",
                default_used="Tier 1 signals unavailable",
            )
        )
        severity = "MAJOR"

    elif uw_status == DataSourceStatus.PARTIAL:
        for field in uw_data.get("missing_fields", []):
            gaps.append(
                DataGapDetail(
                    field=field,
                    source="Unusual Whales",
                    reason=f"{field} not returned by API",
                    impact=f"{field} modifier not applied",
                    default_used="0",
                )
            )
        if severity == "NONE":
            severity = "PARTIAL"

    # ── Polygon / dark pool gaps ────────────────────────────────────────────
    if polygon_status == DataSourceStatus.OFFLINE:
        gaps.append(
            DataGapDetail(
                field="dark_pool",
                source="Polygon.io",
                reason="API unavailable",
                impact=(
                    "Dark pool formula cannot run. "
                    "Tier 2 blocked. Modifier = 0."
                ),
                default_used="dark_pool_modifier = 0",
            )
        )
        if uw_status == DataSourceStatus.OFFLINE:
            severity = "MAJOR"
        elif severity != "MAJOR":
            severity = "PARTIAL" if severity == "NONE" else severity

    for field in dp_data.get("missing_fields", []):
        gaps.append(
            DataGapDetail(
                field=f"dark_pool.{field}",
                source="Polygon.io",
                reason=f"{field} missing from trade data",
                impact="spread_position calculation incomplete",
                default_used="spread_position = 0.5 (neutral)",
            )
        )
        if severity == "NONE":
            severity = "PARTIAL"

    # ── Volume / put-call gaps ──────────────────────────────────────────────
    if vol_data.get("put_call_ratio") is None:
        gaps.append(
            DataGapDetail(
                field="put_call_ratio",
                source="Polygon + Alpha Vantage",
                reason="Volume data unavailable from both sources",
                impact="Put/call modifier not applied",
                default_used="put_call_modifier = 0",
            )
        )
        if severity == "NONE":
            severity = "PARTIAL"

    # ── Critical: both volume sources offline ──────────────────────────────
    if (
        av_status == DataSourceStatus.OFFLINE
        and polygon_status == DataSourceStatus.OFFLINE
    ):
        gaps.append(
            DataGapDetail(
                field="options_volume",
                source="Polygon + Alpha Vantage",
                reason="Both volume sources offline",
                impact="Cannot verify Tier 3 or signal thresholds",
                default_used="f4_score = 55 neutral baseline",
            )
        )
        severity = "CRITICAL"

    # ── Build F1 propagation fields ─────────────────────────────────────────
    f1_badge: str | None = None
    f1_message: str | None = None
    f1_tooltip: str | None = None

    if severity == "PARTIAL":
        f1_badge = "F4 PARTIAL DATA"
        f1_message = "Options flow data incomplete. Some signals unavailable."
        f1_tooltip = " | ".join(f"{g.field}: {g.reason}" for g in gaps)

    elif severity == "MAJOR":
        f1_badge = "F4 MAJOR DATA GAP"
        f1_message = (
            "Options flow severely limited. "
            "Key sources offline. "
            "F4 score may be understated."
        )
        f1_tooltip = " | ".join(
            f"{g.source} offline: {g.impact}"
            for g in gaps
            if "unavailable" in g.reason.lower()
        )

    elif severity == "CRITICAL":
        f1_badge = "F4 DATA UNAVAILABLE"
        f1_message = (
            "All options flow sources offline. "
            "F4 defaulting to neutral 55. "
            "Verify manually before acting."
        )
        f1_tooltip = (
            "Unusual Whales, Polygon, and Alpha Vantage "
            "all offline. Cannot score options flow."
        )

    return gaps, severity, f1_badge, f1_message, f1_tooltip


# ---------------------------------------------------------------------------
# Async data fetchers
# ---------------------------------------------------------------------------


async def fetch_unusual_whales_flow(
    ticker: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> tuple[dict[str, Any], DataSourceStatus]:
    """Fetch options flow data from Unusual Whales.

    Returns (data, status).  Data is cached for _CACHE_TTL_SECONDS in the
    in-memory store; stale data (> _STALE_THRESHOLD_MINUTES) is surfaced with
    DataSourceStatus.STALE rather than silently refreshed.
    """
    cache_key = f"uw_flow:{ticker}"
    cached_data, age_minutes = _cache_get(cache_key)

    if cached_data is not None:
        if age_minutes > _STALE_THRESHOLD_MINUTES:
            return cached_data, DataSourceStatus.STALE
        if age_minutes <= _CACHE_TTL_SECONDS / 60.0:
            return cached_data, DataSourceStatus.ONLINE

    try:
        response = await client.get(
            "https://api.unusualwhales.com/api/options/flow",
            params={"ticker": ticker.upper(), "limit": 50},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

        if response.status_code == 429:
            # Rate-limited — return stale cache if available.
            if cached_data is not None:
                return cached_data, DataSourceStatus.RATE_LIMITED
            return {}, DataSourceStatus.OFFLINE

        if response.status_code != 200:
            return {}, DataSourceStatus.OFFLINE

        data: dict[str, Any] = response.json()

        required_fields = ["largest_print_usd", "flow_direction", "total_premium"]
        missing = [f for f in required_fields if f not in data]

        _cache_set(cache_key, data)

        if missing:
            data["missing_fields"] = missing
            return data, DataSourceStatus.PARTIAL

        return data, DataSourceStatus.ONLINE

    except Exception as exc:
        logger.warning(
            "Unusual Whales request failed",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return {"error": str(exc)}, DataSourceStatus.OFFLINE


async def fetch_polygon_dark_pool(
    ticker: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> tuple[dict[str, Any], DataSourceStatus]:
    """Fetch dark pool (condition 41) trades from Polygon.io.

    Calculates spread_position per trade and returns an aggregate summary.
    Caches the aggregate result for _CACHE_TTL_SECONDS.
    """
    cache_key = f"dp_trades:{ticker}"
    cached_data, age_minutes = _cache_get(cache_key)
    if cached_data is not None and age_minutes <= _CACHE_TTL_SECONDS / 60.0:
        return cached_data, DataSourceStatus.ONLINE

    try:
        response = await client.get(
            f"https://api.polygon.io/v3/trades/{ticker}",
            params={"conditions": 41, "limit": 100, "apiKey": api_key},
            timeout=10.0,
        )

        if response.status_code == 429:
            if cached_data is not None:
                return cached_data, DataSourceStatus.RATE_LIMITED
            return {}, DataSourceStatus.OFFLINE

        if response.status_code != 200:
            return {}, DataSourceStatus.OFFLINE

        trades: list[dict[str, Any]] = response.json().get("results", [])

        if not trades:
            result: dict[str, Any] = {"num_prints": 0, "total_usd": 0.0}
            _cache_set(cache_key, result)
            return result, DataSourceStatus.ONLINE

        spread_positions: list[float] = []
        total_usd = 0.0
        missing_fields: list[str] = []

        for trade in trades:
            price = trade.get("price")
            bid = trade.get("bid")
            ask = trade.get("ask")
            size = trade.get("size", 0)

            sp, gap_flags = _resolve_spread_position(price, bid, ask)

            for flag_name, is_missing in gap_flags.items():
                if is_missing and flag_name != "zero_spread_detected":
                    # Derive field name from flag key e.g. dark_pool_price_missing → price
                    field_label = flag_name.replace("dark_pool_", "").replace("_missing", "")
                    missing_fields.append(field_label)

            if sp is not None and price is not None:
                spread_positions.append(sp)
                total_usd += price * size * 100  # options contract multiplier

        result = {
            "num_prints": len(trades),
            "total_usd": total_usd,
            "avg_spread_position": (
                sum(spread_positions) / len(spread_positions)
                if spread_positions
                else None
            ),
            "missing_fields": list(set(missing_fields)),
        }

        _cache_set(cache_key, result)

        status = (
            DataSourceStatus.PARTIAL if missing_fields else DataSourceStatus.ONLINE
        )
        return result, status

    except Exception as exc:
        logger.warning(
            "Polygon dark pool request failed",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return {"error": str(exc)}, DataSourceStatus.OFFLINE


async def fetch_options_volume(
    ticker: str,
    polygon_api_key: str,
    av_api_key: str,
    polygon_status: DataSourceStatus,
    client: httpx.AsyncClient,
) -> tuple[dict[str, Any], DataSourceStatus]:
    """Fetch options volume and put/call ratio.

    Tries Polygon.io first; falls back to Alpha Vantage when Polygon is
    offline or rate-limited.
    """
    use_polygon = polygon_status not in (
        DataSourceStatus.OFFLINE,
        DataSourceStatus.RATE_LIMITED,
    )

    if use_polygon:
        try:
            response = await client.get(
                f"https://api.polygon.io/v2/snapshot/options/{ticker}",
                params={"apiKey": polygon_api_key},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                calls = sum(
                    r.get("day", {}).get("volume", 0)
                    for r in data.get("results", [])
                    if r.get("details", {}).get("contract_type") == "call"
                )
                puts = sum(
                    r.get("day", {}).get("volume", 0)
                    for r in data.get("results", [])
                    if r.get("details", {}).get("contract_type") == "put"
                )
                total = calls + puts
                pc_ratio: float | None = puts / calls if calls > 0 else None

                result: dict[str, Any] = {
                    "total_volume": total,
                    "call_volume": calls,
                    "put_volume": puts,
                    "put_call_ratio": pc_ratio,
                    "source": "polygon",
                }

                if pc_ratio is None:
                    result["missing_fields"] = ["put_call_ratio"]
                    return result, DataSourceStatus.PARTIAL

                return result, DataSourceStatus.ONLINE

        except Exception as exc:
            logger.debug("Polygon options volume failed, trying AV", extra={"error": repr(exc)})

    # Fallback to Alpha Vantage
    try:
        response = await client.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "HISTORICAL_OPTIONS",
                "symbol": ticker.upper(),
                "apikey": av_api_key,
            },
            timeout=15.0,
        )

        if response.status_code == 200:
            data = response.json()
            options = data.get("data", [])

            if not options:
                return {"missing_fields": ["all"]}, DataSourceStatus.PARTIAL

            calls_vol = sum(
                int(o.get("volume", 0) or 0) for o in options if o.get("type") == "call"
            )
            puts_vol = sum(
                int(o.get("volume", 0) or 0) for o in options if o.get("type") == "put"
            )
            pc = puts_vol / calls_vol if calls_vol > 0 else None

            result = {
                "total_volume": calls_vol + puts_vol,
                "call_volume": calls_vol,
                "put_volume": puts_vol,
                "put_call_ratio": pc,
                "source": "alpha_vantage",
            }
            status = DataSourceStatus.PARTIAL if pc is None else DataSourceStatus.ONLINE
            return result, status

    except Exception as exc:
        logger.debug("Alpha Vantage options volume failed", extra={"error": repr(exc)})

    # Both failed.
    return (
        {
            "total_volume": None,
            "put_call_ratio": None,
            "missing_fields": ["all"],
            "error": "Both Polygon and Alpha Vantage failed",
        },
        DataSourceStatus.OFFLINE,
    )


async def get_30_day_adv(
    ticker: str,
    polygon_api_key: str,
    client: httpx.AsyncClient,
) -> float | None:
    """Return the 30-day average daily (equity) volume from Polygon.

    Used for the volume-vs-ADV threshold check in signal tier assignment.
    Returns None when the request fails or the data is unavailable.
    """
    try:
        response = await client.get(
            f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}",
            params={"apiKey": polygon_api_key},
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            # Polygon snapshot returns day.volume for today and prevDay.volume.
            # We approximate ADV using the 30d period volume from the ticker details.
            day_vol: float | None = (
                data.get("ticker", {}).get("day", {}).get("volume")
            )
            return float(day_vol) if day_vol else None
    except Exception as exc:
        logger.debug("ADV fetch failed", extra={"ticker": ticker, "error": repr(exc)})
    return None


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def evaluate_framework9(
    ticker: str,
    uw_api_key: str,
    polygon_api_key: str,
    av_api_key: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Framework9Result:
    """Run the Framework 9 evaluation pipeline for *ticker*.

    Steps:
      1. Fetch all three sources concurrently.
      2. Build data gap list and severity.
      3. Check Framework 7 gate status.
      4. Short-circuit on CRITICAL severity (all sources offline).
      5. Validate minimum signal thresholds.
      6. Assign signal tier and base score.
      7. Covered call exception check.
      8. Conflicting signals check.
      9. Compute put/call modifier.
      10. Compute dark pool modifier.
      11. Apply pre-earnings modifier (from F7 gate).
      12. Low liquidity cap.
      13. Final F4 score calculation.
      14. Determine warning level.
      15. Return Framework9Result.
    """
    import asyncio

    warnings: list[str] = []
    modifiers_skipped: list[str] = []
    modifiers: dict[str, int] = {
        "put_call": 0,
        "dark_pool": 0,
        "pre_earnings": 0,
        "index": 0,
    }
    flags: dict[str, bool] = {
        "covered_call": False,
        "covered_call_unverifiable": False,
        "pre_earnings": False,
        "conflicting": False,
        "low_liquidity": False,
        "index_flow": False,
    }

    managed_client = client is None
    _client: httpx.AsyncClient = client if client is not None else httpx.AsyncClient()

    try:
        # Step 1 — Fetch all three sources concurrently.
        (uw_data, uw_status), (dp_data, polygon_status), adv = await asyncio.gather(
            fetch_unusual_whales_flow(ticker, uw_api_key, _client),
            fetch_polygon_dark_pool(ticker, polygon_api_key, _client),
            get_30_day_adv(ticker, polygon_api_key, _client),
        )

        vol_data, av_status = await fetch_options_volume(
            ticker, polygon_api_key, av_api_key, polygon_status, _client
        )

        # Step 2 — Build data gap details.
        gaps, severity, f1_badge, f1_msg, f1_tip = build_data_gap_details(
            uw_status, polygon_status, av_status, uw_data, dp_data, vol_data
        )

        # Step 3 — Framework 7 gate check (internal service call).
        gate_active = False
        try:
            from datetime import date

            from atlas.config import get_settings
            from atlas.services.framework7_service import (
                calculate_gate_close_date,
                get_earnings_date,
            )

            settings = get_settings()
            earnings_date_str = await get_earnings_date(ticker, settings.alphavantage_api_key)
            if earnings_date_str:
                earnings_date = date.fromisoformat(earnings_date_str)
                gate_close = calculate_gate_close_date(earnings_date)
                gate_active = date.today() >= gate_close
        except Exception as exc:
            warnings.append(
                "Could not verify earnings gate — pre-earnings modifier not applied"
            )
            logger.debug(
                "Framework 7 gate check failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )

        # Step 4 — Critical failure short-circuit.
        if severity == "CRITICAL":
            return Framework9Result(
                ticker=ticker,
                f4_score=_SCORE_TIER5_BASELINE,
                f4_grade=_grade_from_score(_SCORE_TIER5_BASELINE),
                f4_contribution=round(_SCORE_TIER5_BASELINE * 0.15, 2),
                signal_tier=SignalTier.TIER_5_NONE,
                flow_direction=FlowDirection.NEUTRAL,
                largest_print_usd=None,
                dark_pool_spread_position=None,
                dark_pool_direction=None,
                put_call_ratio=None,
                put_call_modifier=0,
                dark_pool_modifier=0,
                pre_earnings_modifier=0,
                index_modifier=0,
                options_volume_vs_adv=None,
                signal_valid=False,
                minimum_threshold_met=False,
                covered_call_exception=False,
                covered_call_unverifiable=False,
                pre_earnings_reduction=False,
                conflicting_signals=False,
                low_liquidity=False,
                potential_index_flow=False,
                uw_status=uw_status,
                polygon_status=polygon_status,
                av_status=av_status,
                data_gaps=gaps,
                data_gap_severity=severity,
                f1_propagation_badge=f1_badge,
                f1_propagation_message=f1_msg,
                f1_propagation_tooltip=f1_tip,
                modifiers_skipped=["all"],
                warning_level="RED",
                warning_messages=["All options data sources offline. F4 defaulting to neutral 55."],
                breakdown={},
            )

        # Step 5 — Minimum threshold validation.
        largest_print: float = float(uw_data.get("largest_print_usd") or 0)
        num_prints: int = int(dp_data.get("num_prints") or 0)
        total_volume: float = float(vol_data.get("total_volume") or 0)

        volume_vs_adv: float | None = (
            total_volume / adv if adv and adv > 0 and total_volume else None
        )

        threshold_a = num_prints >= _MIN_PRINTS_COUNT
        threshold_b = (
            volume_vs_adv is not None and volume_vs_adv >= _MIN_ADV_FRACTION
        )
        threshold_c = largest_print >= _MIN_SESSION_USD
        threshold_met = threshold_a or threshold_b or threshold_c

        # Step 6 — Low liquidity check.
        if adv is not None and adv < _LOW_LIQUIDITY_ADV:
            flags["low_liquidity"] = True
            warnings.append(
                "Low liquidity — signals may be unreliable. F4 capped at 70."
            )

        # Step 7 — Assign signal tier and base score.
        uw_direction: str = str(uw_data.get("flow_direction") or "NEUTRAL").upper()
        spread_pos: float | None = dp_data.get("avg_spread_position")

        if not threshold_met:
            tier = SignalTier.TIER_5_NONE
            base_score: float = _SCORE_TIER5_BASELINE
            warnings.append(
                "Signal below minimum threshold — using neutral baseline 55"
            )

        elif (
            uw_status not in (DataSourceStatus.OFFLINE, DataSourceStatus.RATE_LIMITED)
            and largest_print >= _WHALE_THRESHOLD_USD
        ):
            tier = SignalTier.TIER_1_WHALE
            base_score = (
                _SCORE_TIER1_BULLISH if uw_direction == "BULLISH" else _SCORE_TIER1_BEARISH
            )

        elif (
            polygon_status not in (DataSourceStatus.OFFLINE, DataSourceStatus.RATE_LIMITED)
            and dp_data.get("total_usd", 0) >= _INST_DARK_POOL_USD
            and spread_pos is not None
            and spread_pos > 0.6
            and threshold_b
        ):
            tier = SignalTier.TIER_2_INSTITUTIONAL
            base_score = _SCORE_TIER2_BASE

        elif volume_vs_adv is not None and volume_vs_adv >= 2.0:
            tier = SignalTier.TIER_3_UNUSUAL
            base_score = _SCORE_TIER3_BASE

        elif volume_vs_adv is not None and volume_vs_adv >= 1.0:
            tier = SignalTier.TIER_4_WEAK
            base_score = _SCORE_TIER4_BASE

        else:
            tier = SignalTier.TIER_5_NONE
            base_score = _SCORE_TIER5_BASELINE

        # Step 8 — Covered call exception.
        if uw_direction == "BEARISH":
            if polygon_status == DataSourceStatus.OFFLINE:
                flags["covered_call_unverifiable"] = True
                warnings.append(
                    "Cannot verify covered call exception — "
                    "dark pool data unavailable. Bearish signal applied."
                )
            elif spread_pos is not None and spread_pos > 0.6:
                flags["covered_call"] = True
                base_score = max(base_score, _SCORE_TIER5_BASELINE)
                warnings.append(
                    f"Covered call exception applied — dark pool buy-side confirmed "
                    f"(spread={spread_pos:.2f})"
                )

        # Step 9 — Conflicting signals check.
        dp_direction: str
        if spread_pos is not None and spread_pos > 0.6:
            dp_direction = "BULLISH"
        elif spread_pos is not None and spread_pos < 0.4:
            dp_direction = "BEARISH"
        else:
            dp_direction = "NEUTRAL"

        if (
            spread_pos is not None
            and uw_direction != "NEUTRAL"
            and dp_direction != "NEUTRAL"
            and uw_direction != dp_direction
        ):
            flags["conflicting"] = True
            base_score = (base_score + _SCORE_TIER5_BASELINE) / 2.0
            warnings.append(
                f"Conflicting signals — UW: {uw_direction} vs "
                f"Dark pool: {dp_direction}. Score averaged down."
            )

        # Step 10 — Put/call modifier.
        put_call: float | None = vol_data.get("put_call_ratio")
        prev_put_call: float | None = vol_data.get("previous_put_call_ratio")

        if put_call is None:
            modifiers["put_call"] = 0
            modifiers_skipped.append("put_call")
            warnings.append(
                "Put/call modifier not applied — ratio data unavailable"
            )
        elif prev_put_call is not None and prev_put_call > 1.3 and put_call < 0.8:
            modifiers["put_call"] = +5
        elif put_call > 1.3:
            modifiers["put_call"] = -3
        elif put_call < 0.7:
            modifiers["put_call"] = -5
        else:
            modifiers["put_call"] = 0

        # Step 11 — Dark pool modifier.
        if polygon_status == DataSourceStatus.OFFLINE:
            modifiers["dark_pool"] = 0
            modifiers_skipped.append("dark_pool")
            warnings.append(
                "Dark pool modifier not applied — Polygon unavailable"
            )
        elif spread_pos is None:
            modifiers["dark_pool"] = 0
            modifiers_skipped.append("dark_pool")
            warnings.append(
                "Dark pool modifier not applied — spread position unavailable"
            )
        elif spread_pos > 0.6 and threshold_met:
            modifiers["dark_pool"] = +3
        elif spread_pos < 0.4:
            modifiers["dark_pool"] = -3
        else:
            modifiers["dark_pool"] = 0

        # Step 12 — Pre-earnings modifier.
        if gate_active:
            flags["pre_earnings"] = True
            reduction = int(base_score * 0.30)
            modifiers["pre_earnings"] = -reduction
            warnings.append(
                f"Pre-earnings reduction applied — "
                f"-{reduction} points (30% of {base_score:.0f})"
            )

        # Step 13 — Low liquidity cap.
        if flags["low_liquidity"]:
            base_score = min(base_score, _LOW_LIQUIDITY_CAP)

        # Step 14 — Final F4 score.
        f4_raw = (
            base_score
            + modifiers["put_call"]
            + modifiers["dark_pool"]
            + modifiers["pre_earnings"]
            + modifiers["index"]
        )
        f4_score = max(0.0, min(100.0, float(f4_raw)))

        # Step 15 — Warning level.
        if severity in ("MAJOR", "CRITICAL"):
            warning_level = "RED"
        elif severity == "PARTIAL" or flags["conflicting"]:
            warning_level = "AMBER"
        else:
            warning_level = "NONE"

        # Resolve flow direction enum safely.
        try:
            flow_dir = FlowDirection(uw_direction)
        except ValueError:
            flow_dir = FlowDirection.NEUTRAL

        return Framework9Result(
            ticker=ticker,
            f4_score=round(f4_score, 2),
            f4_grade=_grade_from_score(f4_score),
            f4_contribution=round(f4_score * 0.15, 2),
            signal_tier=tier,
            flow_direction=flow_dir,
            largest_print_usd=largest_print or None,
            dark_pool_spread_position=(
                round(spread_pos, 4) if spread_pos is not None else None
            ),
            dark_pool_direction=dp_direction,
            put_call_ratio=(
                round(put_call, 2) if put_call is not None else None
            ),
            put_call_modifier=modifiers["put_call"],
            dark_pool_modifier=modifiers["dark_pool"],
            pre_earnings_modifier=modifiers["pre_earnings"],
            index_modifier=modifiers["index"],
            options_volume_vs_adv=(
                round(volume_vs_adv, 4) if volume_vs_adv is not None else None
            ),
            signal_valid=threshold_met,
            minimum_threshold_met=threshold_met,
            covered_call_exception=flags["covered_call"],
            covered_call_unverifiable=flags["covered_call_unverifiable"],
            pre_earnings_reduction=flags["pre_earnings"],
            conflicting_signals=flags["conflicting"],
            low_liquidity=flags["low_liquidity"],
            potential_index_flow=flags["index_flow"],
            uw_status=uw_status,
            polygon_status=polygon_status,
            av_status=av_status,
            data_gaps=gaps,
            data_gap_severity=severity,
            f1_propagation_badge=f1_badge,
            f1_propagation_message=f1_msg,
            f1_propagation_tooltip=f1_tip,
            modifiers_skipped=modifiers_skipped,
            warning_level=warning_level,
            warning_messages=warnings,
            breakdown={
                "base_score": base_score,
                "tier": tier.value,
                "whale_block_usd": largest_print,
                "spread_position": spread_pos,
                "put_call_ratio": put_call,
                "volume_vs_adv": volume_vs_adv,
                "modifiers": modifiers,
                "flags": flags,
                "thresholds": {
                    "A_prints": threshold_a,
                    "B_volume": threshold_b,
                    "C_dollar": threshold_c,
                },
            },
        )

    finally:
        if managed_client:
            await _client.aclose()
