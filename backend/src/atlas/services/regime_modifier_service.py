"""Regime Modifier service.

Fetches live Brent crude and VIX values from Polygon.io, retrieves the base
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
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.framework_score import FrameworkScoreResponse
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.framework_score_service import FrameworkScoreService
from atlas.services.ticker_service import TickerService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Polygon.io ticker symbols
# ---------------------------------------------------------------------------

# Brent Crude Oil continuous contract on Polygon.io commodities feed.
_BRENT_SYMBOL: Final[str] = "C:BCO"

# CBOE Volatility Index on Polygon.io indices feed.
_VIX_SYMBOL: Final[str] = "I:VIX"

# Polygon.io daily aggregates endpoint template.
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)

# Number of calendar days to look back when fetching recent daily bars.
# 10 calendar days guarantees at least 2 trading sessions even around holidays.
_BAR_LOOKBACK_DAYS: Final[int] = 10

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
      • Brent crude bars (last 2 trading days) from Polygon.io
      • VIX bars (last trading day) from Polygon.io
      • Framework Score for the ticker

    Also reads the ticker's ``position_value`` from the database to compute
    USD cash bounds.

    Parameters
    ----------
    polygon_api_key:
        Polygon.io API key (required for Brent and VIX data).
    alphavantage_api_key, transcript_api_key, benzinga_api_key,
    unusual_whales_api_key, sec_api_key:
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
        self._polygon_key = polygon_api_key
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
    ) -> RegimeModifierResponse:
        """Return the regime-adjusted score and cash guidance for ``ticker``.

        Runs three concurrent tasks:
          1. Fetch Brent crude daily bars (last 2 closes)
          2. Fetch VIX daily bar (last close)
          3. Compute Framework Score for the ticker
        """
        async with httpx.AsyncClient() as client:
            brent_task = self._fetch_bars(client, _BRENT_SYMBOL, num_bars=2)
            vix_task = self._fetch_bars(client, _VIX_SYMBOL, num_bars=1)
            fw_task = self._fw_service.compute_framework_score(ticker)

            brent_bars, vix_bars, fw_result = await asyncio.gather(
                brent_task,
                vix_task,
                fw_task,
                return_exceptions=True,
            )

        # ── Extract Brent price and consecutive-close flag ─────────────────
        brent_price: float | None = None
        brent_consecutive_below_95 = False
        if isinstance(brent_bars, list) and brent_bars:
            brent_price = float(brent_bars[-1]["c"])
            if len(brent_bars) >= 2:
                brent_consecutive_below_95 = all(
                    float(bar["c"]) < _RULE3_BRENT_CLEAR for bar in brent_bars[-2:]
                )
        else:
            logger.warning(
                "Brent crude fetch failed or returned no data",
                extra={"error": repr(brent_bars)},
            )

        # ── Extract VIX value ─────────────────────────────────────────────
        vix_value: float | None = None
        if isinstance(vix_bars, list) and vix_bars:
            vix_value = float(vix_bars[-1]["c"])
        else:
            logger.warning(
                "VIX fetch failed or returned no data",
                extra={"error": repr(vix_bars)},
            )

        # ── Extract base Framework Score ──────────────────────────────────
        if isinstance(fw_result, FrameworkScoreResponse):
            base_score = fw_result.final_score
        else:
            logger.error(
                "Framework Score fetch failed",
                extra={"ticker": ticker, "error": repr(fw_result)},
            )
            # Neutral fallback — cannot compute modifier without base score.
            base_score = 50

        # ── Look up position value from DB ────────────────────────────────
        position_value_usd: Decimal | None = None
        db_ticker = await self._ticker_service.get_by_ticker(ticker)
        if db_ticker is not None and db_ticker.position_value is not None:
            position_value_usd = db_ticker.position_value

        # ── Apply regime rules ────────────────────────────────────────────
        if brent_price is not None and vix_value is not None:
            rule = _determine_rule(
                active_war=active_war,
                brent_price=brent_price,
                vix_value=vix_value,
                brent_consecutive_below_95=brent_consecutive_below_95,
            )
        else:
            # Cannot determine regime without market data.
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
            min_cash_usd=min_cash_usd,
            max_cash_usd=max_cash_usd,
            output_text=output_text,
        )

    async def _fetch_bars(
        self,
        client: httpx.AsyncClient,
        polygon_ticker: str,
        num_bars: int,
    ) -> list[dict]:  # type: ignore[type-arg]
        """Fetch the most recent ``num_bars`` daily bars from Polygon.io.

        Returns an empty list on any error.
        """
        to_date = date.today()
        from_date = to_date - timedelta(days=_BAR_LOOKBACK_DAYS)
        url = _POLYGON_AGGS_URL.format(
            ticker=polygon_ticker,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        try:
            response = await client.get(
                url,
                params={"apiKey": self._polygon_key, "adjusted": "true", "sort": "asc"},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: dict = response.json()  # type: ignore[type-arg]
            results: list[dict] = payload.get("results", [])  # type: ignore[type-arg]
            return results[-num_bars:] if results else []
        except Exception:
            logger.exception(
                "Polygon.io bar fetch failed",
                extra={"ticker": polygon_ticker},
            )
            return []
