"""Section 16 — Entry Gatekeeper API.

Endpoints:
  GET  /api/v1/section16/{ticker}                   → Section16Result (full)
  GET  /api/v1/section16/{ticker}/gate              → {"gate": GateResult}
  POST /api/v1/section16/track/{ticker}             → TrackAssignment
  POST /api/v1/section16/rule4/{ticker}             → Rule4 row
  POST /api/v1/section16/override/{ticker}/use      → OverrideUsage row
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.section16 import (
    OverrideUseRequest,
    Rule4Request,
    Section16Result,
    TrackAssignmentRequest,
)
from atlas.services.section16_service import (
    evaluate_section16,
    fetch_f7_live,
    mark_override_used,
    upsert_rule4_today,
    upsert_track_assignment,
)

router = APIRouter(prefix="/section16", tags=["section16"])


def _normalise(ticker: str) -> str:
    return ticker.strip().upper()


@router.get("/{ticker}", response_model=Section16Result)
async def get_section16(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Section16Result:
    """Full Section 16 evaluation — fetches all live data on every call."""
    return await evaluate_section16(_normalise(ticker), session)


@router.get("/{ticker}/gate")
async def get_section16_gate(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Lightweight: returns just `{"ticker", "gate", "track"}`."""
    result = await evaluate_section16(_normalise(ticker), session)
    return {
        "ticker": result.ticker,
        "track": result.track,
        "gate": result.gate,
        "override_used": result.override_used,
    }


@router.post("/track/{ticker}", status_code=status.HTTP_200_OK)
async def post_track_assignment(
    ticker: str,
    body: TrackAssignmentRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await upsert_track_assignment(
        ticker=_normalise(ticker),
        track=body.track,
        assigned_by=body.assigned_by,
        notes=body.notes,
        session=session,
    )
    return {
        "ticker": row.ticker, "track": row.track,
        "assigned_by": row.assigned_by, "notes": row.notes,
    }


@router.post("/rule4/{ticker}", status_code=status.HTTP_200_OK)
async def post_rule4(
    ticker: str,
    body: Rule4Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await upsert_rule4_today(
        ticker=_normalise(ticker),
        fits_portfolio=body.fits_portfolio,
        set_by=body.set_by,
        cluster_gap=body.cluster_gap,
        redundancy_check=body.redundancy_check,
        notes=body.notes,
        session=session,
    )
    return {
        "ticker": row.ticker,
        "fit_date": row.fit_date.isoformat(),
        "fits_portfolio": row.fits_portfolio,
        "set_by": row.set_by,
    }


@router.post("/override/{ticker}/use", status_code=status.HTTP_200_OK)
async def post_override_use(
    ticker: str,
    body: OverrideUseRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Mark the override as used for the current earnings cycle."""
    norm = _normalise(ticker)
    f7 = await fetch_f7_live(norm)
    raw_date = f7.get("earnings_date")
    earnings_dt: date | None = None
    if isinstance(raw_date, str):
        try:
            earnings_dt = date.fromisoformat(raw_date[:10])
        except ValueError:
            earnings_dt = None
    if earnings_dt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No earnings date available; cannot scope override to a cycle.",
        )
    row = await mark_override_used(
        ticker=norm, used_by=body.used_by,
        earnings_date=earnings_dt, notes=body.notes, session=session,
    )
    return {
        "ticker": row.ticker,
        "earnings_cycle_start": row.earnings_cycle_start.isoformat(),
        "earnings_cycle_end": row.earnings_cycle_end.isoformat(),
        "override_used": row.override_used,
        "override_used_by": row.override_used_by,
    }
