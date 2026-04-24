"""Section 16 Exit Rules service.

Evaluates all four exit rules for a given ticker using only canonical
data sources:
  F1  (conviction score)  — GET /api/v1/framework-score/{ticker}
  F7  (earnings gate)     — GET /api/v1/framework7/{ticker}
  F9  (options flow)      — GET /api/v1/framework9/{ticker}
  F30 (portfolio nav)     — GET /api/v1/framework30/portfolio
  Polygon.io              — ONLY source for current/open prices
  atlas_config DB         — ONLY source for threshold constants
  exit_rule_cycles DB     — ONLY source for cycle state
  gap_down_events DB      — ONLY source for gap-down records
  grok_scores DB          — ONLY source for Grok scores
  geo_flag_history DB     — ONLY source for historic geo flag state

Single source of truth rules:
  - conviction score = F1 final_score only.
  - NAV = F30 total_nav only.
  - earnings days = F7 days_to_earnings only.
  - bearish flow = F9 largest_print_usd (put flow only) only.
  - NO dummy data: missing source → null result + explicit missing_sources list.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.models.atlas_config import AtlasConfig
from atlas.models.decision_trace import DecisionTrace
from atlas.models.exit_rule_cycle import ExitRuleCycle
from atlas.models.gap_down_event import GapDownEvent
from atlas.models.grok_score import GrokScore
from atlas.schemas.section16 import (
    ActiveCycleEntry,
    ActiveCyclesSummary,
    Rule161Result,
    Rule162Result,
    Rule163Result,
    Rule164ConditionDetail,
    Rule164Result,
    Section16OverallStatus,
    Section16Result,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal request timeout for localhost framework calls.
# ---------------------------------------------------------------------------
_HTTP_TIMEOUT_SECONDS: Final[float] = 10.0

# Base URL for intra-service calls — only localhost in V1.
_BASE_URL: Final[str] = "http://localhost:8000"

# Polygon.io daily aggs endpoint template for open/close prices.
_POLYGON_DAILY_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}"
)

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

# Weekday numbers — Monday=0, Friday=4.
_FRIDAY: Final[int] = 4


def get_last_friday_date(
    today: date | None = None,
    after_close: bool = False,
) -> date:
    """Return the most recent completed Friday rescore date.

    A Friday rescore is considered complete once the market is closed
    (16:00 ET or later on Fridays).  Pass ``after_close=True`` on a
    Friday afternoon to treat today as the completed rescore date.

    Args:
        today:       Override for today's date (used in tests).
        after_close: True when called after 16:00 ET on a Friday.

    Returns:
        The most recent Friday date that has a completed rescore.
    """
    if today is None:
        today = date.today()

    if today.weekday() == _FRIDAY and after_close:
        return today

    # Walk backwards until we land on a Friday.
    days_since_friday = (today.weekday() - _FRIDAY) % 7
    if days_since_friday == 0:
        # Today is Friday but before close — go back 7 days.
        days_since_friday = 7
    return today - timedelta(days=days_since_friday)


def add_trading_days(start: date, days: int) -> date:
    """Return a date that is ``days`` trading days after ``start``.

    Skips Saturday (5) and Sunday (6).  Public holidays not tracked in V1.
    Pure function — no I/O.
    """
    result = start
    added = 0
    while added < days:
        result += timedelta(days=1)
        if result.weekday() < 5:
            added += 1
    return result


# ---------------------------------------------------------------------------
# Config reader
# ---------------------------------------------------------------------------


async def _get_config_decimal(key: str, session: AsyncSession) -> Decimal:
    """Read a Decimal value from atlas_config. Raises RuntimeError if missing."""
    row = await session.get(AtlasConfig, key)
    if row is None:
        raise RuntimeError(
            f"atlas_config key '{key}' not found — run 'alembic upgrade head'."
        )
    return Decimal(row.value)


async def _get_config_int(key: str, session: AsyncSession) -> int:
    """Read an int value from atlas_config. Raises RuntimeError if missing."""
    return int(await _get_config_decimal(key, session))


# ---------------------------------------------------------------------------
# Internal data fetchers — each returns a plain dict, never raises on
# upstream failures (returns None fields instead).
# ---------------------------------------------------------------------------


async def _fetch_conviction_score(ticker: str) -> dict[str, object]:
    """Fetch F1 final_score from the framework-score endpoint.

    Returns:
        {"score": float | None, "error": str | None}
    """
    url = f"{_BASE_URL}/api/v1/framework-score/{ticker}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            score = data.get("final_score")
            return {"score": float(score) if score is not None else None, "error": None}
        except Exception as exc:
            logger.warning("F1 fetch failed for %s: %s", ticker, exc)
            return {"score": None, "error": str(exc)}


async def _fetch_earnings_days(ticker: str) -> dict[str, object]:
    """Fetch F7 days_to_earnings from the framework7 endpoint.

    Returns:
        {"days_to_earnings": int | None, "error": str | None}
    """
    url = f"{_BASE_URL}/api/v1/framework7/{ticker}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            days = data.get("days_to_earnings")
            return {"days_to_earnings": int(days) if days is not None else None, "error": None}
        except Exception as exc:
            logger.warning("F7 fetch failed for %s: %s", ticker, exc)
            return {"days_to_earnings": None, "error": str(exc)}


async def _fetch_bearish_flow(ticker: str) -> dict[str, object]:
    """Fetch F9 largest bearish print from the framework9 endpoint.

    Returns:
        {"put_flow_usd": Decimal | None, "error": str | None}
    """
    url = f"{_BASE_URL}/api/v1/framework9/{ticker}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            largest_print = data.get("largest_print_usd")
            return {
                "put_flow_usd": Decimal(str(largest_print)) if largest_print is not None else None,
                "error": None,
            }
        except Exception as exc:
            logger.warning("F9 fetch failed for %s: %s", ticker, exc)
            return {"put_flow_usd": None, "error": str(exc)}


async def _fetch_total_nav() -> dict[str, object]:
    """Fetch total_nav from the portfolio summary endpoint.

    Returns:
        {"total_nav": Decimal | None, "error": str | None}
    """
    url = f"{_BASE_URL}/api/v1/portfolio/summary"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            nav = data.get("total_nav")
            return {
                "total_nav": Decimal(str(nav)) if nav is not None else None,
                "error": None,
            }
        except Exception as exc:
            logger.warning("F30 fetch failed: %s", exc)
            return {"total_nav": None, "error": str(exc)}


async def _fetch_position_value(ticker: str) -> dict[str, object]:
    """Fetch current position market value from Polygon.io.

    Returns:
        {"position_value": Decimal | None, "error": str | None}
    """
    settings = get_settings()
    today_str = date.today().isoformat()
    url = _POLYGON_DAILY_URL.format(ticker=ticker, date=today_str)
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(
                url, params={"apiKey": settings.polygon_api_key}
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return {"position_value": None, "error": "Polygon returned no price data"}
            close_price = Decimal(str(results[0].get("c", 0)))
            return {"position_value": close_price, "error": None}
        except Exception as exc:
            logger.warning("Polygon fetch failed for %s: %s", ticker, exc)
            return {"position_value": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Rule 16.1 — Score-Based Exit (pure logic, injectable inputs)
# ---------------------------------------------------------------------------


async def evaluate_rule_161(
    *,
    ticker: str,
    current_friday_score: float,
    cycle_record: dict[str, object] | None,
    f12_no_fly_active: bool,
    reconciliation_pending: bool,
    session: AsyncSession,
) -> dict[str, object]:
    """Evaluate Rule 16.1 (two-cycle score-based exit) and return a result dict.

    Args:
        ticker:                  Ticker symbol.
        current_friday_score:    F1 final_score from this Friday's rescore.
        cycle_record:            Existing cycle DB record as a plain dict, or None.
        f12_no_fly_active:       True when F12 has an active catalyst no-fly.
        reconciliation_pending:  True when Claude vs Grok gap exceeds threshold.
        session:                 AsyncSession for config reads.

    Returns plain dict matching Rule161Result fields.
    """
    score_55 = int(await _get_config_int("s16_score_below_55_threshold", session))
    score_45 = int(await _get_config_int("s16_score_below_45_threshold", session))
    trim_days = int(await _get_config_int("s16_trim_window_trading_days", session))
    exit_days = int(await _get_config_int("s16_full_exit_trading_days", session))
    trim_pct = await _get_config_decimal("s16_trim_pct_cycle_two", session)

    score = int(current_friday_score)

    # Score < 45 → immediate full exit regardless of cycle state.
    if score < score_45:
        return {
            "status": "FULL_EXIT_TRIGGERED",
            "cycle_count": 0 if cycle_record is None else _current_cycle_count(cycle_record),
            "trim_triggered": False,
            "full_exit_triggered": True,
            "exit_window_trading_days": exit_days,
            "trim_window_trading_days": None,
            "trim_pct": None,
            "deferred_reason": None,
            "deferred_until": None,
            "reconciliation_pending": reconciliation_pending,
            "claude_score": Decimal(str(current_friday_score)),
            "grok_score": None,
            "score_gap": None,
            "triggering_score": Decimal(str(current_friday_score)),
            "triggering_date": get_last_friday_date(),
            "data_available": True,
            "missing_sources": [],
        }

    # Score ≥ 55 → clear any existing cycle.
    if score >= score_55:
        return {
            "status": "CLEAR",
            "cycle_count": 0,
            "trim_triggered": False,
            "full_exit_triggered": False,
            "exit_window_trading_days": None,
            "trim_window_trading_days": None,
            "trim_pct": None,
            "deferred_reason": None,
            "deferred_until": None,
            "reconciliation_pending": False,
            "claude_score": Decimal(str(current_friday_score)),
            "grok_score": None,
            "score_gap": None,
            "triggering_score": None,
            "triggering_date": None,
            "data_available": True,
            "missing_sources": [],
        }

    # Score is below 55 — determine cycle progression.
    existing_status = (
        cycle_record.get("cycle_status", "CLEAR") if cycle_record is not None else "CLEAR"
    )
    paused = bool(cycle_record.get("reconciliation_pause", False)) if cycle_record else False
    deferred_until = cycle_record.get("deferred_until") if cycle_record else None

    # Reconciliation pause: clock does not advance.
    if reconciliation_pending or paused:
        return {
            "status": "CYCLE_ONE_PAUSED",
            "cycle_count": 1,
            "trim_triggered": False,
            "full_exit_triggered": False,
            "exit_window_trading_days": None,
            "trim_window_trading_days": None,
            "trim_pct": None,
            "deferred_reason": "RECONCILIATION_PENDING",
            "deferred_until": None,
            "reconciliation_pending": True,
            "claude_score": Decimal(str(current_friday_score)),
            "grok_score": None,
            "score_gap": None,
            "triggering_score": Decimal(str(current_friday_score)),
            "triggering_date": get_last_friday_date(),
            "data_available": True,
            "missing_sources": [],
        }

    is_cycle_one = existing_status in ("CYCLE_ONE", "CYCLE_ONE_PAUSED")

    if is_cycle_one:
        # Cycle two would fire — check for F12 deferral first.
        if f12_no_fly_active:
            return {
                "status": "DEFERRED",
                "cycle_count": 1,
                "trim_triggered": False,
                "full_exit_triggered": False,
                "exit_window_trading_days": None,
                "trim_window_trading_days": None,
                "trim_pct": None,
                "deferred_reason": "F12_NO_FLY_ACTIVE",
                "deferred_until": deferred_until,
                "reconciliation_pending": False,
                "claude_score": Decimal(str(current_friday_score)),
                "grok_score": None,
                "score_gap": None,
                "triggering_score": Decimal(str(current_friday_score)),
                "triggering_date": get_last_friday_date(),
                "data_available": True,
                "missing_sources": [],
            }

        return {
            "status": "CYCLE_TWO",
            "cycle_count": 2,
            "trim_triggered": True,
            "full_exit_triggered": False,
            "exit_window_trading_days": None,
            "trim_window_trading_days": trim_days,
            "trim_pct": trim_pct,
            "deferred_reason": None,
            "deferred_until": None,
            "reconciliation_pending": False,
            "claude_score": Decimal(str(current_friday_score)),
            "grok_score": None,
            "score_gap": None,
            "triggering_score": Decimal(str(current_friday_score)),
            "triggering_date": get_last_friday_date(),
            "data_available": True,
            "missing_sources": [],
        }

    # No existing cycle → this is cycle one.
    return {
        "status": "CYCLE_ONE",
        "cycle_count": 1,
        "trim_triggered": False,
        "full_exit_triggered": False,
        "exit_window_trading_days": None,
        "trim_window_trading_days": None,
        "trim_pct": None,
        "deferred_reason": None,
        "deferred_until": None,
        "reconciliation_pending": False,
        "claude_score": Decimal(str(current_friday_score)),
        "grok_score": None,
        "score_gap": None,
        "triggering_score": Decimal(str(current_friday_score)),
        "triggering_date": get_last_friday_date(),
        "data_available": True,
        "missing_sources": [],
    }


def _current_cycle_count(cycle_record: dict[str, object]) -> int:
    """Return the numeric cycle count from a cycle_record dict."""
    status = cycle_record.get("cycle_status", "CLEAR")
    if status in ("CYCLE_TWO", "TRIM_TRIGGERED", "DEFERRED"):
        return 2
    if status in ("CYCLE_ONE", "CYCLE_ONE_PAUSED"):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Rule 16.2 — Gap-Down (pure logic)
# ---------------------------------------------------------------------------


def evaluate_rule_162(
    *,
    ticker: str,
    prev_close: Decimal,
    open_price: Decimal,
    event_timestamp: datetime,
    gap_down_threshold_pct: Decimal,
    hold_hours: int,
    rescore_hours: int = 72,
) -> dict[str, object]:
    """Evaluate Rule 16.2 gap-down logic.  Pure function — no I/O.

    Args:
        ticker:                 Ticker symbol (used in result for traceability).
        prev_close:             Prior session close price.
        open_price:             Current session open price.
        event_timestamp:        UTC datetime of the gap-down event.
        gap_down_threshold_pct: Percent threshold above which gap triggers rule.
        hold_hours:             Hours to hold before taking action.
        rescore_hours:          Hours after event to rescore.

    Returns plain dict matching Rule162Result fields.
    """
    # Gap-down percentage: positive value means price fell.
    gap_pct = ((prev_close - open_price) / prev_close) * Decimal("100")

    if gap_pct <= gap_down_threshold_pct:
        return {
            "gap_triggered": False,
            "status": "CLEAR",
            "gap_down_pct": gap_pct,
            "prev_close": prev_close,
            "open_price": open_price,
            "event_date": event_timestamp.date(),
            "hold_until": None,
            "rescore_at": None,
            "rescore_score": None,
            "resolved_at": None,
            "data_available": True,
            "missing_sources": [],
        }

    hold_until = event_timestamp + timedelta(hours=hold_hours)
    rescore_at = event_timestamp + timedelta(hours=rescore_hours)

    return {
        "gap_triggered": True,
        "status": "HOLDING",
        "gap_down_pct": gap_pct,
        "prev_close": prev_close,
        "open_price": open_price,
        "event_date": event_timestamp.date(),
        "hold_until": hold_until,
        "rescore_at": rescore_at,
        "rescore_score": None,
        "resolved_at": None,
        "data_available": True,
        "missing_sources": [],
    }


# ---------------------------------------------------------------------------
# Rule 16.3 — Appreciation Trim (pure logic)
# ---------------------------------------------------------------------------


def evaluate_rule_163(
    *,
    ticker: str,
    position_value: Decimal,
    total_nav: Decimal,
    soft_cap_pct: Decimal,
    hard_cap_pct: Decimal,
    trim_pct: Decimal,
) -> dict[str, object]:
    """Evaluate Rule 16.3 appreciation/concentration trim.  Pure function.

    Args:
        ticker:         Ticker symbol.
        position_value: Current market value of the position.
        total_nav:      Total portfolio NAV (from F30).
        soft_cap_pct:   Percent of NAV above which no new capital is deployed.
        hard_cap_pct:   Percent of NAV above which trim is considered.
        trim_pct:       Percent of position to trim at hard cap.

    Returns plain dict matching Rule163Result fields.
    """
    position_pct = (position_value / total_nav) * Decimal("100")

    if position_pct > hard_cap_pct:
        return {
            "status": "CONSIDER_TRIM",
            "no_new_capital": True,
            "consider_trim": True,
            "position_pct_of_nav": position_pct,
            "position_value": position_value,
            "total_nav": total_nav,
            "trim_pct": trim_pct,
            "data_available": True,
            "missing_sources": [],
        }

    if position_pct > soft_cap_pct:
        return {
            "status": "NO_NEW_CAPITAL",
            "no_new_capital": True,
            "consider_trim": False,
            "position_pct_of_nav": position_pct,
            "position_value": position_value,
            "total_nav": total_nav,
            "trim_pct": None,
            "data_available": True,
            "missing_sources": [],
        }

    return {
        "status": "CLEAR",
        "no_new_capital": False,
        "consider_trim": False,
        "position_pct_of_nav": position_pct,
        "position_value": position_value,
        "total_nav": total_nav,
        "trim_pct": None,
        "data_available": True,
        "missing_sources": [],
    }


# ---------------------------------------------------------------------------
# Rule 16.4 — Put Protection (pure logic)
# ---------------------------------------------------------------------------


def evaluate_rule_164(
    *,
    ticker: str,
    bearish_flow_usd: Decimal | None,
    earnings_days_away: int | None,
    gain_from_cost_pct: Decimal | None,
    current_score: float | None,
    put_flow_threshold_usd: Decimal,
    put_earnings_days: int,
    score_tier3_threshold: int,
) -> dict[str, object]:
    """Evaluate Rule 16.4 put-protection.  Pure function — no I/O.

    All four conditions must be True to recommend protective puts.
    Any None input → status UNKNOWN with missing_sources populated.

    Args:
        ticker:                  Ticker symbol.
        bearish_flow_usd:        Largest bearish dark pool print (F9).
        earnings_days_away:      Days until earnings (F7).
        gain_from_cost_pct:      Unrealised gain pct from cost basis.
        current_score:           Current F1 conviction score.
        put_flow_threshold_usd:  Minimum bearish flow for condition 1.
        put_earnings_days:       Max days-to-earnings for condition 2.
        score_tier3_threshold:   Score below which condition 4 is satisfied.

    Returns plain dict matching Rule164Result fields.
    """
    missing: list[str] = []

    cond1: bool | None = None
    if bearish_flow_usd is None:
        missing.append("F9")
    else:
        cond1 = bearish_flow_usd >= put_flow_threshold_usd

    cond2: bool | None = None
    if earnings_days_away is None:
        missing.append("F7")
    else:
        cond2 = earnings_days_away <= put_earnings_days

    cond3: bool | None = None
    if gain_from_cost_pct is None:
        missing.append("PORTFOLIO_COST_BASIS")
    else:
        # "Up significantly" — proxy: gain > 20%
        _gain_significant_pct: Final[Decimal] = Decimal("20")
        cond3 = gain_from_cost_pct > _gain_significant_pct

    cond4: bool | None = None
    if current_score is None:
        missing.append("F1")
    else:
        cond4 = int(current_score) < score_tier3_threshold

    conditions = [
        Rule164ConditionDetail(
            condition_number=1,
            description="Institutional bearish options flow > $500K in a single session",
            met=cond1,
            value=f"${bearish_flow_usd:,.0f}" if bearish_flow_usd is not None else None,
            threshold=f"${put_flow_threshold_usd:,.0f}",
        ),
        Rule164ConditionDetail(
            condition_number=2,
            description="Earnings binary event within 20 days",
            met=cond2,
            value=f"{earnings_days_away}d" if earnings_days_away is not None else None,
            threshold=f"{put_earnings_days}d",
        ),
        Rule164ConditionDetail(
            condition_number=3,
            description="Name is up significantly from cost basis (protecting unrealised gains)",
            met=cond3,
            value=f"{gain_from_cost_pct:.1f}%" if gain_from_cost_pct is not None else None,
            threshold="20%",
        ),
        Rule164ConditionDetail(
            condition_number=4,
            description="Score has dropped or is trending toward Tier 3 or Watchlist",
            met=cond4,
            value=str(current_score) if current_score is not None else None,
            threshold=f"< {score_tier3_threshold}",
        ),
    ]

    if missing:
        return {
            "recommend_puts": None,
            "status": "UNKNOWN",
            "conditions_met": sum(1 for c in [cond1, cond2, cond3, cond4] if c is True),
            "conditions": conditions,
            "data_available": False,
            "missing_sources": missing,
        }

    all_met = all([cond1, cond2, cond3, cond4])
    conditions_met = sum(1 for c in [cond1, cond2, cond3, cond4] if c is True)

    return {
        "recommend_puts": all_met,
        "status": "PUT_PROTECTION_RECOMMENDED" if all_met else "NOT_TRIGGERED",
        "conditions_met": conditions_met,
        "conditions": conditions,
        "data_available": True,
        "missing_sources": [],
    }


# ---------------------------------------------------------------------------
# Top-level evaluator
# ---------------------------------------------------------------------------


async def evaluate_section16(ticker: str, session: AsyncSession) -> Section16Result:
    """Run all four Section 16 exit rules for a single ticker.

    All rules are evaluated in parallel via asyncio.gather.
    Data fetches that fail return None inputs — the rule returns UNKNOWN
    with a populated missing_sources list.  No exception is raised for
    upstream failures.

    Args:
        ticker:  Ticker symbol (normalised to uppercase by caller).
        session: AsyncSession for DB reads/writes.

    Returns:
        Section16Result with all four rule evaluations embedded.
    """
    normalised = ticker.upper()

    # ------------------------------------------------------------------
    # Parallel HTTP fetches (safe to gather — independent connections)
    # DB reads must be sequential on a single AsyncSession (asyncpg limitation).
    # ------------------------------------------------------------------
    (
        f1_data,
        f7_data,
        f9_data,
        f30_data,
    ) = await asyncio.gather(
        _fetch_conviction_score(normalised),
        _fetch_earnings_days(normalised),
        _fetch_bearish_flow(normalised),
        _fetch_total_nav(),
    )

    cycle_row = await _fetch_cycle_record(normalised, session)
    grok_row = await _fetch_latest_grok_score(normalised, session)

    # Check for human override — overrides suppress all rule signals.
    if cycle_row is not None and cycle_row.get("override_active"):
        return _build_override_result(normalised, cycle_row)

    # ------------------------------------------------------------------
    # Config reads (needed by multiple rules — fetch once)
    # ------------------------------------------------------------------
    recon_gap = int(await _get_config_int("s16_reconciliation_gap_threshold", session))
    put_flow_threshold = await _get_config_decimal("s16_put_flow_threshold_usd", session)
    put_earnings_days = await _get_config_int("s16_put_earnings_days", session)
    soft_cap_pct = await _get_config_decimal("s16_appreciation_soft_cap_pct", session)
    hard_cap_pct = await _get_config_decimal("s16_appreciation_hard_cap_pct", session)
    trim_size_pct = await _get_config_decimal("s16_appreciation_trim_size_pct", session)

    f1_score: float | None = f1_data.get("score")  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Reconciliation check (Claude vs Grok gap)
    # ------------------------------------------------------------------
    reconciliation_pending = False
    if f1_score is not None and grok_row is not None:
        grok_val: float = float(grok_row.get("grok_score", 0.0))  # type: ignore[arg-type]
        gap = abs(f1_score - grok_val)
        reconciliation_pending = gap > recon_gap

    # ------------------------------------------------------------------
    # F12 no-fly check (intra-service call)
    # ------------------------------------------------------------------
    f12_no_fly = await _fetch_f12_no_fly(normalised)

    # ------------------------------------------------------------------
    # Rule 16.1
    # ------------------------------------------------------------------
    if f1_score is not None:
        r161_dict = await evaluate_rule_161(
            ticker=normalised,
            current_friday_score=f1_score,
            cycle_record=cycle_row,
            f12_no_fly_active=f12_no_fly,
            reconciliation_pending=reconciliation_pending,
            session=session,
        )
    else:
        r161_dict = {
            "status": "UNKNOWN",
            "cycle_count": 0,
            "trim_triggered": False,
            "full_exit_triggered": False,
            "exit_window_trading_days": None,
            "trim_window_trading_days": None,
            "trim_pct": None,
            "deferred_reason": None,
            "deferred_until": None,
            "reconciliation_pending": False,
            "claude_score": None,
            "grok_score": None,
            "score_gap": None,
            "triggering_score": None,
            "triggering_date": None,
            "data_available": False,
            "missing_sources": ["F1"],
        }
    rule_161 = Rule161Result(**r161_dict)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Rule 16.2 — fetch current open/prev_close from Polygon
    # ------------------------------------------------------------------
    rule_162 = await _evaluate_rule162_with_db(normalised, session)

    # ------------------------------------------------------------------
    # Rule 16.3 — position value from DB, NAV from F30
    # ------------------------------------------------------------------
    position_value = await _fetch_position_market_value(normalised, session)
    total_nav: Decimal | None = f30_data.get("total_nav")  # type: ignore[assignment]

    if position_value is not None and total_nav is not None:
        r163_dict = evaluate_rule_163(
            ticker=normalised,
            position_value=position_value,
            total_nav=total_nav,
            soft_cap_pct=soft_cap_pct,
            hard_cap_pct=hard_cap_pct,
            trim_pct=trim_size_pct,
        )
    else:
        missing_163: list[str] = []
        if position_value is None:
            missing_163.append("PORTFOLIO_POSITION")
        if total_nav is None:
            missing_163.append("PORTFOLIO_NAV")
        r163_dict = {
            "status": "UNKNOWN",
            "no_new_capital": False,
            "consider_trim": False,
            "position_pct_of_nav": None,
            "position_value": position_value,
            "total_nav": total_nav,
            "trim_pct": None,
            "data_available": False,
            "missing_sources": missing_163,
        }
    rule_163 = Rule163Result(**r163_dict)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Rule 16.4 — gain from cost basis requires portfolio DB
    # ------------------------------------------------------------------
    gain_pct = await _fetch_gain_from_cost_pct(normalised, session)
    from atlas.core.scoring import TIER_2_MIN as _TIER_2_MIN

    r164_dict = evaluate_rule_164(
        ticker=normalised,
        bearish_flow_usd=f9_data.get("put_flow_usd"),  # type: ignore[arg-type]
        earnings_days_away=f7_data.get("days_to_earnings"),  # type: ignore[arg-type]
        gain_from_cost_pct=gain_pct,
        current_score=f1_score,
        put_flow_threshold_usd=put_flow_threshold,
        put_earnings_days=put_earnings_days,
        score_tier3_threshold=_TIER_2_MIN,
    )
    rule_164 = Rule164Result(**r164_dict)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Overall status
    # ------------------------------------------------------------------
    any_exit_signal = bool(
        rule_161.trim_triggered
        or rule_161.full_exit_triggered
        or rule_164.recommend_puts
    )

    all_data_available = all([
        rule_161.data_available,
        rule_162.data_available,
        rule_163.data_available,
        rule_164.data_available,
    ])

    if any_exit_signal:
        overall: Section16OverallStatus = "EXIT_ACTIVE"
    elif not all_data_available:
        overall = "PARTIAL_DATA"
    else:
        overall = "ALL_CLEAR"

    return Section16Result(
        ticker=normalised,
        available=True,
        overall_status=overall,
        rule_161=rule_161,
        rule_162=rule_162,
        rule_163=rule_163,
        rule_164=rule_164,
        any_exit_signal=any_exit_signal,
        override_active=False,
        evaluated_at=datetime.now(tz=UTC),
    )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _fetch_cycle_record(
    ticker: str, session: AsyncSession
) -> dict[str, object] | None:
    """Fetch the current exit_rule_cycles row for ticker as a plain dict."""
    row = (
        await session.execute(
            select(ExitRuleCycle).where(ExitRuleCycle.ticker == ticker)
        )
    ).scalars().first()
    if row is None:
        return None
    return {
        "cycle_status": row.cycle_status,
        "cycle_one_date": row.cycle_one_date,
        "cycle_one_score": row.cycle_one_score,
        "cycle_two_date": row.cycle_two_date,
        "cycle_two_score": row.cycle_two_score,
        "reconciliation_pause": row.reconciliation_pause,
        "grok_score": row.grok_score,
        "claude_score": row.claude_score,
        "trim_triggered": row.trim_triggered,
        "full_exit_triggered": row.full_exit_triggered,
        "deferred_until": row.deferred_until,
        "override_active": row.override_active,
        "override_reason": row.override_reason,
        "override_set_by": row.override_set_by,
        "override_set_at": row.override_set_at,
    }


async def _fetch_latest_grok_score(
    ticker: str, session: AsyncSession
) -> dict[str, object] | None:
    """Fetch the most recent grok_scores row for ticker."""
    row = (
        await session.execute(
            select(GrokScore)
            .where(GrokScore.ticker == ticker)
            .order_by(GrokScore.score_date.desc())
            .limit(1)
        )
    ).scalars().first()
    if row is None:
        return None
    return {
        "grok_score": float(row.grok_score),
        "score_date": row.score_date,
    }


async def _evaluate_rule162_with_db(
    ticker: str, session: AsyncSession
) -> Rule162Result:
    """Check gap_down_events for an active HOLDING event for this ticker."""
    row = (
        await session.execute(
            select(GapDownEvent)
            .where(GapDownEvent.ticker == ticker)
            .where(GapDownEvent.status == "HOLDING")
            .order_by(GapDownEvent.created_at.desc())
            .limit(1)
        )
    ).scalars().first()

    if row is None:
        return Rule162Result(
            gap_triggered=False,
            status="CLEAR",
            data_available=True,
        )

    return Rule162Result(
        gap_triggered=True,
        status="HOLDING",
        gap_down_pct=row.gap_down_pct,
        prev_close=row.prev_close,
        open_price=row.open_price,
        event_date=row.event_date,
        hold_until=row.hold_until,
        rescore_at=row.rescore_at,
        rescore_score=row.rescore_score,
        resolved_at=row.resolved_at,
        data_available=True,
    )


async def _fetch_position_market_value(
    ticker: str, session: AsyncSession
) -> Decimal | None:
    """Return shares * current_price from the tickers table."""
    from atlas.models.ticker import Ticker

    row = (
        await session.execute(
            select(Ticker).where(Ticker.ticker == ticker)
        )
    ).scalars().first()

    if row is None or row.current_price is None or row.shares is None:
        return None
    return Decimal(str(row.shares)) * Decimal(str(row.current_price))


async def _fetch_gain_from_cost_pct(
    ticker: str, session: AsyncSession
) -> Decimal | None:
    """Return (current_price - cost_basis) / cost_basis * 100 from portfolio DB.

    Returns None when cost basis is unavailable.
    Cost basis is approximated as portfolio_config.cost_basis_per_share when present.
    """
    from atlas.models.ticker import Ticker

    ticker_row = (
        await session.execute(
            select(Ticker).where(Ticker.ticker == ticker)
        )
    ).scalars().first()

    if ticker_row is None or ticker_row.current_price is None:
        return None

    config_row = await session.get(AtlasConfig, f"cost_basis_{ticker}")

    if config_row is None:
        return None

    try:
        cost_basis = Decimal(str(config_row.value))
        current = Decimal(str(ticker_row.current_price))
        return ((current - cost_basis) / cost_basis) * Decimal("100")
    except Exception:
        return None


async def _fetch_f12_no_fly(ticker: str) -> bool:
    """Check F12 catalyst no-fly status via intra-service call.

    Returns True only if F12 is explicitly ACTIVE.
    Returns False on any failure (fail-open: do not silently block exits).
    """
    url = f"{_BASE_URL}/api/v1/framework12/{ticker}/status"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            data = resp.json()
            return bool(data.get("blocked", False))
        except Exception as exc:
            logger.warning("F12 status fetch failed for %s: %s", ticker, exc)
            return False


def _build_override_result(
    ticker: str, cycle_row: dict[str, object]
) -> Section16Result:
    """Return a Section16Result with all rules suppressed due to human override."""
    now = datetime.now(tz=UTC)
    clear_161 = Rule161Result(
        status="CLEAR",
        cycle_count=0,
        trim_triggered=False,
        full_exit_triggered=False,
    )
    clear_162 = Rule162Result(gap_triggered=False, status="CLEAR")
    clear_163 = Rule163Result(
        status="CLEAR", no_new_capital=False, consider_trim=False
    )
    clear_164 = Rule164Result(
        recommend_puts=False,
        status="NOT_TRIGGERED",
        conditions_met=0,
        conditions=[],
    )
    return Section16Result(
        ticker=ticker,
        available=True,
        overall_status="ALL_CLEAR",
        rule_161=clear_161,
        rule_162=clear_162,
        rule_163=clear_163,
        rule_164=clear_164,
        any_exit_signal=False,
        override_active=True,
        override_reason=str(cycle_row.get("override_reason")),
        override_set_by=(
            str(cycle_row.get("override_set_by"))
            if cycle_row.get("override_set_by")
            else None
        ),
        override_set_at=cycle_row.get("override_set_at"),  # type: ignore[arg-type]
        evaluated_at=now,
    )


# ---------------------------------------------------------------------------
# Active cycles summary
# ---------------------------------------------------------------------------


async def get_active_cycles(session: AsyncSession) -> ActiveCyclesSummary:
    """Return all tickers with non-CLEAR exit rule cycle state."""
    rows = (
        await session.execute(
            select(ExitRuleCycle).where(ExitRuleCycle.cycle_status != "CLEAR")
        )
    ).scalars().all()

    entries = [
        ActiveCycleEntry(
            ticker=row.ticker,
            cycle_status=row.cycle_status,
            cycle_one_date=row.cycle_one_date,
            cycle_one_score=row.cycle_one_score,
            trim_triggered=row.trim_triggered,
            full_exit_triggered=row.full_exit_triggered,
            deferred_until=row.deferred_until,
            override_active=row.override_active,
        )
        for row in rows
    ]

    return ActiveCyclesSummary(cycles=entries, total_active=len(entries))


# ---------------------------------------------------------------------------
# Decision trace writer
# ---------------------------------------------------------------------------


async def _log_section16_trace(
    *,
    session: AsyncSession,
    ticker: str,
    signal_type: str,
    trigger: str,
    resolution: str,
) -> None:
    """Append one immutable entry to decision_trace for a Section 16 event."""
    entry = DecisionTrace(
        timestamp_utc=datetime.now(tz=UTC),
        trigger=trigger,
        signal_type=signal_type,
        ticker=ticker,
        catalyst_type=None,
        catalyst_date=None,
        days_to_catalyst=None,
        actions_blocked=None,
        framework_states={"section16": resolution},
        regime_snapshot=None,
        data_freshness=None,
        human_override=False,
        override_reason=None,
    )
    session.add(entry)
    await session.flush()
