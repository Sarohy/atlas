"""API routes for Framework 30 — Max Drawdown Gate.

GET  /api/v1/framework30/drawdown         → Framework30Result (full evaluation)
GET  /api/v1/framework30/drawdown/state   → Framework30DrawdownState (lightweight)
POST /api/v1/framework30/hard-halt/confirm → confirm or rescind hard halt
POST /api/v1/framework30/refresh          → clear cache + re-evaluate
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.framework30 import (
    Framework30DrawdownState,
    Framework30Result,
    HardHaltConfirmRequest,
)
from atlas.services.framework30_service import (
    _cache_invalidate,
    evaluate_framework30,
    get_drawdown_state,
    set_hard_halt_confirmed,
)

router = APIRouter(prefix="/framework30", tags=["framework30"])


@router.get("/drawdown", response_model=Framework30Result)
async def get_framework30_drawdown(
    session: AsyncSession = Depends(get_db_session),
) -> Framework30Result:
    """Return the full Framework 30 drawdown evaluation."""
    settings = get_settings()
    return await evaluate_framework30(
        session=session,
        polygon_api_key=settings.polygon_api_key,
        refresh_prices=False,
    )


@router.get("/drawdown/state", response_model=Framework30DrawdownState)
async def get_framework30_drawdown_state(
    session: AsyncSession = Depends(get_db_session),
) -> Framework30DrawdownState:
    """Return lightweight drawdown state from cache.  Triggers full evaluation if empty."""
    cached = get_drawdown_state()
    if cached is not None:
        return cached

    # Nothing in cache — run a full evaluation.
    settings = get_settings()
    result = await evaluate_framework30(
        session=session,
        polygon_api_key=settings.polygon_api_key,
        refresh_prices=False,
    )
    return Framework30DrawdownState(
        drawdown_state=result.drawdown_state,
        drawdown_pct=result.drawdown_pct,
        adds_permitted=result.adds_permitted,
        leaps_permitted=result.leaps_permitted,
        leaps_position_cap_pct=result.leaps_position_cap_pct,
        sizing_multiplier=result.sizing_multiplier,
        hard_halt_active=result.hard_halt_active,
        data_complete=result.nav_data_complete,
    )


@router.post("/hard-halt/confirm")
async def confirm_hard_halt(
    body: HardHaltConfirmRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    """Manually confirm or rescind a hard halt.

    This is a human-in-the-loop safeguard.  A confirmed hard halt reinforces
    the HARD_HALT state even if drawdown briefly recovers.  Use confirmed=False
    to rescind a previously set confirmation.
    """
    if not body.reason or len(body.reason.strip()) < 5:
        raise HTTPException(
            status_code=422,
            detail="A meaningful reason (min 5 characters) is required for hard-halt confirmation.",
        )
    set_hard_halt_confirmed(confirmed=body.confirmed, reason=body.reason)
    return {
        "ok": True,
        "confirmed": body.confirmed,
        "message": (
            "Hard halt confirmed. Cache invalidated."
            if body.confirmed
            else "Hard halt rescinded. Cache invalidated."
        ),
    }


@router.post("/refresh", response_model=Framework30Result)
async def refresh_framework30(
    session: AsyncSession = Depends(get_db_session),
) -> Framework30Result:
    """Clear the in-memory cache and re-evaluate drawdown with fresh prices."""
    settings = get_settings()
    _cache_invalidate()
    return await evaluate_framework30(
        session=session,
        polygon_api_key=settings.polygon_api_key,
        refresh_prices=True,
    )
