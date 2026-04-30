"""FastAPI router for Framework 13 — Beta-Adjusted Portfolio Management.

Endpoints
---------
GET  /api/v1/framework13/{ticker}
    Evaluate beta cap for a single ticker position.

GET  /api/v1/framework13/portfolio/beta
    Calculate weighted-average and effective beta across all held positions.

GET  /api/v1/framework13/beta/{ticker}
    Quick beta lookup: returns just beta value and source.
    Consumed by other frameworks (e.g. Framework 4) for fast cap checks.

``position_weight_override`` and ``nav_override`` query params allow test
callers to bypass live DB queries (same pattern as framework14 router).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.portfolio_config import PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.framework13 import Framework13Result, PortfolioBetaResult
from atlas.services.framework13_service import (
    calculate_portfolio_beta,
    evaluate_framework13,
    get_beta,
)

router = APIRouter(prefix="/framework13", tags=["framework13"])

# Minimum length for a valid ticker string
_TICKER_MIN_LEN: int = 1

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_position_weight_and_nav(
    ticker: str,
    session: AsyncSession,
) -> tuple[float, float]:
    """Return (position_weight_fraction, total_nav_dollars) from live DB.

    Returns (0.0, 0.0) when the ticker is not in the portfolio or NAV is zero.
    """
    total_invested_result = await session.execute(select(func.sum(Ticker.position_value)))
    total_invested: float = float(total_invested_result.scalar() or 0.0)

    cash_result = await session.execute(select(PortfolioConfig.cash_balance).limit(1))
    cash_balance: float = float(cash_result.scalar() or 0.0)

    total_nav = total_invested + cash_balance
    if total_nav == 0.0:
        return 0.0, 0.0

    ticker_result = await session.execute(
        select(Ticker.position_value).where(Ticker.ticker == ticker.upper())
    )
    position_value: float = float(ticker_result.scalar() or 0.0)
    weight = position_value / total_nav
    return weight, total_nav


async def _get_all_positions(session: AsyncSession) -> tuple[list[dict[str, float | str]], float]:
    """Return (positions_list, cash_percentage) from the live DB.

    Each position dict has keys ``ticker`` (str) and ``weight`` (float fraction).
    ``cash_percentage`` is cash / total_nav.
    """
    tickers_result = await session.execute(
        select(Ticker.ticker, Ticker.position_value).where(Ticker.position_value.isnot(None))
    )
    rows = tickers_result.all()

    total_invested_result = await session.execute(select(func.sum(Ticker.position_value)))
    total_invested: float = float(total_invested_result.scalar() or 0.0)

    cash_result = await session.execute(select(PortfolioConfig.cash_balance).limit(1))
    cash_balance: float = float(cash_result.scalar() or 0.0)

    total_nav = total_invested + cash_balance
    if total_nav == 0.0:
        return [], 0.0

    positions: list[dict[str, float | str]] = [
        {
            "ticker": str(row.ticker),
            "weight": float(row.position_value or 0.0) / total_nav,
        }
        for row in rows
        if (row.position_value or 0.0) > 0.0
    ]

    cash_percentage = cash_balance / total_nav
    return positions, cash_percentage


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{ticker}", response_model=Framework13Result)
async def get_framework13(
    ticker: Annotated[
        str,
        Path(description="Ticker symbol (case-insensitive, e.g. 'AAOI')."),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    position_weight_override: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=1.0,
            description=(
                "Override live DB position weight (0.0-1.0 fraction). "
                "For testing — omit in production."
            ),
        ),
    ] = None,
    nav_override: Annotated[
        float | None,
        Query(
            ge=0.0,
            description=(
                "Override total NAV in USD (used to compute position_dollars). "
                "For testing — omit in production."
            ),
        ),
    ] = None,
) -> Framework13Result:
    """Return the full Framework 13 beta cap evaluation for a single ticker."""
    if not ticker.strip():
        raise HTTPException(status_code=422, detail="Ticker must not be blank.")

    if position_weight_override is not None:
        weight = position_weight_override
        nav = nav_override if nav_override is not None else 0.0
    else:
        weight, nav = await _get_position_weight_and_nav(ticker.strip().upper(), session)

    return await evaluate_framework13(ticker.strip().upper(), weight, nav)


@router.get("/portfolio/beta", response_model=PortfolioBetaResult)
async def get_portfolio_beta(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cash_percentage_override: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=1.0,
            description="Override cash percentage (0.0-1.0). For testing.",
        ),
    ] = None,
) -> PortfolioBetaResult:
    """Return weighted-average and effective portfolio beta across all positions.

    Reads all non-zero positions from the portfolio table and calculates:
      weighted_avg_beta = Σ (weight * beta)
      effective_beta    = weighted_avg_beta * (1 - cash_percentage)
    """
    positions, db_cash_pct = await _get_all_positions(session)
    cash_pct = cash_percentage_override if cash_percentage_override is not None else db_cash_pct
    return await calculate_portfolio_beta(positions, cash_pct)


@router.get("/beta/{ticker}")
async def get_beta_lookup(
    ticker: Annotated[
        str,
        Path(description="Ticker symbol (case-insensitive)."),
    ],
) -> dict[str, object]:
    """Quick beta lookup: returns beta value and source for a ticker.

    Used by Framework 4 and other frameworks for fast cap checks without
    computing the full Framework13Result.
    """
    if not ticker.strip():
        raise HTTPException(status_code=422, detail="Ticker must not be blank.")
    beta, source = get_beta(ticker.strip().upper())
    return {
        "ticker": ticker.strip().upper(),
        "beta": beta,
        "beta_source": source.value,
    }
