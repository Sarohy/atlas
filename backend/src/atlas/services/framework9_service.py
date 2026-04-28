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

    Source-of-truth contract: F9 reuses the F4 score produced by
    ``OptionsFlowService.compute_options_flow`` (the same data already
    rendered in the F4 panel).  F9's only job is to layer F9-specific
    timing modifiers (pre-earnings reduction from F7) on top of the F4
    score.  It does NOT re-fetch options data from Unusual Whales or
    Polygon — those endpoints have moved/become entitled-only and
    fetching them here previously caused a spurious "F4 MAJOR DATA GAP"
    badge while the F4 panel itself was healthy.

    Modifier policy:
      • put_call and dark_pool modifiers are NOT applied here. F4 already
        weights call/put ratio (20%) and dark-pool premium (15%) inside
        its own composite, so re-applying them would double-count.
      • pre_earnings reduction (-30%) is applied when F7's earnings gate
        is active (F4 has no earnings awareness on its own).
      • index_modifier remains 0 (no signal source).
    """
    from atlas.services.options_flow_service import OptionsFlowService

    # Suppress unused-arg warnings — kept for backward-compatible signature
    # used by callers that pass through all keys (regime_modifier_service,
    # leaps_service, etc.).
    _ = (polygon_api_key, av_api_key)

    warnings: list[str] = []
    modifiers_skipped: list[str] = ["put_call", "dark_pool", "index"]
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
        # Step 1 — Reuse F4 (OptionsFlowService) as the single source of truth.
        f4_service = OptionsFlowService(api_key=uw_api_key)
        try:
            f4 = await f4_service.compute_options_flow(ticker)
            f4_available = True
        except Exception as exc:
            logger.warning(
                "F4 OptionsFlowService failed — F9 will degrade to neutral baseline",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            f4 = None
            f4_available = False

        # Step 2 — Map F4 → F9 fields, or build degraded response.
        gaps: list[DataGapDetail] = []
        severity: str = "NONE"
        f1_badge: str | None = None
        f1_msg: str | None = None
        f1_tip: str | None = None

        if not f4_available or f4 is None:
            # F4 unavailable — graceful degradation. Mirror F4's own
            # behaviour: never fabricate a score, surface the gap clearly.
            gaps.append(
                DataGapDetail(
                    field="f4_options_flow",
                    source="OptionsFlowService (Unusual Whales)",
                    reason="F4 service call failed",
                    impact="F4 score unavailable; F9 cannot evaluate flow.",
                    default_used="f4_score = 55 neutral baseline",
                )
            )
            severity = "MAJOR"
            f1_badge = "F4 SERVICE UNAVAILABLE"
            f1_msg = (
                "Options flow service unavailable. F4 score defaulting to "
                "neutral 55. Verify manually before acting."
            )
            f1_tip = "OptionsFlowService.compute_options_flow() raised an exception."

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
                uw_status=DataSourceStatus.OFFLINE,
                polygon_status=DataSourceStatus.OFFLINE,
                av_status=DataSourceStatus.OFFLINE,
                data_gaps=gaps,
                data_gap_severity=severity,
                f1_propagation_badge=f1_badge,
                f1_propagation_message=f1_msg,
                f1_propagation_tooltip=f1_tip,
                modifiers_skipped=["all"],
                warning_level="RED",
                warning_messages=[
                    "Options flow service offline — F4 score unavailable. "
                    "F9 returning neutral baseline 55."
                ],
                breakdown={},
            )

        # ----- F4 succeeded — derive F9 fields from F4's response. -----
        base_score: float = float(f4.f4_score)
        cp_ratio: float | None = f4.call_put_ratio.ratio
        largest_premium: float = float(f4.whale_block.largest_premium or 0.0)
        largest_dp: float | None = f4.dark_pool.largest_print
        dp_count: int = f4.dark_pool.print_count or 0

        # Flow direction is implied by F4's call/put ratio (it has no explicit
        # bull/bear field). Thresholds match F4's own _score_cp_ratio bands.
        if cp_ratio is None:
            uw_direction: str = "NEUTRAL"
        elif cp_ratio > 1.5:
            uw_direction = "BULLISH"
        elif cp_ratio < 0.7:
            uw_direction = "BEARISH"
        else:
            uw_direction = "NEUTRAL"

        # Map F4's signal hierarchy (GOLD/BLUE/GREEN/YELLOW/GREY/WHITE) onto
        # F9's tier enum so downstream UI keeps working unchanged.
        f4_tier_str = (
            f4.signal_tier.value
            if hasattr(f4.signal_tier, "value")
            else str(f4.signal_tier)
        )
        f4_to_f9_tier: dict[str, SignalTier] = {
            "GOLD": SignalTier.TIER_1_WHALE,
            "BLUE": SignalTier.TIER_1_WHALE,
            "GREEN": SignalTier.TIER_2_INSTITUTIONAL,
            "YELLOW": SignalTier.TIER_3_UNUSUAL,
            "GREY": SignalTier.TIER_4_WEAK,
            "WHITE": SignalTier.TIER_5_NONE,
        }
        tier: SignalTier = f4_to_f9_tier.get(f4_tier_str, SignalTier.TIER_5_NONE)

        # Step 3 — F7 earnings gate check (timing only — F4 has no earnings awareness).
        gate_active = False
        try:
            from datetime import date

            from atlas.config import get_settings
            from atlas.services.framework7_service import (
                calculate_gate_close_date,
                get_earnings_date,
            )

            settings = get_settings()
            earnings_date_str = await get_earnings_date(
                ticker, settings.alphavantage_api_key
            )
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

        # Step 4 — Apply pre-earnings reduction (the only modifier F9 layers on F4).
        if gate_active:
            flags["pre_earnings"] = True
            reduction = int(base_score * 0.30)
            modifiers["pre_earnings"] = -reduction
            warnings.append(
                f"Pre-earnings reduction applied — "
                f"-{reduction} points (30% of F4 score {base_score:.0f})"
            )

        # Step 5 — Final F4 score.
        f4_score = max(0.0, min(100.0, base_score + modifiers["pre_earnings"]))

        # Step 6 — Threshold/validity flags carried over from F4's data.
        threshold_met = base_score >= _GRADE_BUY_MIN  # F4 BUY-or-better => actionable
        threshold_a = dp_count >= _MIN_PRINTS_COUNT
        threshold_b = False  # volume-vs-ADV not computed when reusing F4
        threshold_c = largest_premium >= _MIN_SESSION_USD

        # Step 7 — Warning level (no MAJOR/CRITICAL when F4 is healthy).
        warning_level = "AMBER" if flags["pre_earnings"] else "NONE"

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
            largest_print_usd=largest_dp,
            dark_pool_spread_position=None,  # not exposed by F4
            dark_pool_direction=None,
            put_call_ratio=(round(cp_ratio, 2) if cp_ratio is not None else None),
            put_call_modifier=0,
            dark_pool_modifier=0,
            pre_earnings_modifier=modifiers["pre_earnings"],
            index_modifier=0,
            options_volume_vs_adv=None,
            signal_valid=threshold_met,
            minimum_threshold_met=threshold_met,
            covered_call_exception=False,
            covered_call_unverifiable=False,
            pre_earnings_reduction=flags["pre_earnings"],
            conflicting_signals=False,
            low_liquidity=False,
            potential_index_flow=False,
            uw_status=DataSourceStatus.ONLINE,
            polygon_status=DataSourceStatus.ONLINE,
            av_status=DataSourceStatus.ONLINE,
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
                "f4_source_score": f4.f4_score,
                "f4_signal_tier": f4_tier_str,
                "whale_block_usd": largest_premium,
                "dark_pool_largest_usd": largest_dp,
                "dark_pool_count": dp_count,
                "put_call_ratio": cp_ratio,
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
