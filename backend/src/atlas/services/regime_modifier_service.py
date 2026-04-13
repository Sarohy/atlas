"""Regime Modifier service.

Fetches live Brent crude and VIX values from Alpha Vantage, retrieves the base
Framework Score for a ticker, and applies one of three market-regime rules to
produce an adjusted conviction score with cash-management guidance.

Rule priority (highest to lowest):
  Rule 1 — Crisis   : active war OR Brent > $110 OR VIX > 35     → -10 pts
  Rule 2 — Caution  : Brent in [$95, $110] AND VIX in [24, 35]   → -5 pts
  Rule 3 — Clear    : Brent < $95 for 2 consecutive closes AND VIX < 24 → +5 pts
  None   — Normal   : no modifier; cash guidance set to zero

Pure helpers (_determine_rule, _compute_regime_output) are side-effect-free
and unit-testable without any mocks or network calls.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Final

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.framework_score import FrameworkScoreResponse
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.framework_score_service import FrameworkScoreService
from atlas.services.ticker_service import TickerService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alpha Vantage endpoints
# ---------------------------------------------------------------------------

# Brent crude oil daily prices (USD per barrel).
# Returns JSON: {"data": [{"date": "YYYY-MM-DD", "value": "65.10"}, ...]}
# Data is returned in descending date order.
_AV_BRENT_URL: Final[str] = "https://www.alphavantage.co/query"

# CBOE VIX index — fetched via GLOBAL_QUOTE for the most recent value.
# Returns JSON: {"Global Quote": {"05. price": "22.50", ...}}
_AV_GLOBAL_QUOTE_URL: Final[str] = "https://www.alphavantage.co/query"

# Yahoo Finance chart API — fallback for VIX when Alpha Vantage returns empty.
# Returns JSON: {"chart": {"result": [{"meta": {"regularMarketPrice": 19.99, ...}}]}}
# %5E is URL-encoded '^'.
_YAHOO_VIX_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart/%5EVIX"

# Yahoo Finance chart API — primary source for Brent crude (BZ=F futures).
# Returns current price via meta.regularMarketPrice and previous close via
# meta.chartPreviousClose. More up-to-date than Alpha Vantage's EIA dataset.
_YAHOO_BRENT_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart/BZ%3DF"

# Number of most-recent Brent data points needed (2 for consecutive check).
_BRENT_NUM_CLOSES: Final[int] = 2

# ---------------------------------------------------------------------------
# Rule 1 — Crisis thresholds
# ---------------------------------------------------------------------------

# Brent above this triggers Rule 1 (strictly greater than).
_RULE1_BRENT_THRESHOLD: Final[float] = 110.0  # USD per barrel

# VIX above this triggers Rule 1 (strictly greater than).
_RULE1_VIX_THRESHOLD: Final[float] = 35.0

# Score modifier for Rule 1.
_RULE1_SCORE_DELTA: Final[int] = -10

# Cash fraction bounds for Rule 1 (as decimals: 0.35 = 35 %).
_RULE1_MIN_CASH_PCT: Final[float] = 0.35
_RULE1_MAX_CASH_PCT: Final[float] = 0.40

# ---------------------------------------------------------------------------
# Rule 2 — Caution thresholds
# ---------------------------------------------------------------------------

# Brent must be within this inclusive range for a Rule 2 trigger.
_RULE2_BRENT_LOW: Final[float] = 95.0  # USD per barrel (inclusive)
_RULE2_BRENT_HIGH: Final[float] = 110.0  # USD per barrel (inclusive)

# VIX must be within this inclusive range for a Rule 2 trigger.
_RULE2_VIX_LOW: Final[float] = 24.0  # (inclusive)
_RULE2_VIX_HIGH: Final[float] = 35.0  # (inclusive)

# Score modifier for Rule 2.
_RULE2_SCORE_DELTA: Final[int] = -5

# Cash fraction bounds for Rule 2.
_RULE2_MIN_CASH_PCT: Final[float] = 0.25
_RULE2_MAX_CASH_PCT: Final[float] = 0.35

# ---------------------------------------------------------------------------
# Rule 3 — Clear thresholds
# ---------------------------------------------------------------------------

# Brent must be strictly below this for Rule 3 (checked against last 2 closes).
_RULE3_BRENT_CLEAR: Final[float] = 95.0  # USD per barrel

# VIX must be strictly below this for Rule 3.
_RULE3_VIX_CLEAR: Final[float] = 24.0

# Score modifier for Rule 3.
_RULE3_SCORE_DELTA: Final[int] = 5

# Cash fraction bounds for Rule 3.
_RULE3_MIN_CASH_PCT: Final[float] = 0.10
_RULE3_MAX_CASH_PCT: Final[float] = 0.12

# ---------------------------------------------------------------------------
# Output text constants — multi-line strings match the spec verbatim
# ---------------------------------------------------------------------------

_OUTPUT_RULE1: Final[str] = "must stay in cash\ncannot be touched\nfor any trade"

_OUTPUT_RULE2: Final[str] = "must stay in cash"

_OUTPUT_RULE3: Final[str] = "only this stays in cash\neverything else\ncan be deployed"

_OUTPUT_NONE: Final[str] = ""


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects, fully unit-testable
# ---------------------------------------------------------------------------


def _parse_yahoo_vix_payload(payload: dict) -> float | None:  # type: ignore[type-arg]
    """Extract the VIX level from a Yahoo Finance chart API response.

    Reads ``chart.result[0].meta.regularMarketPrice``.
    Returns None if the key is absent or the payload is malformed.

    Pure function — no I/O.
    """
    try:
        chart = payload.get("chart") or {}
        results_raw = chart.get("result")
        if not results_raw:
            return None
        first = results_raw[0]
        if not isinstance(first, dict):
            return None
        meta = first.get("meta") or {}
        if not isinstance(meta, dict):
            return None
        price = meta.get("regularMarketPrice")
        return float(price) if price is not None else None
    except (TypeError, ValueError, IndexError):
        return None


def _parse_yahoo_brent_payload(payload: dict) -> list[float]:  # type: ignore[type-arg]
    """Extract up to two Brent closes from a Yahoo Finance chart API response.

    Returns [regularMarketPrice, chartPreviousClose] (most-recent first),
    omitting any value that is None or unparseable.
    Returns [] if the payload is malformed.

    Pure function — no I/O.
    """
    try:
        chart = payload.get("chart") or {}
        results_raw = chart.get("result")
        if not results_raw:
            return []
        first = results_raw[0]
        if not isinstance(first, dict):
            return []
        meta = first.get("meta") or {}
        if not isinstance(meta, dict):
            return []
        closes: list[float] = []
        current = meta.get("regularMarketPrice")
        if current is not None:
            closes.append(float(current))
        prev = meta.get("chartPreviousClose")
        if prev is not None:
            closes.append(float(prev))
        return closes
    except (TypeError, ValueError, IndexError):
        return []


def _determine_rule(
    active_war: bool,
    brent_price: float,
    vix_value: float,
    brent_consecutive_below_95: bool,
) -> int | None:
    """Return the highest-priority regime rule number that fires, or None.

    Rules are evaluated in priority order:

    Rule 1 (Crisis) — any ONE of:
      • Active war confirmed (active_war is True)
      • Brent crude above $110
      • VIX above 35

    Rule 2 (Caution) — BOTH of:
      • Brent in [$95, $110]
      • VIX in [24, 35]

    Rule 3 (Clear) — BOTH of:
      • Brent below $95 for two consecutive daily closes
      • VIX below 24

    Pure function — no I/O.
    """
    # ── Rule 1 ──────────────────────────────────────────────────────────────
    if active_war or brent_price > _RULE1_BRENT_THRESHOLD or vix_value > _RULE1_VIX_THRESHOLD:
        return 1

    # ── Rule 2 ──────────────────────────────────────────────────────────────
    brent_in_caution = _RULE2_BRENT_LOW <= brent_price <= _RULE2_BRENT_HIGH
    vix_in_caution = _RULE2_VIX_LOW <= vix_value <= _RULE2_VIX_HIGH
    if brent_in_caution and vix_in_caution:
        return 2

    # ── Rule 3 ──────────────────────────────────────────────────────────────
    if brent_consecutive_below_95 and vix_value < _RULE3_VIX_CLEAR:
        return 3

    return None


def _compute_regime_output(
    rule: int | None,
    base_score: int,
    position_value_usd: Decimal | None,
) -> tuple[int, float, float, Decimal | None, Decimal | None, str]:
    """Compute the adjusted score, cash bounds, and output text for a rule.

    Returns:
        (adjusted_score, min_cash_pct, max_cash_pct,
         min_cash_usd, max_cash_usd, output_text)

    ``position_value_usd`` is the ticker's portfolio position value in USD.
    When None (ticker not in portfolio) the USD cash amounts are also None.

    Pure function — no I/O.
    """
    if rule == 1:
        delta = _RULE1_SCORE_DELTA
        min_pct = _RULE1_MIN_CASH_PCT
        max_pct = _RULE1_MAX_CASH_PCT
        text = _OUTPUT_RULE1
    elif rule == 2:
        delta = _RULE2_SCORE_DELTA
        min_pct = _RULE2_MIN_CASH_PCT
        max_pct = _RULE2_MAX_CASH_PCT
        text = _OUTPUT_RULE2
    elif rule == 3:
        delta = _RULE3_SCORE_DELTA
        min_pct = _RULE3_MIN_CASH_PCT
        max_pct = _RULE3_MAX_CASH_PCT
        text = _OUTPUT_RULE3
    else:
        # No regime rule triggered — score and cash guidance unchanged.
        adjusted = base_score
        return adjusted, 0.0, 0.0, None, None, _OUTPUT_NONE

    adjusted_score = max(0, min(100, base_score + delta))

    min_cash_usd: Decimal | None = None
    max_cash_usd: Decimal | None = None
    if position_value_usd is not None:
        min_cash_usd = (position_value_usd * Decimal(str(min_pct))).quantize(Decimal("0.01"))
        max_cash_usd = (position_value_usd * Decimal(str(max_pct))).quantize(Decimal("0.01"))

    return adjusted_score, min_pct, max_pct, min_cash_usd, max_cash_usd, text


# ---------------------------------------------------------------------------
# Service class — orchestrates Polygon fetches + FW score + rule application
# ---------------------------------------------------------------------------


class RegimeModifierService:
    """Computes the regime-adjusted conviction score for a single ticker.

    Concurrently fetches:
      • Brent crude daily closes from Alpha Vantage (function=BRENT)
      • VIX latest value from Alpha Vantage (GLOBAL_QUOTE ^VIX)
      • Framework Score for the ticker

    Also reads the ticker's ``position_value`` from the database to compute
    USD cash bounds.

    Parameters
    ----------
    polygon_api_key:
        Polygon.io API key — forwarded to the internal FrameworkScoreService.
    alphavantage_api_key:
        Alpha Vantage key — used for Brent crude and VIX data.
    transcript_api_key, benzinga_api_key, unusual_whales_api_key, sec_api_key:
        Keys forwarded to the internal ``FrameworkScoreService`` instance.
    session:
        SQLAlchemy async session used to look up portfolio position value.
    """

    def __init__(
        self,
        polygon_api_key: str,
        alphavantage_api_key: str,
        transcript_api_key: str,
        benzinga_api_key: str,
        unusual_whales_api_key: str,
        sec_api_key: str,
        session: AsyncSession,
    ) -> None:
        self._av_key = alphavantage_api_key
        self._fw_service = FrameworkScoreService(
            polygon_api_key=polygon_api_key,
            alphavantage_api_key=alphavantage_api_key,
            transcript_api_key=transcript_api_key,
            benzinga_api_key=benzinga_api_key,
            unusual_whales_api_key=unusual_whales_api_key,
            sec_api_key=sec_api_key,
        )
        self._ticker_service = TickerService(session)

    async def compute_regime_modifier(
        self,
        ticker: str,
        active_war: bool,
        provided_base_score: int | None = None,
    ) -> RegimeModifierResponse:
        """Return the regime-adjusted score and cash guidance for ``ticker``.

        Runs two or three concurrent tasks:
          1. Fetch Brent crude daily closes from Alpha Vantage
          2. Fetch VIX latest value from Alpha Vantage
          3. Compute Framework Score for the ticker — skipped when
             ``provided_base_score`` is supplied by the caller (Frontend F1
             cache) to avoid redundant computation and score skew.
        """
        async with httpx.AsyncClient() as client:
            brent_task = self._fetch_brent(client)
            vix_task = self._fetch_vix(client)

            brent_closes: Any
            vix_value_raw: Any
            fw_result: Any

            if provided_base_score is None:
                # Caller has no cached score — fetch it concurrently.
                brent_closes, vix_value_raw, fw_result = await asyncio.gather(
                    brent_task,
                    vix_task,
                    self._fw_service.compute_framework_score(ticker),
                    return_exceptions=True,
                )
            else:
                # Use caller-supplied score; only fetch market data.
                _market = await asyncio.gather(brent_task, vix_task, return_exceptions=True)
                brent_closes = _market[0]
                vix_value_raw = _market[1]
                fw_result = provided_base_score

        # ── Extract Brent price and consecutive-close flag ─────────────────
        brent_price: float | None = None
        brent_consecutive_below_95 = False
        if isinstance(brent_closes, list) and brent_closes:
            brent_price = brent_closes[0]
            if len(brent_closes) >= 2:
                brent_consecutive_below_95 = all(v < _RULE3_BRENT_CLEAR for v in brent_closes[:2])
        else:
            logger.warning(
                "Brent crude fetch failed or returned no data",
                extra={"error": repr(brent_closes)},
            )

        # ── Extract VIX value ─────────────────────────────────────────────
        vix_value: float | None = None
        if isinstance(vix_value_raw, float):
            vix_value = vix_value_raw
        else:
            logger.warning(
                "VIX fetch failed or returned no data",
                extra={"error": repr(vix_value_raw)},
            )

        # ── Extract base Framework Score ──────────────────────────────────
        if isinstance(fw_result, int):
            # Caller-supplied score passed through directly.
            base_score = fw_result
        elif isinstance(fw_result, FrameworkScoreResponse):
            base_score = fw_result.final_score
        else:
            logger.error(
                "Framework Score fetch failed",
                extra={"ticker": ticker, "error": repr(fw_result)},
            )
            base_score = 50

        # ── Look up position value from DB ────────────────────────────────
        position_value_usd: Decimal | None = None
        db_ticker = await self._ticker_service.get_by_ticker(ticker)
        if db_ticker is not None and db_ticker.position_value is not None:
            position_value_usd = db_ticker.position_value

        # ── Apply regime rules ────────────────────────────────────────────
        # active_war alone is sufficient to trigger Rule 1; market data is
        # only required when the war flag is not set (Brent/VIX thresholds
        # cannot be evaluated without real values).
        if brent_price is not None and vix_value is not None:
            rule = _determine_rule(
                active_war=active_war,
                brent_price=brent_price,
                vix_value=vix_value,
                brent_consecutive_below_95=brent_consecutive_below_95,
            )
        elif active_war:
            # No market data but war is confirmed — Rule 1 fires unconditionally.
            rule = 1
        else:
            rule = None

        (
            adjusted_score,
            min_cash_pct,
            max_cash_pct,
            min_cash_usd,
            max_cash_usd,
            output_text,
        ) = _compute_regime_output(rule, base_score, position_value_usd)

        return RegimeModifierResponse(
            ticker=ticker,
            active_war=active_war,
            brent_price=brent_price,
            vix_value=vix_value,
            base_score=base_score,
            adjusted_score=adjusted_score,
            rule_triggered=rule,
            min_cash_pct=min_cash_pct,
            max_cash_pct=max_cash_pct,
            min_cash_usd=float(min_cash_usd) if min_cash_usd is not None else None,
            max_cash_usd=float(max_cash_usd) if max_cash_usd is not None else None,
            output_text=output_text,
        )

    async def _fetch_brent(self, client: httpx.AsyncClient) -> list[float]:
        """Fetch the two most recent Brent crude closes.

        Tries Yahoo Finance (BZ=F) first — returns live intraday price plus
        the previous session close, so the data is always current.
        Falls back to Alpha Vantage function=BRENT (daily EIA dataset) when
        Yahoo Finance fails; that dataset can lag by ~1-2 weeks but is the
        only alternative.

        Returns a list of up to 2 floats in descending date order
        (most recent first). Returns [] if both sources fail.
        """
        # ── Yahoo Finance (primary) ───────────────────────────────────────
        try:
            yf_response = await client.get(
                _YAHOO_BRENT_URL,
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=10.0,
            )
            yf_response.raise_for_status()
            closes = _parse_yahoo_brent_payload(yf_response.json())
            if closes:
                return closes
            logger.warning("Yahoo Finance Brent payload had no price; using Alpha Vantage fallback")
        except Exception:
            logger.warning("Yahoo Finance Brent fetch failed; using Alpha Vantage fallback")

        # ── Alpha Vantage (fallback) ──────────────────────────────────────
        try:
            response = await client.get(
                _AV_BRENT_URL,
                params={"function": "BRENT", "interval": "daily", "apikey": self._av_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: dict = response.json()  # type: ignore[type-arg]
            data: list[dict] = payload.get("data", [])  # type: ignore[type-arg]
            # Alpha Vantage returns entries newest-first; skip "." values
            closes_av: list[float] = []
            for entry in data:
                raw = entry.get("value", ".")
                if raw != ".":
                    closes_av.append(float(raw))
                if len(closes_av) >= _BRENT_NUM_CLOSES:
                    break
            return closes_av
        except Exception:
            logger.exception("Alpha Vantage Brent fallback failed")
            return []

    async def _fetch_vix(self, client: httpx.AsyncClient) -> float | None:
        """Fetch the latest VIX level.

        Tries Yahoo Finance first; falls back to Alpha Vantage GLOBAL_QUOTE
        when Yahoo Finance fails or returns no price.
        Returns None if both sources fail.
        """
        # ── Yahoo Finance (primary) ───────────────────────────────────────
        try:
            yf_response = await client.get(
                _YAHOO_VIX_URL,
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=10.0,
            )
            yf_response.raise_for_status()
            yf_payload: dict = yf_response.json()  # type: ignore[type-arg]
            vix = _parse_yahoo_vix_payload(yf_payload)
            if vix is not None:
                return vix
            logger.warning("Yahoo Finance VIX payload had no price; using Alpha Vantage fallback")
        except Exception:
            logger.warning("Yahoo Finance VIX fetch failed; using Alpha Vantage fallback")

        # ── Alpha Vantage (fallback) ──────────────────────────────────────
        try:
            response = await client.get(
                _AV_GLOBAL_QUOTE_URL,
                params={"function": "GLOBAL_QUOTE", "symbol": "^VIX", "apikey": self._av_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: dict = response.json()  # type: ignore[type-arg]
            quote: dict = payload.get("Global Quote", {})  # type: ignore[type-arg]
            price_str: str = quote.get("05. price", "")
            if price_str:
                return float(price_str)
            logger.warning("Alpha Vantage VIX returned empty quote")
        except Exception:
            logger.exception("Alpha Vantage VIX fallback failed")
        return None
