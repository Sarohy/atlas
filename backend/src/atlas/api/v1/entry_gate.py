"""Entry Gate API — unified Section 16 + Framework 12 endpoint.

Endpoint:
  GET /api/v1/entry-gate/{ticker}  →  EntryGateResult

Returns both Section 16 and Framework 12 evaluations in one response so the
frontend never needs to make two separate requests for the same ticker.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.entry_gate import EntryGateResult
from atlas.services.entry_gate_service import evaluate_entry_gate

router = APIRouter(prefix="/entry-gate", tags=["entry-gate"])


def _normalise(ticker: str) -> str:
    return ticker.strip().upper()


@router.get("/{ticker}", response_model=EntryGateResult)
async def get_entry_gate(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> EntryGateResult:
    """Unified entry-gate evaluation: Section 16 → Framework 12 in one call."""
    return await evaluate_entry_gate(_normalise(ticker), session)
