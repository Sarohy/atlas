"""API routes for Framework 12 — Catalyst No-Fly Zone.

GET  /api/v1/framework12/{ticker}              → Framework12Result (full, 5-min cache)
GET  /api/v1/framework12/{ticker}/status       → Framework12StatusResult (lightweight)
GET  /api/v1/framework12/portfolio/summary     → Framework12PortfolioSummary
POST /api/v1/framework12/catalysts             → CatalystResponse (add non-earnings catalyst)
PUT  /api/v1/framework12/catalysts/{id}/deactivate → CatalystResponse
POST /api/v1/framework12/{ticker}/override     → OverrideDetail (human override for one action)
POST /api/v1/framework12/refresh/{ticker}      → Framework12Result (clears cache, re-evaluates)
POST /api/v1/framework12/refresh/all           → {"cleared": int}

Architecture note: the /portfolio/summary route is registered BEFORE the
/{ticker} routes so FastAPI does not interpret "portfolio" as a ticker symbol.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.catalyst_event import CatalystEvent
from atlas.models.decision_trace import DecisionTrace
from atlas.models.framework12_override import Framework12Override
from atlas.schemas.framework12 import (
    AddCatalystRequest,
    AddOverrideRequest,
    CatalystResponse,
    Framework12PortfolioSummary,
    Framework12Result,
    Framework12StatusResult,
    OverrideDetail,
)
from atlas.services.framework12_service import (
    _cache,
    cache_invalidate,
    cache_invalidate_all,
    evaluate_framework12,
    evaluate_portfolio_summary,
)

router = APIRouter(prefix="/framework12", tags=["framework12"])


# ---------------------------------------------------------------------------
# Portfolio-level routes (must come before /{ticker} routes)
# ---------------------------------------------------------------------------


@router.get("/portfolio/summary", response_model=Framework12PortfolioSummary)
async def get_portfolio_summary(
    session: AsyncSession = Depends(get_db_session),
) -> Framework12PortfolioSummary:
    """Return Framework 12 status for all held tickers — morning briefing overview."""
    return await evaluate_portfolio_summary(session)


@router.post("/refresh/all")
async def refresh_all(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Invalidate the in-memory cache for ALL tickers."""
    count = len(_cache)
    cache_invalidate_all()
    return {"cleared": count}


@router.post("/catalysts", response_model=CatalystResponse)
async def add_catalyst(
    body: AddCatalystRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CatalystResponse:
    """Operator adds a new non-earnings catalyst to the DB.

    EARNINGS catalysts are owned by Framework 7 — do not submit EARNINGS here.
    """
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="ticker must not be empty.")

    # Parse and validate the date string.
    try:
        from datetime import date
        parsed_date = date.fromisoformat(body.catalyst_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"catalyst_date '{body.catalyst_date}' must be YYYY-MM-DD.",
        )

    # Reject EARNINGS — Framework 7 is the single source of truth for earnings.
    if body.catalyst_type.upper() == "EARNINGS":
        raise HTTPException(
            status_code=422,
            detail=(
                "EARNINGS catalysts are owned by Framework 7 — "
                "do not enter them here.  They are fetched automatically."
            ),
        )

    event = CatalystEvent(
        ticker=ticker,
        catalyst_type=body.catalyst_type.upper(),
        catalyst_date=parsed_date,
        description=body.description,
        status="ACTIVE",
        entered_by=body.entered_by,
    )
    session.add(event)
    await session.flush()

    # Invalidate cache so next GET picks up the new catalyst.
    cache_invalidate(ticker)

    return CatalystResponse(
        id=event.id,
        ticker=event.ticker,
        catalyst_type=event.catalyst_type,
        catalyst_date=event.catalyst_date.isoformat(),
        description=event.description,
        status=event.status,
        entered_by=event.entered_by,
    )


