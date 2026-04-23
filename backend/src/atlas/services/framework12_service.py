"""Framework 12 — Catalyst No-Fly Zone service.

Protects unrealized gains by blocking all sell-side actions (covered calls,
partial sells, and trims) within the catalyst window before a confirmed
catalyst event.

Data sources (single source of truth rules):
  Framework 7  — ONLY source for earnings dates per ticker.  Never fetches
                 earnings from Alpha Vantage or Polygon directly.
  catalyst_events DB — ONLY source for non-earnings catalysts.
  atlas_config DB    — ONLY source for catalyst_window_days and
                       exit_deferral_trading_days.  Never hardcode these.
  framework12_overrides DB — per-action human overrides.

No-fly zone cache TTL: 5 minutes per ticker.
Cache uses in-memory dict (swap for Redis.setex in production).

Consuming frameworks:
  Framework 3  — reads no_fly_active / trims_status before TRIM/SELL signal.
  Section 16   — reads exit_rule_deferred before executing trim window.

Architecture: module-level async functions + module-level _cache dict.
Matches the pattern of framework11_service.py exactly.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Final

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.atlas_config import AtlasConfig
from atlas.models.catalyst_event import CatalystEvent
from atlas.models.decision_trace import DecisionTrace
from atlas.models.framework12_override import Framework12Override
from atlas.models.ticker import Ticker
from atlas.schemas.framework12 import (
    ActionStatus,
    ActiveCatalyst,
    CatalystType,
    Framework12Result,
    Framework12StatusResult,
    Framework12PortfolioSummary,
    NoFlyStatus,
    OverrideDetail,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — all spec values are named constants, never hardcoded inline
# ---------------------------------------------------------------------------

# In-memory result cache TTL — 5 minutes per ticker.
_CACHE_TTL_SECONDS: Final[int] = 300

# Config DB keys — only the key strings are constants; values come from DB.
_CONFIG_KEY_WINDOW: Final[str] = "f12_catalyst_window_days"
_CONFIG_KEY_DEFERRAL: Final[str] = "f12_exit_deferral_trading_days"

# Framework 7 endpoint path (relative to backend base URL).
_F7_PATH: Final[str] = "/api/v1/framework7/{ticker}"

# Section 16 endpoint path (not yet implemented — returns 404 gracefully).
_S16_PATH: Final[str] = "/api/v1/section16/exit-status/{ticker}"

# Internal base URL for service-to-service calls.
_INTERNAL_BASE_URL: Final[str] = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Module-level in-memory cache: ticker → (Framework12Result, expiry_epoch)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[Framework12Result, float]] = {}


def _cache_get(ticker: str) -> Framework12Result | None:
    """Return cached result if not expired, else None."""
    entry = _cache.get(ticker)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _cache[ticker]
        return None
    return result


def _cache_set(ticker: str, result: Framework12Result) -> None:
    """Store result with TTL expiry."""
    _cache[ticker] = (result, time.monotonic() + _CACHE_TTL_SECONDS)


def cache_invalidate(ticker: str) -> None:
    """Remove a single ticker from the cache."""
    _cache.pop(ticker, None)


def cache_invalidate_all() -> None:
    """Remove ALL tickers from the cache."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Sync accessor for consuming frameworks (Framework 3)
# ---------------------------------------------------------------------------


def get_f12_status(ticker: str) -> Framework12StatusResult | None:
    """Return the lightweight status for *ticker* from in-memory cache.

    Returns None when the cache is empty or expired for this ticker.
    Consuming frameworks (F3, Section 16) call this — never evaluate_framework12
    directly — so they always read F12 as the single source of truth.
    """
    result = _cache_get(ticker)
    if result is None:
        return None
    return Framework12StatusResult(
        no_fly_status=result.no_fly_status,
        no_fly_active=result.no_fly_active,
        covered_calls_status=result.covered_calls_status,
        partial_sells_status=result.partial_sells_status,
        trims_status=result.trims_status,
        nearest_catalyst_date=(
            result.nearest_catalyst.catalyst_date if result.nearest_catalyst else None
        ),
        nearest_catalyst_type=(
            result.nearest_catalyst.catalyst_type if result.nearest_catalyst else None
        ),
        days_to_catalyst=(
            result.nearest_catalyst.days_to_catalyst if result.nearest_catalyst else None
        ),
        exit_rule_deferred=result.exit_rule_deferred,
        exit_rule_deferred_until=result.exit_rule_deferred_until,
        data_gap_severity=result.data_gap_severity,
    )


