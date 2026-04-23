"""API routes for Framework 6 - Conviction Action (v7.3.4 Watchlist Tier Structure).

GET  /api/v1/conviction-action/{ticker}[?adjusted_score={n}]
POST /api/v1/conviction-action/{ticker}/consensus
POST /api/v1/conviction-action/{ticker}/exit-cycle?score={n}

Tier assignment (v7.3.4)::

  score >= 85  -> TIER_1_CORE  : 3-5% NAV - LEAPS eligible, add on dips
  78-84        -> GREY_ZONE    : 1.5-2.5% - 3-AI consensus required
  70-77        -> TIER_2       : 0.5-1.5% - GTC adds permitted
  55-69        -> TIER_3       : 0.25-0.5% - Satellite only
  below 55     -> WATCHLIST    : 0% - No capital, monitor, exit rule triggers

Returns 503 when POLYGON_API_KEY is not configured.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.conviction_action import (
    ConsensusUpdateRequest,
    ConvictionActionResponse,
    ExitCycleResponse,
)
from atlas.services.conviction_action_service import ConvictionActionService

router = APIRouter(prefix="/conviction-action", tags=["conviction-action"])

# ---------------------------------------------------------------------------
# Shared builder
# ---------------------------------------------------------------------------


def _build_service(session: AsyncSession) -> ConvictionActionService:
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Conviction Action unavailable: POLYGON_API_KEY is not configured. "
                "This key is required for Framework Score and Regime Modifier data."
            ),
        )
    return ConvictionActionService(
        polygon_api_key=settings.polygon_api_key,
        alphavantage_api_key=settings.alphavantage_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
        session=session,
    )


# ---------------------------------------------------------------------------
# GET /{ticker}
# ---------------------------------------------------------------------------


@router.get("/{ticker}", response_model=ConvictionActionResponse)
async def get_conviction_action(
    ticker: str,
    adjusted_score: float | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> ConvictionActionResponse:
    """Return the Framework 6 conviction-action guidance for *ticker*.

    Pass ``adjusted_score`` (the score already displayed by the F1 panel --
    i.e. ``final_score + regime_modifier``, clamped 0-100) to skip the
    regime service and prevent the modifier from being applied twice.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")
    service = _build_service(session)
    return await service.compute_conviction_action(
        normalised, provided_adjusted_score=adjusted_score
    )


# ---------------------------------------------------------------------------
# POST /{ticker}/consensus
# ---------------------------------------------------------------------------


@router.post("/{ticker}/consensus", response_model=ConvictionActionResponse)
async def update_consensus(
    ticker: str,
    body: ConsensusUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ConvictionActionResponse:
    """Set the 3-AI consensus status for *ticker* (GREY_ZONE only).

    Body: ``{"status": "CONFIRMED" | "FAILED" | "PENDING"}``

    After updating the in-memory consensus store, returns the full updated
    Framework 6 result.  For a non-GREY_ZONE ticker the consensus field will
    always be NOT_REQUIRED regardless of what was stored.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")
    service = _build_service(session)
    return await service.update_consensus(normalised, body)


# ---------------------------------------------------------------------------
# POST /{ticker}/exit-cycle
# ---------------------------------------------------------------------------


@router.post("/{ticker}/exit-cycle", response_model=ExitCycleResponse)
async def record_exit_cycle(
    ticker: str,
    score: float,
    session: AsyncSession = Depends(get_db_session),
) -> ExitCycleResponse:
    """Update the Friday-close exit cycle counter for *ticker*.

    Call once per Friday close with the current ``score``.
      • score < 55 → increment counter
      • score ≥ 55 → reset counter to 0

    Returns ``exit_cycle_count`` and ``exit_triggered`` (True after 2 consecutive
    closes below 55).  Framework 6 only flags the trigger — execution belongs
    to Framework 16.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")
    service = _build_service(session)
    return await service.record_exit_cycle(normalised, score)
