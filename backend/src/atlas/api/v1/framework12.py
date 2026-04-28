"""Framework 12 — Decision Matrix sizing API.

Endpoints:
  GET /api/v1/framework12/{ticker}            → Framework12Result (full)
  GET /api/v1/framework12/{ticker}/sizing     → {"size_min_usd","size_max_usd",...}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.framework12 import Framework12Result
from atlas.services.framework12_service import evaluate_framework12

router = APIRouter(prefix="/framework12", tags=["framework12"])


def _normalise(ticker: str) -> str:
    return ticker.strip().upper()


@router.get("/{ticker}", response_model=Framework12Result)
async def get_framework12(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> Framework12Result:
    """Full Framework 12 evaluation: Section 16 → Decision Matrix → USD sizing."""
    return await evaluate_framework12(_normalise(ticker), session)


@router.get("/{ticker}/sizing")
async def get_framework12_sizing(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Lightweight: just the USD sizing range and timing rule."""
    result = await evaluate_framework12(_normalise(ticker), session)
    return {
        "ticker": result.ticker,
        "status": result.status,
        "priority_code": result.matched_row.priority_code if result.matched_row else None,
        "size_min_usd": result.size_min_usd,
        "size_max_usd": result.size_max_usd,
        "timing_rule": result.timing_rule,
        "current_nav_usd": result.current_nav_usd,
        "blocked_reason": result.blocked_reason,
    }
