"""API routes for portfolio tickers — CRUD operations."""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import get_settings
from atlas.db.session import get_db_session
from atlas.schemas.ticker import TickerCreate, TickerResponse, TickerUpdate
from atlas.services.market_data_service import MarketDataService
from atlas.services.ticker_service import TickerService

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("", response_model=list[TickerResponse])
async def list_tickers(
    session: AsyncSession = Depends(get_db_session),
) -> list[TickerResponse]:
    """Return all saved portfolio tickers ordered by symbol."""
    service = TickerService(session)
    return await service.list_tickers()  # type: ignore[return-value]


@router.post("", response_model=TickerResponse, status_code=201)
async def create_ticker(
    data: TickerCreate,
    session: AsyncSession = Depends(get_db_session),
) -> TickerResponse:
    """Add a new ticker/share-count pair to the portfolio.

    Returns 409 if the ticker already exists.
    """
    service = TickerService(session)
    existing = await service.get_by_ticker(data.ticker)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ticker {data.ticker} already exists. Use PATCH to update shares.",
        )
    return await service.create_ticker(data)  # type: ignore[return-value]


@router.patch("/{ticker_id}", response_model=TickerResponse)
async def update_ticker(
    ticker_id: int,
    data: TickerUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> TickerResponse:
    """Update the share count for an existing ticker."""
    service = TickerService(session)
    ticker = await service.update_shares(ticker_id, data.shares, data.cluster_id)
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker_id} not found.")
    return ticker  # type: ignore[return-value]


@router.delete("/{ticker_id}", status_code=204)
async def delete_ticker(
    ticker_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a ticker from the portfolio."""
    service = TickerService(session)
    deleted = await service.delete_ticker(ticker_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker_id} not found.")


@router.post("/sync", response_model=list[TickerResponse])
async def sync_market_data(
    session: AsyncSession = Depends(get_db_session),
) -> list[TickerResponse]:
    """Fetch live quotes from Polygon and update all ticker market-data fields.

    Returns 503 when ``POLYGON_API_KEY`` is not configured.
    Returns the full updated ticker list after sync.
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Market data sync is unavailable: POLYGON_API_KEY is not configured.",
        )

    async with httpx.AsyncClient() as client:
        service = MarketDataService(
            api_key=settings.polygon_api_key,
            alphavantage_api_key=settings.alphavantage_api_key,
            session=session,
            client=client,
        )
        return await service.sync_tickers()  # type: ignore[return-value]


@router.get("/beta/live", response_model=dict[str, float | None])
async def get_live_beta(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, float | None]:
    """Fetch live Beta for every portfolio ticker directly from Alpha Vantage.

    Returns a ``{ticker: beta}`` map — values are floats or null when AV has
    no usable beta for a symbol.  Always fetches fresh; never reads from DB.
    Returns 503 when ``ALPHAVANTAGE_API_KEY`` is not configured.
    """
    settings = get_settings()
    if not settings.alphavantage_api_key:
        raise HTTPException(
            status_code=503,
            detail="Live beta is unavailable: ALPHAVANTAGE_API_KEY is not configured.",
        )

    from atlas.services.ticker_service import TickerService  # local import avoids circular

    ticker_service = TickerService(session)
    tickers = await ticker_service.list_tickers()
    symbols = [t.ticker for t in tickers]

    async with httpx.AsyncClient() as client:
        service = MarketDataService(
            api_key=settings.polygon_api_key,
            alphavantage_api_key=settings.alphavantage_api_key,
            session=session,
            client=client,
        )
        beta_map = await service.fetch_live_betas(symbols)

    return {k: float(v) if v is not None else None for k, v in beta_map.items()}