# ---------------------------------------------------------------------------
# Config helpers — always read from DB, never hardcode
# ---------------------------------------------------------------------------


async def _get_config_int(key: str, session: AsyncSession) -> int:
    """Fetch a single integer value from atlas_config.

    Raises RuntimeError when the key is missing or the DB is unavailable.
    Never returns a hardcoded fallback.
    """
    stmt = select(AtlasConfig.value).where(AtlasConfig.key == key)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise RuntimeError(
            f"Config key '{key}' not found in atlas_config table. "
            "Run the Framework 12 migration to seed the required values."
        )
    return int(row)


# ---------------------------------------------------------------------------
# Earnings catalyst (Framework 7 — single source of truth)
# ---------------------------------------------------------------------------


async def _fetch_earnings_catalyst(
    ticker: str,
    catalyst_window_days: int,
    alphavantage_api_key: str,
    session: AsyncSession,
) -> dict[str, object]:
    """Read earnings proximity from Framework 7.

    Framework 7 is the ONLY authoritative source for earnings dates.
    This function calls the F7 service directly (Python import) to avoid
    an internal HTTP round-trip, mirroring the pattern used by leaps_service.

    Returns a dict with keys:
      available   bool   — True when F7 returned usable data
      active      bool | None — None = unknown (F7 offline / data missing)
      catalyst_date, days_to_catalyst, catalyst_type, description, source
        (only present when active = True)
      reason      str    — human-readable explanation when available = False
    """
    from atlas.config import get_settings
    from atlas.services.framework7_service import Framework7Service

    settings = get_settings()
    if not settings.alphavantage_api_key:
        return {
            "available": False,
            "active": None,
            "reason": "ALPHAVANTAGE_API_KEY not configured — cannot check earnings.",
        }

    try:
        svc = Framework7Service(
            alphavantage_api_key=settings.alphavantage_api_key,
            polygon_api_key=settings.polygon_api_key or "",
            transcript_api_key=settings.earnings_transcript_api_key or "",
            benzinga_api_key=settings.benzinga_api_key or "",
            unusual_whales_api_key=settings.unusual_whales_api_key or "",
            sec_api_key=settings.sec_api_key or "",
        )
        gate = await svc.compute(ticker)

        if gate.days_to_earnings is None:
            return {"available": True, "active": False}

        if gate.days_to_earnings <= catalyst_window_days:
            return {
                "available": True,
                "active": True,
                "catalyst_date": gate.earnings_date.isoformat() if gate.earnings_date else None,
                "days_to_catalyst": gate.days_to_earnings,
                "catalyst_type": CatalystType.EARNINGS,
                "description": "Earnings report",
                "source": "Framework 7",
            }

        return {"available": True, "active": False}

    except Exception as exc:
        logger.warning(
            "Framework 12: Framework 7 call failed",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return {"available": False, "active": None, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Non-earnings catalysts (catalyst_events DB)
# ---------------------------------------------------------------------------


async def _fetch_non_earnings_catalysts(
    ticker: str,
    catalyst_window_days: int,
    session: AsyncSession,
) -> dict[str, object]:
    """Query catalyst_events for active non-earnings catalysts within window.

    Returns a dict with keys:
      available   bool
      active      bool | None
      catalysts   list[dict]  (only when active = True)
      reason      str         (only when available = False)
    """
    try:
        today = date.today()
        window_end = today + timedelta(days=catalyst_window_days)

        stmt = (
            select(CatalystEvent)
            .where(
                CatalystEvent.ticker == ticker,
                CatalystEvent.status == "ACTIVE",
                CatalystEvent.catalyst_date >= today,
                CatalystEvent.catalyst_date <= window_end,
            )
            .order_by(CatalystEvent.catalyst_date.asc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return {"available": True, "active": False, "catalysts": []}

        catalysts = [
            {
                "catalyst_type": row.catalyst_type,
                "catalyst_date": row.catalyst_date.isoformat(),
                "days_to_catalyst": (row.catalyst_date - today).days,
                "description": row.description,
                "source": "catalyst_events DB",
            }
            for row in rows
        ]
        return {"available": True, "active": True, "catalysts": catalysts}

    except Exception as exc:
        logger.warning(
            "Framework 12: catalyst_events DB query failed",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return {
            "available": False,
            "active": None,
            "reason": str(exc),
            "catalysts": [],
        }


# ---------------------------------------------------------------------------
# Override lookup
# ---------------------------------------------------------------------------


async def _fetch_active_overrides(
    ticker: str,
    session: AsyncSession,
) -> dict[str, OverrideDetail]:
    """Return a dict of action_type → OverrideDetail for active, non-expired overrides."""
    try:
        now = datetime.now(tz=timezone.utc)
        stmt = (
            select(Framework12Override)
            .where(
                Framework12Override.ticker == ticker,
                Framework12Override.override_active.is_(True),
                Framework12Override.override_expires_at > now,
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        return {
            row.action_type: OverrideDetail(
                action_type=row.action_type,
                override_reason=row.override_reason,
                entered_by=row.entered_by,
                created_at=row.created_at.isoformat(),
                override_expires_at=row.override_expires_at.isoformat(),
            )
            for row in rows
        }
    except Exception as exc:
        logger.warning(
            "Framework 12: override lookup failed",
            extra={"ticker": ticker, "error": repr(exc)},
        )
        return {}


# ---------------------------------------------------------------------------
# Exit rule status (Section 16 — not yet implemented, handled gracefully)
# ---------------------------------------------------------------------------


async def _fetch_exit_rule_status(ticker: str) -> dict[str, object]:
    """Check whether Section 16 has an active exit rule for ticker.

    Section 16 is not yet implemented in V1.  This function returns
    available=False gracefully so Framework 12 can surface the correct
    PARTIAL data_gap_severity without crashing.

    When Section 16 is built it will expose:
      GET /api/v1/section16/exit-status/{ticker}
    and this function will call it.
    """
    # Section 16 is not yet implemented — return gracefully.
    return {
        "available": False,
        "exit_rule_active": None,
        "reason": "Section 16 not yet implemented in V1.",
    }


# ---------------------------------------------------------------------------
# Deferral date calculator (pure — no I/O)
# ---------------------------------------------------------------------------


def _calculate_deferral_date(
    catalyst_date_str: str,
    deferral_trading_days: int,
) -> str:
    """Return the ISO date that is *deferral_trading_days* trading days after catalyst_date.

    Skips weekends (Saturday = 5, Sunday = 6).
    Public holidays are not tracked in V1.
    Pure function — no I/O.
    """
    result = date.fromisoformat(catalyst_date_str)
    days_added = 0
    while days_added < deferral_trading_days:
        result += timedelta(days=1)
        if result.weekday() < 5:  # Mon–Fri only
            days_added += 1
    return result.isoformat()


# ---------------------------------------------------------------------------
# Decision Trace writer
# ---------------------------------------------------------------------------


async def _log_decision_trace(
    *,
    session: AsyncSession,
    trigger: str,
    signal_type: str,
    ticker: str,
    catalyst_type: str | None,
    catalyst_date: str | None,
    days_to_catalyst: int | None,
    actions_blocked: list[str] | None,
    resolution: str,
    human_override: bool,
    override_reason: str | None = None,
    override_action: str | None = None,
    visible_in_briefing: bool = False,
) -> None:
    """Append one immutable entry to the decision_trace table.

    Never updates or deletes existing entries.
    """
    try:
        entry = DecisionTrace(
            timestamp_utc=datetime.now(tz=timezone.utc),
            trigger=trigger,
            signal_type=signal_type,
            ticker=ticker,
            catalyst_type=catalyst_type,
            catalyst_date=catalyst_date,
            days_to_catalyst=days_to_catalyst,
            actions_blocked={"blocked": actions_blocked} if actions_blocked else None,
            human_override=human_override,
            override_reason=override_reason,
            override_action=override_action,
            resolution=resolution,
            visible_in_briefing=visible_in_briefing,
        )
        session.add(entry)
        await session.flush()
    except Exception as exc:
        # Decision trace writes must never crash the main evaluation path.
        logger.error(
            "Framework 12: failed to write decision trace",
            extra={"ticker": ticker, "trigger": trigger, "error": repr(exc)},
        )


# ---------------------------------------------------------------------------
# UNKNOWN result builder
# ---------------------------------------------------------------------------


def _build_unknown_result(
    ticker: str,
    warnings: list[str],
    catalyst_window_days: int,
    exit_deferral_trading_days: int,
) -> Framework12Result:
    """Return an all-UNKNOWN Framework12Result for error paths."""
    return Framework12Result(
        ticker=ticker,
        no_fly_status=NoFlyStatus.UNKNOWN,
        no_fly_active=None,
        active_catalysts=[],
        nearest_catalyst=None,
        catalyst_window_days=catalyst_window_days,
        covered_calls_status=ActionStatus.UNKNOWN,
        partial_sells_status=ActionStatus.UNKNOWN,
        trims_status=ActionStatus.UNKNOWN,
        covered_calls_override=None,
        partial_sells_override=None,
        trims_override=None,
        exit_rule_active=None,
        exit_rule_deferred=False,
        exit_rule_deferred_until=None,
        exit_deferral_trading_days=exit_deferral_trading_days,
        f7_available=False,
        catalyst_db_available=False,
        section16_available=False,
        data_gap_severity="CRITICAL",
        warning_messages=warnings,
        last_updated=datetime.utcnow().isoformat(),
        cache_hit=False,
    )


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


async def evaluate_framework12(
    ticker: str,
    session: AsyncSession,
) -> Framework12Result:
    """Full Framework 12 evaluation for one ticker.

    Steps:
      1. Read catalyst_window_days and exit_deferral_trading_days from DB.
      2. Fetch earnings catalyst (F7) and non-earnings catalysts (DB) in parallel.
      3. Build active_catalysts list and determine no_fly_active.
      4. Fetch overrides and exit rule status in parallel.
      5. Determine per-action status (BLOCKED / PERMITTED / OVERRIDDEN / UNKNOWN).
      6. Handle exit rule conflict / deferral.
      7. Log decision trace on block or deferral.
      8. Cache result (5 minutes).
    """
    normalised = ticker.strip().upper()
    warnings: list[str] = []

    # ── Check cache ──────────────────────────────────────────────────────────
    cached = _cache_get(normalised)
    if cached is not None:
        return Framework12Result(**{**cached.model_dump(), "cache_hit": True})

    # ── Step 1: Read config from DB ──────────────────────────────────────────
    try:
        catalyst_window_days = await _get_config_int(_CONFIG_KEY_WINDOW, session)
        exit_deferral_trading_days = await _get_config_int(
            _CONFIG_KEY_DEFERRAL, session
        )
    except RuntimeError as exc:
        err_msg = f"Cannot read config from DB: {exc}"
        logger.error("Framework 12: config read failure", extra={"error": err_msg})
        result = _build_unknown_result(
            normalised, [err_msg], catalyst_window_days=0, exit_deferral_trading_days=0
        )
        _cache_set(normalised, result)
        return result

    from atlas.config import get_settings
    settings = get_settings()

    # ── Step 2: Parallel fetch — earnings + non-earnings ────────────────────
    earnings_result_raw, non_earnings_result_raw = await asyncio.gather(
        _fetch_earnings_catalyst(
            normalised,
            catalyst_window_days,
            settings.alphavantage_api_key or "",
            session,
        ),
        _fetch_non_earnings_catalysts(normalised, catalyst_window_days, session),
        return_exceptions=True,
    )

    # Guard against unexpected exceptions from gather.
    earnings_result: dict[str, object]
    non_earnings_result: dict[str, object]

    if isinstance(earnings_result_raw, Exception):
        earnings_result = {
            "available": False,
            "active": None,
            "reason": str(earnings_result_raw),
        }
    else:
        earnings_result = earnings_result_raw  # type: ignore[assignment]

    if isinstance(non_earnings_result_raw, Exception):
        non_earnings_result = {
            "available": False,
            "active": None,
            "reason": str(non_earnings_result_raw),
            "catalysts": [],
        }
    else:
        non_earnings_result = non_earnings_result_raw  # type: ignore[assignment]

    f7_available = bool(earnings_result.get("available", False))
    catalyst_db_available = bool(non_earnings_result.get("available", False))

    if not f7_available:
        reason = earnings_result.get("reason", "unknown error")
        warnings.append(
            f"Framework 7 unavailable — cannot verify earnings catalyst. "
            f"Reason: {reason}. Treating earnings status as unknown."
        )

    if not catalyst_db_available:
        reason = non_earnings_result.get("reason", "unknown error")
        warnings.append(
            f"Catalyst events DB unavailable — cannot verify non-earnings catalysts. "
            f"Reason: {reason}."
        )

    # ── Step 3: Build active catalysts list ──────────────────────────────────
    active_catalysts: list[ActiveCatalyst] = []

    earnings_active = earnings_result.get("active")
    if earnings_active is True:
        active_catalysts.append(
            ActiveCatalyst(
                catalyst_type=CatalystType.EARNINGS,
                catalyst_date=str(earnings_result.get("catalyst_date", "")),
                days_to_catalyst=int(earnings_result.get("days_to_catalyst", 0)),
                description="Earnings report",
                source="Framework 7",
            )
        )

    non_earnings_active = non_earnings_result.get("active")
    if non_earnings_active is True:
        for c in non_earnings_result.get("catalysts", []):  # type: ignore[union-attr]
            c_dict = c  # type: ignore[assignment]
            active_catalysts.append(
                ActiveCatalyst(
                    catalyst_type=CatalystType(str(c_dict["catalyst_type"])),
                    catalyst_date=str(c_dict["catalyst_date"]),
                    days_to_catalyst=int(c_dict["days_to_catalyst"]),
                    description=c_dict.get("description"),  # type: ignore[arg-type]
                    source="catalyst_events DB",
                )
            )

    # Sort by soonest catalyst first.
    active_catalysts.sort(key=lambda x: x.days_to_catalyst)
    nearest_catalyst = active_catalysts[0] if active_catalysts else None

    # ── Step 4: Determine no_fly_active ──────────────────────────────────────
    if active_catalysts:
        no_fly_active: bool | None = True
        no_fly_status = NoFlyStatus.ACTIVE
    elif earnings_active is None or non_earnings_active is None:
        no_fly_active = None
        no_fly_status = NoFlyStatus.UNKNOWN
        warnings.append(
            "No-fly zone status unknown — one or more data sources unavailable. "
            "All sell-side actions treated as BLOCKED for safety."
        )
    else:
        no_fly_active = False
        no_fly_status = NoFlyStatus.CLEAR

    # ── Step 5: Parallel fetch — overrides + exit rule ───────────────────────
    overrides_raw, exit_status_raw = await asyncio.gather(
        _fetch_active_overrides(normalised, session),
        _fetch_exit_rule_status(normalised),
        return_exceptions=True,
    )

    overrides: dict[str, OverrideDetail] = (
        {} if isinstance(overrides_raw, Exception) else overrides_raw  # type: ignore[assignment]
    )
    exit_status: dict[str, object] = (
        {"available": False, "exit_rule_active": None}
        if isinstance(exit_status_raw, Exception)
        else exit_status_raw  # type: ignore[assignment]
    )

    section16_available = bool(exit_status.get("available", False))

    # ── Step 6: Per-action status ────────────────────────────────────────────
    def _action_status(
        action_key: str,
    ) -> tuple[ActionStatus, OverrideDetail | None]:
        override = overrides.get(action_key)
        if override:
            return ActionStatus.OVERRIDDEN, override
        if no_fly_active is True:
            return ActionStatus.BLOCKED, None
        if no_fly_active is None:
            return ActionStatus.UNKNOWN, None
        return ActionStatus.PERMITTED, None

    covered_calls_status, covered_calls_override = _action_status("COVERED_CALL")
    partial_sells_status, partial_sells_override = _action_status("PARTIAL_SELL")
    trims_status, trims_override = _action_status("TRIM")

    # ── Step 7: Exit rule conflict / deferral ────────────────────────────────
    exit_rule_active: bool | None = exit_status.get("exit_rule_active")  # type: ignore[assignment]
    exit_rule_deferred = False
    exit_rule_deferred_until: str | None = None

    if (
        exit_rule_active is True
        and no_fly_active is True
        and nearest_catalyst is not None
    ):
        exit_rule_deferred = True
        exit_rule_deferred_until = _calculate_deferral_date(
            nearest_catalyst.catalyst_date, exit_deferral_trading_days
        )
        warnings.append(
            f"EXIT RULE DEFERRED — {nearest_catalyst.catalyst_type} catalyst "
            f"on {nearest_catalyst.catalyst_date} within no-fly window. "
            f"Trim window resumes {exit_deferral_trading_days} trading days "
            f"after catalyst: {exit_rule_deferred_until}."
        )
        await _log_decision_trace(
            session=session,
            trigger="FRAMEWORK_12_CONFLICT",
            signal_type="DEFER",
            ticker=normalised,
            catalyst_type=nearest_catalyst.catalyst_type,
            catalyst_date=nearest_catalyst.catalyst_date,
            days_to_catalyst=nearest_catalyst.days_to_catalyst,
            actions_blocked=["COVERED_CALL", "PARTIAL_SELL", "TRIM"],
            resolution=f"Exit rule deferred to {exit_rule_deferred_until}",
            human_override=False,
        )
    elif not section16_available:
        warnings.append(
            "Section 16 unavailable — cannot check exit rule conflict. "
            "Deferral status unknown."
        )

    # ── Step 8: Log block to Decision Trace ──────────────────────────────────
    if no_fly_active is True:
        blocked_actions = [
            a
            for a, s in [
                ("COVERED_CALL", covered_calls_status),
                ("PARTIAL_SELL", partial_sells_status),
                ("TRIM", trims_status),
            ]
            if s == ActionStatus.BLOCKED
        ]
        if blocked_actions:
            await _log_decision_trace(
                session=session,
                trigger="FRAMEWORK_12",
                signal_type="BLOCK",
                ticker=normalised,
                catalyst_type=(
                    nearest_catalyst.catalyst_type if nearest_catalyst else None
                ),
                catalyst_date=(
                    nearest_catalyst.catalyst_date if nearest_catalyst else None
                ),
                days_to_catalyst=(
                    nearest_catalyst.days_to_catalyst if nearest_catalyst else None
                ),
                actions_blocked=blocked_actions,
                resolution="BLOCKED — no-fly zone active",
                human_override=False,
            )

    # ── Step 9: Data gap severity ─────────────────────────────────────────────
    if not f7_available and not catalyst_db_available:
        gap_severity = "CRITICAL"
    elif not f7_available or not catalyst_db_available:
        gap_severity = "MAJOR"
    elif not section16_available:
        gap_severity = "PARTIAL"
    else:
        gap_severity = "NONE"

    # ── Step 10: Build + cache result ────────────────────────────────────────
    result = Framework12Result(
        ticker=normalised,
        no_fly_status=no_fly_status,
        no_fly_active=no_fly_active,
        active_catalysts=active_catalysts,
        nearest_catalyst=nearest_catalyst,
        catalyst_window_days=catalyst_window_days,
        covered_calls_status=covered_calls_status,
        partial_sells_status=partial_sells_status,
        trims_status=trims_status,
        covered_calls_override=covered_calls_override,
        partial_sells_override=partial_sells_override,
        trims_override=trims_override,
        exit_rule_active=exit_rule_active,
        exit_rule_deferred=exit_rule_deferred,
        exit_rule_deferred_until=exit_rule_deferred_until,
        exit_deferral_trading_days=exit_deferral_trading_days,
        f7_available=f7_available,
        catalyst_db_available=catalyst_db_available,
        section16_available=section16_available,
        data_gap_severity=gap_severity,
        warning_messages=warnings,
        last_updated=datetime.utcnow().isoformat(),
        cache_hit=False,
    )

    _cache_set(normalised, result)
    return result


# ---------------------------------------------------------------------------
# Portfolio summary — evaluate all held tickers in parallel
# ---------------------------------------------------------------------------


async def evaluate_portfolio_summary(
    session: AsyncSession,
) -> Framework12PortfolioSummary:
    """Evaluate Framework 12 for every ticker in the portfolio concurrently.

    Uses asyncio.gather(return_exceptions=True) so one failed ticker does not
    block the others.
    """
    stmt = select(Ticker.ticker)
    result = await session.execute(stmt)
    tickers = [row[0] for row in result.all()]

    if not tickers:
        return Framework12PortfolioSummary(
            tickers_in_no_fly=[],
            tickers_clear=[],
            tickers_unknown=[],
            total_held=0,
            active_catalysts_count=0,
        )

    results = await asyncio.gather(
        *[evaluate_framework12(t, session) for t in tickers],
        return_exceptions=True,
    )

    no_fly: list[str] = []
    clear: list[str] = []
    unknown: list[str] = []
    total_catalysts = 0

    for r in results:
        if isinstance(r, Exception):
            unknown.append("UNKNOWN")
            continue
        f12 = r  # type: ignore[assignment]
        if f12.no_fly_status == NoFlyStatus.ACTIVE:
            no_fly.append(f12.ticker)
            total_catalysts += len(f12.active_catalysts)
        elif f12.no_fly_status == NoFlyStatus.CLEAR:
            clear.append(f12.ticker)
        else:
            unknown.append(f12.ticker)

    return Framework12PortfolioSummary(
        tickers_in_no_fly=no_fly,
        tickers_clear=clear,
        tickers_unknown=unknown,
        total_held=len(tickers),
        active_catalysts_count=total_catalysts,
    )
