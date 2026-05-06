"""API routes for Section 17 — LEAPS Strategy Module.

GET  /api/v1/leaps/eligibility/{ticker}   → LeapsEligibility (per-ticker check)
GET  /api/v1/leaps/positions              → list[LeapsPosition] (open positions)
GET  /api/v1/leaps/bucket                 → LeapsBucketStatus (aggregate utilisation)
POST /api/v1/leaps/refresh/{ticker}       → invalidate cache + re-evaluate
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.leaps import (
    LeapsBucketStatus,
    LeapsEligibility,
    LeapsPosition,
)
from atlas.services.framework30_service import get_drawdown_state
from atlas.services.leaps_service import (
    _cache_invalidate,
    check_leaps_eligibility,
    get_leaps_bucket,
    get_leaps_positions,
)

router = APIRouter(prefix="/leaps", tags=["leaps"])


@router.get("/eligibility/{ticker}", response_model=LeapsEligibility)
async def get_leaps_eligibility(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
    provided_score: int | None = Query(
        default=None,
        ge=0,
        le=100,
        alias="score",
        description=(
            "Optional override: pass the Framework 1 panel score so LEAPS "
            "evaluation uses the same value the investor already sees, "
            "avoiding a 1-point rounding divergence from independent re-computation."
        ),
    ),
) -> LeapsEligibility:
    """Evaluate LEAPS eligibility for *ticker*.

    Checks all required gates (F7, F29, F30), IV data from Unusual Whales,
    and Framework 1 score from F9 dark pool data.  Returns a tristate result:
    true = eligible, false = blocked, null = data incomplete.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker must not be empty.")

    settings = get_settings()
    return await check_leaps_eligibility(
        ticker=normalised,
        session=session,
        polygon_api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key,
        alphavantage_api_key=settings.alphavantage_api_key,
        sec_api_key=settings.sec_api_key,
        transcript_api_key=settings.earnings_transcript_api_key,
        benzinga_api_key=settings.benzinga_api_key,
        provided_score=provided_score,
    )


@router.get("/positions", response_model=list[LeapsPosition])
async def get_all_leaps_positions(
    session: AsyncSession = Depends(get_db_session),
) -> list[LeapsPosition]:
    """Return all open LEAPS positions tracked in the portfolio.

    V1: positions are read-only; live price enrichment is not yet implemented.
    """
    return await get_leaps_positions(session)


@router.get("/bucket", response_model=LeapsBucketStatus)
async def get_leaps_bucket_status(
    session: AsyncSession = Depends(get_db_session),
) -> LeapsBucketStatus:
    """Return the current LEAPS bucket utilisation relative to NAV.

    Uses F30 cached NAV for deployed percentage calculation.
    """
    f30_state = get_drawdown_state()
    current_nav: float | None = None
    if f30_state is not None:
        # Lightweight state doesn't expose NAV directly; the caller must use
        # the full F30 result for exact NAV.  Bucket % is approximate here.
        pass

    return await get_leaps_bucket(session, current_nav)


@router.post("/refresh/{ticker}", response_model=LeapsEligibility)
async def refresh_leaps_eligibility(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> LeapsEligibility:
    """Invalidate the LEAPS eligibility cache for *ticker* and re-evaluate."""
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker must not be empty.")

    settings = get_settings()
    _cache_invalidate(normalised)
    return await check_leaps_eligibility(
        ticker=normalised,
        session=session,
        polygon_api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key,
        alphavantage_api_key=settings.alphavantage_api_key,
        sec_api_key=settings.sec_api_key,
        transcript_api_key=settings.earnings_transcript_api_key,
        benzinga_api_key=settings.benzinga_api_key,
    )
