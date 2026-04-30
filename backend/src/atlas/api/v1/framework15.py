"""API routes for Framework 15 — VIX Regime Override.

GET  /api/v1/framework15/status          → Framework15Result (full, 60-s cache)
GET  /api/v1/framework15/status/simple   → Framework15SimpleResult (lightweight)
GET  /api/v1/framework15/vix-snapshot    → VixSnapshot (for Framework 25)
GET  /api/v1/framework15/paused-orders   → list of PausedOrder for today's session
POST /api/v1/framework15/override        → apply human override for session
PUT  /api/v1/framework15/paused-orders/{order_id}/review → review one paused order
POST /api/v1/framework15/session/reset   → reset session state (DEBUG mode only)

Architecture note:
  /status/simple is registered before /status so FastAPI doesn't
  interpret "simple" as a path variable.
  Framework 15 is portfolio-level — no {ticker} path parameter.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.decision_trace import DecisionTrace
from atlas.models.framework15_paused_order import Framework15PausedOrder
from atlas.models.framework15_session import Framework15Session
from atlas.schemas.framework15 import (
    AddOverrideRequest,
    Framework15Result,
    Framework15SimpleResult,
    OrderReviewStatus,
    PausedOrder,
    ReviewOrderRequest,
    VixSnapshot,
)
from atlas.services.framework15_service import (
    _log_decision_trace,
    cache_invalidate,
    evaluate_framework15,
    get_f15_simple,
    get_vix_snapshot,
)

router = APIRouter(prefix="/framework15", tags=["framework15"])

# Minimum override reason length (from spec).
_MIN_OVERRIDE_REASON_LEN: int = 50


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------


@router.get("/status/simple", response_model=Framework15SimpleResult)
async def get_f15_status_simple(
    session: AsyncSession = Depends(get_db_session),
) -> Framework15SimpleResult:
    """Lightweight F15 status for consuming frameworks.

    Framework 3, 4, 16, and Section 17 call this endpoint.
    They NEVER independently check VIX spike conditions.
    Cached 60 seconds — very short because intraday VIX changes every minute.
    """
    cached = get_f15_simple()
    if cached is not None:
        return cached

    result = await evaluate_framework15(session)
    return Framework15SimpleResult(
        f15_status=result.f15_status,
        f15_active=result.f15_active,
        severity=result.severity,
        new_market_orders_blocked=result.new_market_orders_blocked,
        non_stop_orders_paused=result.non_stop_orders_paused,
        data_gap_severity=result.data_gap_severity,
        market_open=result.market_open,
    )


@router.get("/status", response_model=Framework15Result)
async def get_f15_status(
    session: AsyncSession = Depends(get_db_session),
) -> Framework15Result:
    """Full Framework 15 evaluation result.

    Cached 60 seconds.  F15 is the single source of truth for f15_active.
    """
    from atlas.services.framework15_service import _cache_get

    cached = _cache_get()
    if cached is not None:
        return Framework15Result(**{**cached.model_dump(), "cache_hit": True})

    return await evaluate_framework15(session)


@router.get("/vix-snapshot", response_model=VixSnapshot)
async def get_vix_snapshot_endpoint(
    session: AsyncSession = Depends(get_db_session),
) -> VixSnapshot:
    """VIX snapshot for Framework 25 — Liquidity Protocol.

    Framework 25 reads current intraday VIX exclusively from this endpoint.
    F15 is the single source of truth for intraday VIX in the system.
    """
    snap = get_vix_snapshot()
    if snap is not None:
        return snap

    result = await evaluate_framework15(session)
    return VixSnapshot(
        current_vix=result.current_vix,
        session_open_vix=result.session_open_vix,
        spike_size=result.spike_size,
        spike_threshold=result.spike_threshold,
        f15_active=result.f15_active,
        data_available=result.polygon_available,
        market_open=result.market_open,
        last_updated=result.last_updated,
    )


@router.get("/paused-orders")
async def get_paused_orders(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return all paused orders for today's session."""
    today = date.today()
    rows_result = await session.execute(
        select(Framework15PausedOrder).where(
            Framework15PausedOrder.session_date == today
        )
    )
    rows = rows_result.scalars().all()
    orders = [
        PausedOrder(
            order_id=row.order_id,
            ticker=row.ticker,
            order_type=row.order_type,
            paused_at=row.paused_at.isoformat(),
            review_status=OrderReviewStatus(row.review_status),
        )
        for row in rows
    ]
    return {
        "session_date": today.isoformat(),
        "paused_orders": [o.model_dump() for o in orders],
        "count": len(orders),
    }


