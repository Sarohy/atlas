"""API routes for Framework 17 — Geopolitical Monitor.

GET  /api/v1/framework17/status          → Framework17Result (full, 60-s cache)
GET  /api/v1/framework17/flag            → simplified flag only (lightweight for F2)
POST /api/v1/framework17/flag            → set flag (operator only)
GET  /api/v1/framework17/history         → last N days flag history

Architecture note:
  /flag (GET/POST) is registered before /history so FastAPI doesn't
  interpret route segments as path variables.
  Framework 17 is portfolio-level — no {ticker} path parameter.

After POST /flag:
  - Writes a row to geopolitical_flag table.
  - Logs decision trace (append-only).
  - Invalidates F17, F27, F28 caches.
  - Triggers Framework 2 regime refresh via POST to /api/v1/regime-modifier/refresh.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.geopolitical_flag import GeopoliticalFlag
from atlas.schemas.framework17 import (
    FlagHistoryEntry,
    Framework17Result,
    Framework17SimpleResult,
    GeoFlagState,
    SetFlagRequest,
)
from atlas.services.framework17_service import (
    _log_decision_trace,
    cache_invalidate,
    evaluate_framework17,
    get_f17_simple,
)
from atlas.services.framework27_service import cache_invalidate as f27_cache_invalidate
from atlas.services.framework28_service import cache_invalidate as f28_cache_invalidate

router = APIRouter(prefix="/framework17", tags=["framework17"])

# Default number of history days to return.
_DEFAULT_HISTORY_DAYS: int = 30

# Minimum override reason length (matches F15 pattern).
_MIN_OVERRIDE_REASON_LEN: int = 50

# Framework 2 refresh endpoint — called after every flag change.
_F2_REFRESH_PATH: Final[str] = "/api/v1/regime-modifier/refresh"

from typing import Final


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------


@router.get("/flag", response_model=Framework17SimpleResult)
async def get_f17_flag(
    session: AsyncSession = Depends(get_db_session),
) -> Framework17SimpleResult:
    """Lightweight F17 flag status.

    Framework 2, 3, and 7 call this endpoint instead of re-reading the DB.
    Returns a cached 60-second result (framework17_service cache).
    """
    simple = get_f17_simple()
    if simple is not None:
        return simple

    result = await evaluate_framework17(session)
    return Framework17SimpleResult(
        f17_active=result.f17_active,
        flag_state=result.flag_state,
        clear_regime_possible=result.clear_regime_possible,
        severity=result.severity,
        brent_price=result.brent_price,
        conflict_duration_days=result.conflict_duration_days,
    )


@router.get("/status", response_model=Framework17Result)
async def get_f17_status(
    session: AsyncSession = Depends(get_db_session),
) -> Framework17Result:
    """Full Framework 17 evaluation result (60-second cache)."""
    from atlas.services.framework17_service import _cache_get

    cached = _cache_get()
    if cached is not None:
        return Framework17Result(**{**cached.model_dump(), "cache_hit": True})

    return await evaluate_framework17(session)


@router.get("/history", response_model=list[FlagHistoryEntry])
async def get_f17_history(
    days: int = _DEFAULT_HISTORY_DAYS,
    session: AsyncSession = Depends(get_db_session),
) -> list[FlagHistoryEntry]:
    """Return flag history for the last N days (default 30).

    Returns rows ordered by session_date DESC, set_at DESC.
    """
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=422,
            detail="days parameter must be between 1 and 365.",
        )

    from datetime import timedelta

    cutoff = date.today() - timedelta(days=days)

    stmt = (
        select(GeopoliticalFlag)
        .where(GeopoliticalFlag.session_date >= cutoff)
        .order_by(
            GeopoliticalFlag.session_date.desc(),
            GeopoliticalFlag.set_at.desc(),
        )
    )
    rows = (await session.execute(stmt)).scalars().all()

    return [
        FlagHistoryEntry(
            id=row.id,
            flag_state=GeoFlagState(row.flag_state),
            set_by=row.set_by,
            set_at=row.set_at,
            conflict_start_date=row.conflict_start_date,
            notes=row.notes,
            session_date=row.session_date,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Write routes
# ---------------------------------------------------------------------------


@router.post("/flag", response_model=Framework17Result, status_code=201)
async def set_f17_flag(
    body: SetFlagRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Framework17Result:
    """Set the geopolitical flag (operator only).

    Validation:
      - NOT_SET is not accepted as flag_state input.
      - override_reason must be at least 50 characters.
      - ACTIVE flag without conflict_start_date shows a warning but is accepted.

    After writing:
      - Logs to decision_trace (append-only).
      - Invalidates F17, F27, F28 caches.
      - Calls POST /api/v1/regime-modifier/refresh to sync Framework 2.
    """
    if body.flag_state == GeoFlagState.NOT_SET:
        raise HTTPException(
            status_code=422,
            detail="NOT_SET is not a valid input flag_state. "
            "Use NONE, DE_ESCALATING, or ACTIVE.",
        )

    if len(body.override_reason.strip()) < _MIN_OVERRIDE_REASON_LEN:
        raise HTTPException(
            status_code=422,
            detail=(
                f"override_reason must be at least {_MIN_OVERRIDE_REASON_LEN} characters. "
                f"Provided: {len(body.override_reason.strip())} characters."
            ),
        )

    # Write flag row.
    new_flag = GeopoliticalFlag(
        flag_state=body.flag_state.value,
        set_by=body.set_by,
        set_at=datetime.now(timezone.utc),
        conflict_start_date=body.conflict_start_date,
        notes=body.notes,
        session_date=date.today(),
    )
    session.add(new_flag)

    # Log decision trace (append-only).
    await _log_decision_trace(
        trigger="FRAMEWORK_17",
        signal_type="GEO_FLAG_SET",
        resolution=(
            f"Operator {body.set_by!r} set geopolitical flag to "
            f"{body.flag_state.value}. "
            f"Reason: {body.override_reason.strip()}"
        ),
        human_override=True,
        override_reason=body.override_reason.strip(),
        session=session,
    )

    # Flush to DB before cache invalidation.
    await session.flush()

    # Invalidate all affected caches.
    cache_invalidate()
    f27_cache_invalidate()
    f28_cache_invalidate()

    # Trigger F2 regime refresh (best-effort — do not fail if F2 is down).
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"http://localhost:8000{_F2_REFRESH_PATH}",
                timeout=3.0,
            )
    except Exception as exc:
        # Non-blocking — log and continue.
        import logging

        logging.getLogger(__name__).warning(
            "F17: F2 regime refresh call failed",
            extra={"error": repr(exc)},
        )

    # Return fresh evaluation.
    return await evaluate_framework17(session)
