"""API route for Framework 5 — Cash Floor.

Endpoints
---------
GET /api/v1/cash-floor/status      Portfolio-level cash floor status (new).
GET /api/v1/cash-floor/{ticker}    Legacy per-ticker endpoint (backward compat).

The portfolio-level endpoint is registered before the parameterised route so
that ``/status`` is not captured as a ticker symbol.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.cash_floor import CashFloorResponse, Framework5Response
from atlas.services.cash_floor_service import CashFloorService

router = APIRouter(prefix="/cash-floor", tags=["cash-floor"])


def _build_service(session: AsyncSession) -> CashFloorService:
    """Construct CashFloorService from current settings."""
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cash Floor unavailable: POLYGON_API_KEY is not configured. "
                "This key is required for Brent crude, VIX, and Framework 2 data."
            ),
        )
    return CashFloorService(
        polygon_api_key=settings.polygon_api_key,
        alphavantage_api_key=settings.alphavantage_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
        session=session,
    )


# ── Portfolio-level endpoint — must be registered before /{ticker} ──────────


@router.get("/status", response_model=Framework5Response)
async def get_framework5_status(
    session: AsyncSession = Depends(get_db_session),
) -> Framework5Response:
    """Return the Framework 5 portfolio-level cash floor status.

    Reads the live Framework 2 regime (Brent + VIX) and derives the
    applicable cash floor for the entire portfolio.  No ticker required.

    Returns 503 when POLYGON_API_KEY is not configured.
    """
    service = _build_service(session)
    return await service.compute_portfolio_floor()


# ── Legacy per-ticker endpoint ───────────────────────────────────────────────


@router.get("/{ticker}", response_model=CashFloorResponse)
async def get_cash_floor(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> CashFloorResponse:
    """Return Framework 5 cash-floor guidance for ``ticker`` (legacy endpoint).

    Returns 503 when POLYGON_API_KEY is not configured.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = _build_service(session)
    return await service.compute_cash_floor(normalised)