# ---------------------------------------------------------------------------
# Write routes
# ---------------------------------------------------------------------------


@router.post("/override", response_model=dict)
async def apply_override(
    body: AddOverrideRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Apply a human override for the current session halt.

    Does NOT clear f15_active — the halt alert remains visible.
    Only restores the specified order types.
    Minimum 50-character reason enforced.
    Logged to decision_trace.
    """
    if len(body.override_reason.strip()) < _MIN_OVERRIDE_REASON_LEN:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Override reason must be minimum {_MIN_OVERRIDE_REASON_LEN} "
                "characters. Please provide a detailed justification."
            ),
        )

    today = date.today()

    # Ensure a session row exists before we try to update it.
    await session.execute(
        text(
            "INSERT INTO framework15_sessions (session_date) "
            "VALUES (:sd) ON CONFLICT (session_date) DO NOTHING"
        ),
        {"sd": today},
    )

    await session.execute(
        text(
            "UPDATE framework15_sessions SET "
            "override_applied = true, "
            "override_reason = :reason, "
            "override_applied_at = NOW(), "
            "updated_at = NOW() "
            "WHERE session_date = :sd"
        ),
        {"reason": body.override_reason.strip(), "sd": today},
    )

    await _log_decision_trace(
        trigger="FRAMEWORK_15",
        signal_type="OVERRIDE",
        resolution=(
            f"Human override applied. "
            f"Restored order types: {', '.join(body.restore_order_types)}. "
            f"F15 halt alert remains active."
        ),
        human_override=True,
        override_reason=body.override_reason.strip(),
        session=session,
    )

    await session.commit()
    cache_invalidate()

    return {
        "override_applied": True,
        "session_date": today.isoformat(),
        "restore_order_types": body.restore_order_types,
        "message": (
            "Override recorded. F15 alert remains active. "
            "Specified order types restored for this session only."
        ),
    }


@router.put("/paused-orders/{order_id}/review", response_model=dict)
async def review_paused_order(
    order_id: int,
    body: ReviewOrderRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Record operator review decision for one paused order."""
    valid_decisions = {"KEEP", "MODIFY", "CANCEL"}
    decision_upper = body.decision.strip().upper()
    if decision_upper not in valid_decisions:
        raise HTTPException(
            status_code=422,
            detail=f"Decision must be one of: {', '.join(sorted(valid_decisions))}",
        )

    decision_to_status = {
        "KEEP": OrderReviewStatus.KEPT,
        "MODIFY": OrderReviewStatus.MODIFIED,
        "CANCEL": OrderReviewStatus.CANCELLED,
    }

    today = date.today()
    result = await session.execute(
        select(Framework15PausedOrder).where(
            Framework15PausedOrder.order_id == order_id,
            Framework15PausedOrder.session_date == today,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Paused order {order_id} not found for today's session.",
        )

    row.review_status = decision_to_status[decision_upper].value
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewed_by = body.reviewed_by.strip()
    row.review_decision = decision_upper

    await session.commit()

    return {
        "order_id": order_id,
        "decision": decision_upper,
        "review_status": decision_to_status[decision_upper].value,
        "reviewed_by": body.reviewed_by.strip(),
    }


@router.post("/refresh")
async def refresh_f15(
    session: AsyncSession = Depends(get_db_session),
) -> Framework15Result:
    """Invalidate cache and re-evaluate Framework 15."""
    cache_invalidate()
    return await evaluate_framework15(session)


@router.post("/session/reset")
async def reset_session(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Reset F15 session state for the current day.

    RESTRICTED TO DEBUG / DEVELOPMENT MODE ONLY.
    Not available in production (ENVIRONMENT != 'development').
    """
    from atlas.config import get_settings

    settings = get_settings()
    if settings.environment.lower() not in {"development", "debug", "test"}:
        raise HTTPException(
            status_code=403,
            detail="Session reset is only available in development/debug mode.",
        )

    today = date.today()

    await session.execute(
        text(
            "DELETE FROM framework15_paused_orders WHERE session_date = :sd"
        ),
        {"sd": today},
    )
    await session.execute(
        text("DELETE FROM framework15_sessions WHERE session_date = :sd"),
        {"sd": today},
    )

    # Restore any orders that were paused to OPEN status.
    await session.execute(
        text(
            "UPDATE gtc_orders SET status = 'OPEN', updated_at = NOW() "
            "WHERE status = 'PAUSED_F15'"
        )
    )

    await session.commit()
    cache_invalidate()

    return {"reset": True, "session_date": today.isoformat()}
