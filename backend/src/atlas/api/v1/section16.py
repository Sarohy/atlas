"""API routes for Section 16 — Exit Rules.

GET  /api/v1/section16/exit-status/{ticker}          → Section16Result
GET  /api/v1/section16/exit-status/{ticker}/simple   → Section16SimpleResult (F12 integration)
GET  /api/v1/section16/active-cycles                 → ActiveCyclesSummary
POST /api/v1/section16/override/{ticker}             → {"ok": bool}
POST /api/v1/section16/grok-score/{ticker}           → {"ok": bool}
PUT  /api/v1/section16/gap-down/{event_id}/resolve   → {"ok": bool}

Architecture note: /active-cycles is registered before /{ticker} routes so
FastAPI does not interpret "active-cycles" as a ticker symbol.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.exit_rule_cycle import ExitRuleCycle
from atlas.models.gap_down_event import GapDownEvent
from atlas.models.grok_score import GrokScore
from atlas.schemas.section16 import (
    ActiveCyclesSummary,
    GrokScoreRequest,
    OverrideRequest,
    ResolveGapDownRequest,
    Section16Result,
    Section16SimpleResult,
)
from atlas.services.section16_service import (
    evaluate_section16,
    get_active_cycles,
)

router = APIRouter(prefix="/section16", tags=["section16"])

# Minimum override reason length (must match schema).
_OVERRIDE_REASON_MIN_LEN = 50


# ---------------------------------------------------------------------------
# Portfolio-level routes (must come before /{ticker} routes)
# ---------------------------------------------------------------------------


@router.get("/active-cycles", response_model=ActiveCyclesSummary)
async def get_active_cycles_endpoint(
    session: AsyncSession = Depends(get_db_session),
) -> ActiveCyclesSummary:
    """Return all tickers with a non-CLEAR exit rule cycle."""
    return await get_active_cycles(session)


# ---------------------------------------------------------------------------
# Per-ticker routes
# ---------------------------------------------------------------------------


@router.get("/exit-status/{ticker}", response_model=Section16Result)
async def get_exit_status(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Section16Result:
    """Full Section 16 evaluation for a single ticker.

    Called by Framework 12 to check for active exit conflicts.
    """
    normalised = ticker.upper().strip()
    if not normalised or len(normalised) > 10:
        raise HTTPException(status_code=422, detail="Invalid ticker symbol.")
    return await evaluate_section16(normalised, session)


@router.get("/exit-status/{ticker}/simple", response_model=Section16SimpleResult)
async def get_exit_status_simple(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Section16SimpleResult:
    """Lightweight exit status for F12 integration.

    Returns only: available, exit_rule_active, overall_status, ticker.
    """
    normalised = ticker.upper().strip()
    if not normalised or len(normalised) > 10:
        raise HTTPException(status_code=422, detail="Invalid ticker symbol.")

    result = await evaluate_section16(normalised, session)
    exit_rule_active: bool | None = None
    if result.overall_status == "EXIT_ACTIVE":
        exit_rule_active = True
    elif result.overall_status == "ALL_CLEAR":
        exit_rule_active = False

    return Section16SimpleResult(
        available=True,
        exit_rule_active=exit_rule_active,
        overall_status=result.overall_status,
        ticker=normalised,
    )


@router.post("/override/{ticker}")
async def set_override(
    ticker: str,
    body: OverrideRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """Apply a human override for a ticker, suppressing all exit signals.

    Requires a written justification of at least 50 characters.
    This action is logged to Decision Trace.
    """
    normalised = ticker.upper().strip()
    if not normalised or len(normalised) > 10:
        raise HTTPException(status_code=422, detail="Invalid ticker symbol.")

    if len(body.reason) < _OVERRIDE_REASON_MIN_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"Override reason must be at least {_OVERRIDE_REASON_MIN_LEN} characters.",
        )

    row = (
        await session.execute(
            select(ExitRuleCycle).where(ExitRuleCycle.ticker == normalised)
        )
    ).scalars().first()

    now = datetime.now(tz=UTC)

    if row is None:
        row = ExitRuleCycle(
            ticker=normalised,
            cycle_status="CLEAR",
            override_active=True,
            override_reason=body.reason,
            override_set_by=body.set_by,
            override_set_at=now,
        )
        session.add(row)
    else:
        row.override_active = True
        row.override_reason = body.reason
        row.override_set_by = body.set_by
        row.override_set_at = now

    await session.commit()
    return {"ok": True}


@router.post("/grok-score/{ticker}")
async def enter_grok_score(
    ticker: str,
    body: GrokScoreRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """Enter a Grok conviction score for a ticker and score date.

    Upserts (replaces) the existing score for the same (ticker, score_date).
    """
    normalised = ticker.upper().strip()
    if not normalised or len(normalised) > 10:
        raise HTTPException(status_code=422, detail="Invalid ticker symbol.")

    existing = (
        await session.execute(
            select(GrokScore)
            .where(GrokScore.ticker == normalised)
            .where(GrokScore.score_date == body.score_date)
        )
    ).scalars().first()

    if existing is not None:
        existing.grok_score = body.score
        existing.entered_by = body.entered_by
        existing.notes = body.notes
    else:
        session.add(
            GrokScore(
                ticker=normalised,
                score_date=body.score_date,
                grok_score=body.score,
                entered_by=body.entered_by,
                notes=body.notes,
            )
        )

    await session.commit()
    return {"ok": True}


@router.put("/gap-down/{event_id}/resolve")
async def resolve_gap_down(
    event_id: int,
    body: ResolveGapDownRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """Mark a gap-down event as RESOLVED (post-hold-window action taken)."""
    row = await session.get(GapDownEvent, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"GapDownEvent {event_id} not found.")

    row.status = "RESOLVED"
    row.resolved_at = datetime.now(tz=UTC)
    if body.rescore_score is not None:
        row.rescore_score = body.rescore_score
        row.status = "RESCORED"

    await session.commit()
    return {"ok": True}
