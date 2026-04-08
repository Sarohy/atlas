"""API routes for portfolio summary and cash management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.portfolio import (
    CashResponse,
    CashUpdateRequest,
    PortfolioSummaryResponse,
)
from atlas.services.portfolio_service import PortfolioService, compute_portfolio_summary
from atlas.services.ticker_service import TickerService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioSummaryResponse:
    """Return the computed portfolio summary (NAV, cash breakdown, beta, deployable)."""
    ticker_svc = TickerService(session)
    portfolio_svc = PortfolioService(session)
    tickers = await ticker_svc.list_tickers()
    config = await portfolio_svc.get_or_create_config()
    return compute_portfolio_summary(tickers, config)


@router.get("/cash", response_model=CashResponse)
async def get_cash(
    session: AsyncSession = Depends(get_db_session),
) -> CashResponse:
    """Return the current cash balance and floor percentage."""
    svc = PortfolioService(session)
    config = await svc.get_or_create_config()
    return config  # type: ignore[return-value]


@router.put("/cash", response_model=CashResponse)
async def update_cash(
    data: CashUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CashResponse:
    """Update the portfolio cash balance and floor percentage."""
    svc = PortfolioService(session)
    config = await svc.update_cash(data)
    return config  # type: ignore[return-value]
