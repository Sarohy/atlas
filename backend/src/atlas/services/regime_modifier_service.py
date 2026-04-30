"""Regime Modifier service."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Final

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.framework_score import FrameworkScoreResponse
from atlas.schemas.regime_modifier import GeopoliticalState, RegimeModifierResponse
from atlas.services.framework_score_service import FrameworkScoreService
from atlas.services.ticker_service import TickerService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Market data endpoints
# ---------------------------------------------------------------------------

# Yahoo Finance chart API — VIX (^VIX). %5E is URL-encoded '^'.
# Returns JSON: {"chart": {"result": [{"meta": {"regularMarketPrice": 19.99, ...}}]}}
_YAHOO_VIX_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart/%5EVIX"

# Yahoo Finance chart API — Brent crude (BZ=F futures).
# Returns current price via meta.regularMarketPrice and previous close via
# meta.chartPreviousClose.
_YAHOO_BRENT_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart/BZ%3DF"

# Alpha Vantage — Brent crude (primary when Yahoo Finance is unreachable).
# Returns: {"data": [{"date": "...", "value": "..."}]}
_AV_BASE_URL: Final[str] = "https://www.alphavantage.co/query"

# Number of Brent daily closes to fetch (current + previous for consecutive check).
_BRENT_NUM_CLOSES: Final[int] = 2

# ---------------------------------------------------------------------------
# Rule 1 — Crisis Halt thresholds
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

# Brent in this inclusive range OR VIX in 24-35 triggers Rule 2.
_RULE2_BRENT_LOW: Final[float] = 95.0   # USD per barrel (inclusive)
_RULE2_BRENT_HIGH: Final[float] = 110.0  # USD per barrel (inclusive)
_RULE2_VIX_LOW: Final[float] = 24.0    # VIX level (inclusive)
_RULE2_VIX_HIGH: Final[float] = 35.0   # VIX level (inclusive)

# Score modifier for Rule 2 (standard).
_RULE2_SCORE_DELTA: Final[int] = -5

# Score modifier for Rule 2 CAUTION + ESCALATING geo — the ONLY special case
# in the entire 16-row regime table.  All other geo flags use the standard −5.
_RULE2_SCORE_DELTA_ESCALATING: Final[int] = -7  # CAUTION + ESCALATING

# Cash fraction bounds for Rule 2.
_RULE2_MIN_CASH_PCT: Final[float] = 0.25
_RULE2_MAX_CASH_PCT: Final[float] = 0.35

# ---------------------------------------------------------------------------
# Rule 3 — Soft Caution thresholds
# ---------------------------------------------------------------------------

# Brent must be below this for Rule 3 (strictly less than).
_RULE3_BRENT_THRESHOLD: Final[float] = 100.0  # USD per barrel

# VIX must be below this for Rule 3 (strictly less than).
_RULE3_VIX_THRESHOLD: Final[float] = 22.0

# Score modifier for Rule 3.
_RULE3_SCORE_DELTA: Final[int] = -3

# Cash fraction bounds for Rule 3.
_RULE3_MIN_CASH_PCT: Final[float] = 0.15
_RULE3_MAX_CASH_PCT: Final[float] = 0.25

# ---------------------------------------------------------------------------
# Rule 4 — Clear thresholds
# ---------------------------------------------------------------------------

# Brent must be strictly below this for Rule 4 (checked against last 2 closes).
_RULE4_BRENT_CLEAR: Final[float] = 95.0  # USD per barrel

# VIX must be strictly below this for Rule 4.
_RULE4_VIX_CLEAR: Final[float] = 24.0

# Score modifier for Rule 4.
_RULE4_SCORE_DELTA: Final[int] = 5

# Cash fraction bounds for Rule 4.
_RULE4_MIN_CASH_PCT: Final[float] = 0.10
_RULE4_MAX_CASH_PCT: Final[float] = 0.12

# ---------------------------------------------------------------------------
# Cash floor per regime (Section 14.1) — minimum portfolio cash fraction
# ---------------------------------------------------------------------------

_CASH_FLOOR_RULE1: Final[float] = 0.30  # CRISIS HALT: 30%+
_CASH_FLOOR_RULE2: Final[float] = 0.20  # CAUTION: 20%
_CASH_FLOOR_RULE3: Final[float] = 0.15  # SOFT CAUTION: 15% (v2.2)
_CASH_FLOOR_RULE4: Final[float] = 0.08  # CLEAR: 8% (10% first 2 weeks)

# ---------------------------------------------------------------------------
# Output text constants — multi-line strings match the spec verbatim
# ---------------------------------------------------------------------------

_OUTPUT_RULE1: Final[str] = "must stay in cash\ncannot be touched\nfor any trade"

_OUTPUT_RULE2: Final[str] = "must stay in cash"

_OUTPUT_RULE2_ESCALATING: Final[str] = "must stay in cash\nGEO PENALTY ACTIVE: CAUTION + ESCALATING"

_OUTPUT_RULE3: Final[str] = "reduce exposure\nmonitor conditions closely"

_OUTPUT_RULE4: Final[str] = "only this stays in cash\neverything else\ncan be deployed"

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
    brent_price: float,
    vix_value: float,
    brent_consecutive_below_95_count: int,
    geopolitical_state: GeopoliticalState = "NONE",
) -> int | None:
    """Return the highest-priority regime rule that fires, or None.

    REGIME is determined by Brent + VIX alone (Section 14.1, KEY RULE 2).
    The geopolitical_state parameter is accepted for API compatibility but
    does NOT gate which rule fires — it only affects the score modifier
    calculated by _calculate_modifier() within the CAUTION regime.

    Priority order (highest severity first):
        1 — CRISIS HALT:  Brent > $110  OR  VIX > 35
        2 — CAUTION:      Brent $95–$110 OR  VIX 24–35
        3 — SOFT CAUTION: Brent < $100 AND VIX < 22 AND streak < 2
        4 — CLEAR:        streak ≥ 2  AND  VIX < 24
        default           → 2 (CAUTION, −5)

    Pure function — no I/O.
    """
    # ── Rule 1 — CRISIS HALT (Brent OR VIX — any geo) ──────────────────────
    if brent_price > _RULE1_BRENT_THRESHOLD or vix_value > _RULE1_VIX_THRESHOLD:
        return 1

    # ── Rule 2 — CAUTION (Brent OR VIX — any geo) ──────────────────────────
    caution_market = (
        _RULE2_BRENT_LOW <= brent_price <= _RULE2_BRENT_HIGH
        or _RULE2_VIX_LOW <= vix_value <= _RULE2_VIX_HIGH
    )
    if caution_market:
        return 2

    # ── Rule 3 — SOFT CAUTION (Brent AND VIX — any geo) ────────────────────
    soft_caution_market = (
        brent_price < _RULE3_BRENT_THRESHOLD
        and brent_consecutive_below_95_count < _BRENT_NUM_CLOSES
        and vix_value < _RULE3_VIX_THRESHOLD
    )
    if soft_caution_market:
        return 3

    # ── Rule 4 — CLEAR (both required — any geo) ────────────────────────────
    clear_market = (
        brent_consecutive_below_95_count >= _BRENT_NUM_CLOSES
        and vix_value < _RULE4_VIX_CLEAR
    )
    if clear_market:
        return 4

    # Default — no specific rule matched; treat as CAUTION (−5).
    return 2


def _calculate_modifier(
    rule: int | None,
    geopolitical_state: GeopoliticalState,
) -> int:
    """Return the score modifier for the given regime rule and geo state.

    Per Section 14.1 KEY RULES:
    - CLEAR (4):        geo irrelevant → always +5
    - SOFT CAUTION (3): geo irrelevant → always −3
    - CRISIS HALT (1):  geo irrelevant → always −10
    - CAUTION (2):      ESCALATING → −7  (ONLY special case)
                        all others → −5
    - None (default):   → −5 (safe default)

    Pure function — no I/O.
    """
    if rule == 4:
        return _RULE4_SCORE_DELTA           # +5 — geo irrelevant
    if rule == 3:
        return _RULE3_SCORE_DELTA           # −3 — geo irrelevant
    if rule == 1:
        return _RULE1_SCORE_DELTA           # −10 — geo irrelevant
    if rule == 2:
        # ONLY special case: CAUTION + ESCALATING geo → −7
        if geopolitical_state == "ESCALATING":
            return _RULE2_SCORE_DELTA_ESCALATING  # −7
        return _RULE2_SCORE_DELTA           # −5
    return _RULE2_SCORE_DELTA               # safe default −5


def _get_brent_label(brent: float) -> str:
    """Return a human-readable Brent condition string with zone label."""
    if brent > _RULE1_BRENT_THRESHOLD:
        return f"${brent:.2f} — Above $110 (CRISIS trigger)"
    if _RULE2_BRENT_LOW <= brent <= _RULE2_BRENT_HIGH:
        return f"${brent:.2f} — $95-110 (CAUTION trigger)"
    if brent < _RULE4_BRENT_CLEAR:
        return f"${brent:.2f} — Below $95 (CLEAR zone)"
    return f"${brent:.2f}"


def _get_vix_label(vix: float) -> str:
    """Return a human-readable VIX condition string with zone label."""
    if vix > _RULE1_VIX_THRESHOLD:
        return f"{vix:.2f} — Above 35 (CRISIS trigger)"
    if _RULE2_VIX_LOW <= vix <= _RULE2_VIX_HIGH:
        return f"{vix:.2f} — 24-35 (CAUTION trigger)"
    if vix < _RULE3_VIX_THRESHOLD:
        return f"{vix:.2f} — Below 22 (SOFT CAUTION zone)"
    if vix < _RULE4_VIX_CLEAR:
        return f"{vix:.2f} — Below 24 (CLEAR zone)"
    return f"{vix:.2f}"


def _get_trigger_logic(rule: int | None) -> str:
    """Return the trigger logic description (OR vs AND) for a regime rule."""
    if rule in (1, 2):
        return "OR — either Brent or VIX triggers"
    return "AND — both Brent and VIX required"


def _get_modifier_reason(
    rule: int | None,
    geopolitical_state: GeopoliticalState,
) -> str:
    """Return a human-readable explanation of the modifier applied."""
    if rule == 4:
        return "CLEAR → +5 (geo flag ignored)"
    if rule == 3:
        return "SOFT CAUTION → −3 (geo flag ignored)"
    if rule == 1:
        return "CRISIS HALT → −10 (geo flag ignored)"
    if rule == 2:
        if geopolitical_state == "ESCALATING":
            return "CAUTION + Escalating geo → −7"
        geo_label = geopolitical_state.replace("_", " ")
        return f"CAUTION + {geo_label} → −5"
    return "Unknown → −5"


def _get_cash_floor(rule: int | None) -> float:
    """Return the minimum portfolio cash floor fraction for a regime rule.

    Per Section 14.1 cash floor column.
    """
    floors: dict[int | None, float] = {
        1: _CASH_FLOOR_RULE1,  # CRISIS HALT: 30%
        2: _CASH_FLOOR_RULE2,  # CAUTION: 20%
        3: _CASH_FLOOR_RULE3,  # SOFT CAUTION: 15%
        4: _CASH_FLOOR_RULE4,  # CLEAR: 8%
        None: _CASH_FLOOR_RULE2,  # default: 20%
    }
    return floors.get(rule, _CASH_FLOOR_RULE2)


def _count_consecutive_brent_closes_below_95(closes: list[float]) -> int:
    """Count consecutive most-recent Brent closes below the clear threshold."""
    streak = 0
    for close in closes[:_BRENT_NUM_CLOSES]:
        if close < _RULE4_BRENT_CLEAR:
            streak += 1
            continue
        break
    return streak


def _rule_name(rule: int | None) -> str:
    """Return the regime label for a rule number."""
    return {
        1: "CRISIS HALT",
        2: "CAUTION",
        3: "SOFT CAUTION",
        4: "CLEAR",
        None: "CAUTION",  # default regime
    }[rule]


def _derive_effective_regime(automatic_rule: int | None, geopolitical_state: GeopoliticalState) -> str:
    """Return the effective regime label.

    Regime is determined by market conditions alone (Section 14.1).
    Geo state is retained in the signature for API compatibility but
    does not change the regime label — it only affects the modifier.
    """
    return _rule_name(automatic_rule)


def _build_determination_text(
    automatic_regime: str,
    geopolitical_state: GeopoliticalState,
    brent_consecutive_below_95_count: int,
    modifier: int,
    special_case_active: bool,
) -> str:
    """Build a short explanation of how the regime and modifier were determined."""
    geo_label = geopolitical_state.replace("_", " ")
    base = (
        f"{automatic_regime} regime from Brent/VIX data. "
        f"Brent streak below $95: {brent_consecutive_below_95_count}. "
        f"Geo flag: {geo_label}. Modifier: {modifier:+d}."
    )
    if special_case_active:
        return base + " GEO PENALTY ACTIVE: CAUTION + ESCALATING geo → −7."
    return base


def _compute_regime_output(
    rule: int | None,
    base_score: int,
    position_value_usd: Decimal | None,
    geopolitical_state: GeopoliticalState = "NONE",
) -> tuple[int, float, float, Decimal | None, Decimal | None, str]:
    """Compute the adjusted score, cash bounds, and output text for a rule.

    Returns:
        (adjusted_score, min_cash_pct, max_cash_pct,
         min_cash_usd, max_cash_usd, output_text)

    ``position_value_usd`` is the ticker's portfolio position value in USD.
    When None (ticker not in portfolio) the USD cash amounts are also None.

    Uses _calculate_modifier() so CAUTION + ESCALATING yields −7.

    Pure function — no I/O.
    """
    if rule == 1:
        min_pct = _RULE1_MIN_CASH_PCT
        max_pct = _RULE1_MAX_CASH_PCT
        text = _OUTPUT_RULE1
    elif rule == 2:
        min_pct = _RULE2_MIN_CASH_PCT
        max_pct = _RULE2_MAX_CASH_PCT
        text = (
            _OUTPUT_RULE2_ESCALATING
            if geopolitical_state == "ESCALATING"
            else _OUTPUT_RULE2
        )
    elif rule == 3:
        min_pct = _RULE3_MIN_CASH_PCT
        max_pct = _RULE3_MAX_CASH_PCT
        text = _OUTPUT_RULE3
    elif rule == 4:
        min_pct = _RULE4_MIN_CASH_PCT
        max_pct = _RULE4_MAX_CASH_PCT
        text = _OUTPUT_RULE4
    else:
        # No regime rule triggered — score and cash guidance unchanged.
        adjusted = base_score
        return adjusted, 0.0, 0.0, None, None, _OUTPUT_NONE

    delta = _calculate_modifier(rule, geopolitical_state)
    adjusted_score = max(0, min(100, base_score + delta))

    min_cash_usd: Decimal | None = None
    max_cash_usd: Decimal | None = None
    if position_value_usd is not None:
        min_cash_usd = (position_value_usd * Decimal(str(min_pct))).quantize(Decimal("0.01"))
        max_cash_usd = (position_value_usd * Decimal(str(max_pct))).quantize(Decimal("0.01"))

    return adjusted_score, min_pct, max_pct, min_cash_usd, max_cash_usd, text


# ---------------------------------------------------------------------------
# In-memory geo flag store (swap for Redis in production).
# Key: geo_flag:current — shared between Framework 2 (writes) and
# Framework 4 (reads) so signal 5 detection is self-contained on the backend.
# Default: "NONE" when no state has been recorded.
# ---------------------------------------------------------------------------

_geo_flag_current: str = "NONE"


def get_geo_flag_current() -> str:
    """Read the current geopolitical flag from the in-memory store.

    Returns ``"NONE"`` by default when no flag has been set.
    Pure read — no side effects.
    """
    return _geo_flag_current


def set_geo_flag_current(state: str) -> None:
    """Write the current geopolitical flag to the in-memory store.

    Called by the regime modifier endpoint whenever a request is processed.
    """
    global _geo_flag_current
    _geo_flag_current = state.strip().upper()


def reset_geo_flag_current() -> None:
    """Reset the geo flag store to ``"NONE"``.

    Call between tests to prevent state leakage.
    """
    global _geo_flag_current
    _geo_flag_current = "NONE"


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
        geopolitical_state: GeopoliticalState,
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
        brent_consecutive_below_95_count = 0
        if isinstance(brent_closes, list) and brent_closes:
            brent_price = brent_closes[0]
            brent_consecutive_below_95_count = _count_consecutive_brent_closes_below_95(brent_closes)
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
        if brent_price is not None and vix_value is not None:
            rule = _determine_rule(
                brent_price=brent_price,
                vix_value=vix_value,
                brent_consecutive_below_95_count=brent_consecutive_below_95_count,
                geopolitical_state=geopolitical_state,
            )
        else:
            rule = None

        # ── F17 geo flag gate: block CLEAR regime when ACTIVE geo risk ────
        # Framework 17 is the ONLY source for this gate.
        # Only applies when rule 4 (CLEAR) was determined.
        if rule == 4:
            from atlas.services.framework17_service import get_f17_clear_blocked

            if get_f17_clear_blocked():
                # Downgrade CLEAR → SOFT CAUTION when geo flag is ACTIVE.
                rule = 3
                logger.info(
                    "F2: CLEAR regime blocked by active F17 geopolitical flag; "
                    "downgraded to SOFT CAUTION."
                )

        (
            adjusted_score,
            min_cash_pct,
            max_cash_pct,
            min_cash_usd,
            max_cash_usd,
            output_text,
        ) = _compute_regime_output(rule, base_score, position_value_usd, geopolitical_state)

        modifier = _calculate_modifier(rule, geopolitical_state)
        special_case_active = rule == 2 and geopolitical_state == "ESCALATING"
        automatic_regime = _rule_name(rule)
        effective_regime = _derive_effective_regime(rule, geopolitical_state)
        determination_text = _build_determination_text(
            automatic_regime=automatic_regime,
            geopolitical_state=geopolitical_state,
            brent_consecutive_below_95_count=brent_consecutive_below_95_count,
            modifier=modifier,
            special_case_active=special_case_active,
        )

        brent_condition = _get_brent_label(brent_price) if brent_price is not None else "N/A"
        vix_condition = _get_vix_label(vix_value) if vix_value is not None else "N/A"
        trigger_logic = _get_trigger_logic(rule)
        modifier_reason = _get_modifier_reason(rule, geopolitical_state)
        cash_floor_pct = _get_cash_floor(rule)

        # Persist the geo flag so Framework 4 can read it without needing
        # the frontend to re-send the value on the tranche-sizing request.
        set_geo_flag_current(str(geopolitical_state))

        return RegimeModifierResponse(
            ticker=ticker,
            geopolitical_state=geopolitical_state,
            brent_price=brent_price,
            vix_value=vix_value,
            brent_consecutive_below_95_count=brent_consecutive_below_95_count,
            base_score=base_score,
            adjusted_score=adjusted_score,
            rule_triggered=rule,
            rule=automatic_regime,
            effective_regime=effective_regime,
            modifier=modifier,
            min_cash_pct=min_cash_pct,
            max_cash_pct=max_cash_pct,
            min_cash_usd=float(min_cash_usd) if min_cash_usd is not None else None,
            max_cash_usd=float(max_cash_usd) if max_cash_usd is not None else None,
            output_text=output_text,
            determination_text=determination_text,
            brent_condition=brent_condition,
            vix_condition=vix_condition,
            geo_condition=geopolitical_state,
            trigger_logic=trigger_logic,
            modifier_reason=modifier_reason,
            special_case_active=special_case_active,
            cash_floor_pct=cash_floor_pct,
        )

    async def _fetch_brent(self, client: httpx.AsyncClient) -> list[float]:
        """Fetch the two most recent Brent crude closes from Yahoo Finance (BZ=F).

        Returns a list of up to 2 floats in descending date order (most recent
        first). Returns [] if Yahoo Finance is unreachable or returns no price.
        """
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
            logger.warning("Brent crude: Yahoo Finance returned no price")
        except Exception:
            logger.warning("Brent crude: Yahoo Finance fetch failed")
        return []

    async def _fetch_vix(self, client: httpx.AsyncClient) -> float | None:
        """Fetch the latest VIX from Yahoo Finance (^VIX).

        Returns None if Yahoo Finance is unreachable or returns no price.
        """
        try:
            yf_response = await client.get(
                _YAHOO_VIX_URL,
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=10.0,
            )
            yf_response.raise_for_status()
            vix = _parse_yahoo_vix_payload(yf_response.json())
            if vix is not None:
                return vix
            logger.warning("VIX: Yahoo Finance returned no price")
        except Exception:
            logger.warning("VIX: Yahoo Finance fetch failed")
        return None
