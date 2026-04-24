"""API routes for Framework 19 — NVDA Kill Switch.

GET  /api/v1/framework19/status/simple      → Framework19SimpleResult (lightweight)
GET  /api/v1/framework19/status             → Framework19Result (full, NO CACHE)
GET  /api/v1/framework19/paused-orders      → today's paused orders
GET  /api/v1/framework19/history            → last 30 days session records
PUT  /api/v1/framework19/paused-orders/{id}/review → human review decision

Architecture notes:
  /status/simple is registered BEFORE /status so FastAPI does not
  interpret "simple" as a path variable.

  Framework 19 is portfolio-level — no {ticker} path parameter.

  ZERO CACHING: Every call to GET /status makes a fresh Polygon.io request.
  This is the hard invariant for F19 — NVDA kill-switch must always reflect
  the most recent price data.

  Consuming frameworks (F3 Score Action Map, F4 Tranche Deployment) call
  get_f19_simple() from the service directly (async DB read), not this endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytz
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.framework19_paused_order import Framework19PausedOrder
from atlas.models.framework19_session import Framework19Session
from atlas.schemas.framework19 import (
    Framework19Result,
    Framework19SimpleResult,
    OrderReviewStatus,
    PausedOrder,
    ReviewOrderRequest,
)
from atlas.services.framework19_service import (
    evaluate_framework19,
    get_f19_simple,
)

router = APIRouter(prefix="/framework19", tags=["framework19"])

# Eastern Time timezone (used for date boundary queries).
_ET_TZ = pytz.timezone("America/New_York")


# ---------------------------------------------------------------------------
# Status endpoints
# ---------------------------------------------------------------------------


@router.get("/status/simple", response_model=Framework19SimpleResult)
async def get_f19_status_simple(
    session: AsyncSession = Depends(get_db_session),
) -> Framework19SimpleResult:
    """Lightweight F19 status — reads today's session row from DB.

    No Polygon.io call.  Returns immediately from DB state.
    Consuming frameworks (F3, F4) call this to check kill-switch state.
    ZERO caching — DB reads are fast and always current.
    """
    return await get_f19_simple(session)


@router.get("/status", response_model=Framework19Result)
async def get_f19_status(
    session: AsyncSession = Depends(get_db_session),
) -> Framework19Result:
    """Full Framework 19 evaluation — ALWAYS makes a fresh Polygon.io request.

    ZERO CACHING.  Every request calls Polygon.io.
    Never returns stale NVDA price data.
    This is intentional — the kill switch must be as reactive as possible.
    """
    return await evaluate_framework19(session)


# ---------------------------------------------------------------------------
# Paused orders
# ---------------------------------------------------------------------------


@router.get("/paused-orders", response_model=list[PausedOrder])
async def get_paused_orders(
    session: AsyncSession = Depends(get_db_session),
) -> list[PausedOrder]:
    """Return today's paused orders for human review.

    Scoped to today's session date (ET clock).
    Returns an empty list if no orders were paused today.
    """
    today = datetime.now(_ET_TZ).date()
    result = await session.execute(
        select(Framework19PausedOrder)
        .where(Framework19PausedOrder.session_date == today)
        .order_by(Framework19PausedOrder.paused_at)
    )
    rows = result.scalars().all()
    return [
        PausedOrder(
            order_id=po.order_id,
            ticker=po.ticker,
            order_type=po.order_type,
            beta_vs_nvda=float(po.beta_vs_nvda) if po.beta_vs_nvda is not None else None,
            is_high_beta=po.is_high_beta,
            paused_at=po.paused_at.isoformat() if po.paused_at else "",
            review_status=OrderReviewStatus(po.review_status)
            if po.review_status in OrderReviewStatus._value2member_map_
            else OrderReviewStatus.PENDING_REVIEW,
        )
        for po in rows
    ]


@router.put("/paused-orders/{paused_order_id}/review", response_model=PausedOrder)
async def review_paused_order(
    paused_order_id: int,
    body: ReviewOrderRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PausedOrder:
    """Record a human review decision for a paused order.

    Decision must be one of: KEPT | MODIFIED | CANCELLED.
    This is the safety-critical confirmation flow required by ATLAS spec.
    Once reviewed, the review_status changes from PENDING_REVIEW to the decision.
    """
    result = await session.execute(
        select(Framework19PausedOrder).where(Framework19PausedOrder.id == paused_order_id)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Paused order {paused_order_id} not found.",
        )

    row.review_status = body.decision
    row.reviewed_at = datetime.now(pytz.utc)
    row.reviewed_by = body.reviewed_by
    row.review_decision = body.decision

    await session.commit()
    await session.refresh(row)

    return PausedOrder(
        order_id=row.order_id,
        ticker=row.ticker,
        order_type=row.order_type,
        beta_vs_nvda=float(row.beta_vs_nvda) if row.beta_vs_nvda is not None else None,
        is_high_beta=row.is_high_beta,
        paused_at=row.paused_at.isoformat() if row.paused_at else "",
        review_status=OrderReviewStatus(row.review_status)
        if row.review_status in OrderReviewStatus._value2member_map_
        else OrderReviewStatus.PENDING_REVIEW,
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/history", response_model=list[dict[str, Any]])
async def get_f19_history(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Return last 30 calendar days of F19 session records.

    Each row represents a single trading day.
    Days with no row (weekends, holidays) are excluded automatically.
    """
    result = await session.execute(
        select(Framework19Session)
        .order_by(Framework19Session.session_date.desc())
        .limit(30)
    )
    rows = result.scalars().all()
    return [
        {
            "session_date": str(row.session_date),
            "f19_triggered": row.f19_triggered,
            "triggered_at": row.triggered_at.isoformat() if row.triggered_at else None,
            "nvda_price_at_trigger": (
                float(row.nvda_price_at_trigger) if row.nvda_price_at_trigger else None
            ),
            "nvda_drop_pct": float(row.nvda_drop_pct) if row.nvda_drop_pct else None,
            "drop_window_minutes": row.drop_window_minutes,
            "orders_paused_count": row.orders_paused_count,
            "regime_at_trigger": row.regime_at_trigger,
            "alert_sent_at": row.alert_sent_at.isoformat() if row.alert_sent_at else None,
        }
        for row in rows
    ]