@router.put("/catalysts/{catalyst_id}/deactivate", response_model=CatalystResponse)
async def deactivate_catalyst(
    catalyst_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> CatalystResponse:
    """Mark a catalyst event as PASSED (operator deactivates after event passes)."""
    result = await session.execute(
        select(CatalystEvent).where(CatalystEvent.id == catalyst_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail=f"Catalyst {catalyst_id} not found.")

    event.status = "PASSED"
    await session.flush()

    cache_invalidate(event.ticker)

    return CatalystResponse(
        id=event.id,
        ticker=event.ticker,
        catalyst_type=event.catalyst_type,
        catalyst_date=event.catalyst_date.isoformat(),
        description=event.description,
        status=event.status,
        entered_by=event.entered_by,
    )


# ---------------------------------------------------------------------------
# Per-ticker routes
# ---------------------------------------------------------------------------


@router.get("/{ticker}", response_model=Framework12Result)
async def get_framework12(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Framework12Result:
    """Return the full Framework 12 no-fly zone evaluation for *ticker*."""
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker must not be empty.")
    return await evaluate_framework12(normalised, session)


@router.get("/{ticker}/status", response_model=Framework12StatusResult)
async def get_framework12_status(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Framework12StatusResult:
    """Return the lightweight no-fly status for *ticker*.

    Called by Framework 3 and Section 16 — uses the same evaluation with
    cache, so multiple consumers do not trigger duplicate F7 calls.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker must not be empty.")

    full = await evaluate_framework12(normalised, session)
    return Framework12StatusResult(
        no_fly_status=full.no_fly_status,
        no_fly_active=full.no_fly_active,
        covered_calls_status=full.covered_calls_status,
        partial_sells_status=full.partial_sells_status,
        trims_status=full.trims_status,
        nearest_catalyst_date=(
            full.nearest_catalyst.catalyst_date if full.nearest_catalyst else None
        ),
        nearest_catalyst_type=(
            full.nearest_catalyst.catalyst_type if full.nearest_catalyst else None
        ),
        days_to_catalyst=(
            full.nearest_catalyst.days_to_catalyst if full.nearest_catalyst else None
        ),
        exit_rule_deferred=full.exit_rule_deferred,
        exit_rule_deferred_until=full.exit_rule_deferred_until,
        data_gap_severity=full.data_gap_severity,
    )


@router.post("/{ticker}/override", response_model=OverrideDetail)
async def add_override(
    ticker: str,
    body: AddOverrideRequest,
    session: AsyncSession = Depends(get_db_session),
) -> OverrideDetail:
    """Apply a human override for one specific blocked action on *ticker*.

    Overrides are action-specific — submitting one for COVERED_CALL does not
    unblock PARTIAL_SELL or TRIM.

    Requires a non-empty written reason.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker must not be empty.")

    valid_actions = {"COVERED_CALL", "PARTIAL_SELL", "TRIM"}
    action = body.action_type.upper()
    if action not in valid_actions:
        raise HTTPException(
            status_code=422,
            detail=f"action_type must be one of {sorted(valid_actions)}.",
        )

    if not body.override_reason.strip():
        raise HTTPException(
            status_code=422,
            detail="override_reason must not be empty.",
        )

    if body.override_duration_hours <= 0:
        raise HTTPException(
            status_code=422,
            detail="override_duration_hours must be a positive integer.",
        )

    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(hours=body.override_duration_hours)

    override = Framework12Override(
        ticker=normalised,
        action_type=action,
        override_reason=body.override_reason.strip(),
        override_active=True,
        override_expires_at=expires_at,
        entered_by=body.entered_by,
    )
    session.add(override)

    # Log to Decision Trace — overrides are always visible in morning briefing.
    trace = DecisionTrace(
        timestamp_utc=now,
        trigger="FRAMEWORK_12_OVERRIDE",
        signal_type="OVERRIDE",
        ticker=normalised,
        human_override=True,
        override_reason=body.override_reason.strip(),
        override_action=action,
        resolution=f"OVERRIDE — human approved: {action} unblocked until {expires_at.isoformat()}",
        visible_in_briefing=True,
    )
    session.add(trace)
    await session.flush()

    # Invalidate cache so next GET shows updated status.
    cache_invalidate(normalised)

    return OverrideDetail(
        action_type=action,
        override_reason=body.override_reason.strip(),
        entered_by=body.entered_by,
        created_at=override.created_at.isoformat() if override.created_at else now.isoformat(),
        override_expires_at=expires_at.isoformat(),
    )


@router.post("/refresh/{ticker}", response_model=Framework12Result)
async def refresh_ticker(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Framework12Result:
    """Clear the in-memory cache for *ticker* and re-evaluate fresh."""
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker must not be empty.")
    cache_invalidate(normalised)
    return await evaluate_framework12(normalised, session)
