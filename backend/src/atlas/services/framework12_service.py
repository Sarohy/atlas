"""Framework 12 — Decision Matrix sizing service.

Pipeline: Section 16 PASS → Framework 12 picks the highest-priority matching
row from `framework12_decision_matrix` and computes the recommended USD size
from the LIVE NAV reported by Framework 30.

NO market data is cached.  Decision matrix rows are read fresh from the DB
on every call.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.framework12_decision_matrix import Framework12DecisionMatrix
from atlas.schemas.framework12 import (
    DecisionMatrixRow,
    Framework12Result,
    Framework12Status,
)
from atlas.schemas.section16 import Section16Result
from atlas.services.section16_service import (
    evaluate_section16,
    fetch_f7_live,
    fetch_f9_live,
    fetch_f30_live,
)

logger = logging.getLogger(__name__)

# Default fallback row code — must exist in the seeded matrix.  Used when no
# active priority row matches the live signals + earnings + track combination.
_FALLBACK_PRIORITY_CODE: Final[str] = "4"


# ---------------------------------------------------------------------------
# Matrix loaders.
# ---------------------------------------------------------------------------


async def get_active_matrix_rows(
    session: AsyncSession,
) -> list[Framework12DecisionMatrix]:
    """Return all active matrix rows ordered by priority_order ascending."""
    res = await session.execute(
        select(Framework12DecisionMatrix)
        .where(Framework12DecisionMatrix.active.is_(True))
        .order_by(Framework12DecisionMatrix.priority_order.asc()),
    )
    return list(res.scalars().all())


def _to_row_schema(orm_row: Framework12DecisionMatrix) -> DecisionMatrixRow:
    return DecisionMatrixRow(
        priority_code=orm_row.priority_code,
        priority_label=orm_row.priority_label,
        track=orm_row.track,
        earnings_max_days=orm_row.earnings_max_days,
        earnings_min_days=orm_row.earnings_min_days,
        override_required=orm_row.override_required,
        underweight_required=orm_row.underweight_required,
        strong_flow_required=orm_row.strong_flow_required,
        size_min_pct=float(orm_row.size_min_pct),
        size_max_pct=float(orm_row.size_max_pct),
        timing_rule=orm_row.timing_rule,
        is_watchlist_only=orm_row.is_watchlist_only,
        priority_order=orm_row.priority_order,
        active=orm_row.active,
    )


# ---------------------------------------------------------------------------
# Row matching against live context.
# ---------------------------------------------------------------------------


def _row_matches(
    row: Framework12DecisionMatrix,
    *,
    track: str,
    days_to_earnings: int | None,
    override_used: bool,
    is_underweight: bool,
    is_strong_flow: bool,
) -> bool:
    """True when the live context satisfies all of this row's filters."""
    if row.is_watchlist_only:
        # Fallback row — matches anything (callers handle separately).
        return True

    if row.track is not None and row.track != track:
        return False

    if row.earnings_max_days is not None and (
        days_to_earnings is None or days_to_earnings > row.earnings_max_days
    ):
        return False

    if row.earnings_min_days is not None and (
        days_to_earnings is None or days_to_earnings < row.earnings_min_days
    ):
        return False

    if row.override_required and not override_used:
        return False

    if row.underweight_required and not is_underweight:
        return False

    return not (row.strong_flow_required and not is_strong_flow)


def _select_priority_row(
    rows: list[Framework12DecisionMatrix],
    *,
    track: str,
    days_to_earnings: int | None,
    override_used: bool,
    is_underweight: bool,
    is_strong_flow: bool,
) -> Framework12DecisionMatrix | None:
    """Pick the highest-priority matching row, or fallback (Watchlist Only)."""
    for row in rows:
        if row.is_watchlist_only:
            continue
        if _row_matches(
            row,
            track=track,
            days_to_earnings=days_to_earnings,
            override_used=override_used,
            is_underweight=is_underweight,
            is_strong_flow=is_strong_flow,
        ):
            return row

    # Fallback to Watchlist Only row.
    for row in rows:
        if row.priority_code == _FALLBACK_PRIORITY_CODE:
            return row
    return None


# ---------------------------------------------------------------------------
# Sizing math.
# ---------------------------------------------------------------------------


def _compute_size_usd(
    row: Framework12DecisionMatrix, current_nav_usd: float | None,
) -> tuple[float | None, float | None]:
    if current_nav_usd is None:
        return None, None
    pct_to_fraction = 100.0  # row pcts are stored in percent units
    min_usd = current_nav_usd * float(row.size_min_pct) / pct_to_fraction
    max_usd = current_nav_usd * float(row.size_max_pct) / pct_to_fraction
    return min_usd, max_usd


# ---------------------------------------------------------------------------
# Live signal helpers — same definitions as section16_service uses.
# ---------------------------------------------------------------------------


def _is_underweight(f9: dict[str, Any]) -> bool:
    tier = (f9.get("signal_tier") or "").upper()
    return tier in {"LOW", "NEUTRAL", ""}


def _is_strong_flow(f9: dict[str, Any]) -> bool:
    tier = (f9.get("signal_tier") or "").upper()
    direction = (f9.get("flow_direction") or "").upper()
    return tier in {"HIGH", "STRONG"} and direction in {"BULLISH", "STRONG_BULLISH"}


# ---------------------------------------------------------------------------
# Top-level evaluator.
# ---------------------------------------------------------------------------


async def evaluate_framework12(
    ticker: str, session: AsyncSession,
) -> Framework12Result:
    """Evaluate sizing for one ticker.

    Always runs Section 16 first.  When the gate does not PASS, returns a
    BLOCKED result with the gate reason — no sizing is computed.
    """
    s16: Section16Result = await evaluate_section16(ticker, session)
    now_utc = datetime.now(tz=UTC)

    if s16.gate != "PASS":
        return Framework12Result(
            ticker=ticker, status="BLOCKED",
            blocked_reason=f"Section 16 gate = {s16.gate}",
            evaluated_at=now_utc,
        )

    f7, f9, f30 = await fetch_f7_live(ticker), await fetch_f9_live(ticker), await fetch_f30_live()
    current_nav = f30.get("current_nav")
    current_nav_usd = float(current_nav) if current_nav is not None else None

    days = f7.get("days_to_earnings")
    days_int = int(days) if isinstance(days, int) else None

    rows = await get_active_matrix_rows(session)
    chosen = _select_priority_row(
        rows,
        track=s16.track,
        days_to_earnings=days_int,
        override_used=s16.override_used,
        is_underweight=_is_underweight(f9),
        is_strong_flow=_is_strong_flow(f9),
    )

    if chosen is None:
        return Framework12Result(
            ticker=ticker, status="UNKNOWN",
            current_nav_usd=current_nav_usd,
            blocked_reason="No active matrix rows configured.",
            evaluated_at=now_utc,
        )

    size_min, size_max = _compute_size_usd(chosen, current_nav_usd)
    status_lit: Framework12Status = (
        "WATCHLIST" if chosen.is_watchlist_only else "SIZED"
    )

    return Framework12Result(
        ticker=ticker,
        status=status_lit,
        matched_row=_to_row_schema(chosen),
        current_nav_usd=current_nav_usd,
        size_min_usd=size_min,
        size_max_usd=size_max,
        timing_rule=chosen.timing_rule,
        evaluated_at=now_utc,
    )


__all__ = [
    "evaluate_framework12",
    "get_active_matrix_rows",
]
