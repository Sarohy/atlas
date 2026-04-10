"""API routes for the F5 Fundamental Quality calculator."""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.fundamental import FundamentalResponse
from atlas.services.fundamental_service import FundamentalService

router = APIRouter(prefix="/fundamental", tags=["fundamental"])


@router.get("/{ticker}", response_model=FundamentalResponse)
async def get_fundamental(ticker: str) -> FundamentalResponse:
    """Compute the F5 Fundamental Quality score for a single ticker.

    Pulls data from two sources in parallel:
      - sec-api.io  — Form 4 insider trading filings (last 90 days)
      - Alpha Vantage — BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW, OVERVIEW

    Five weighted sub-indicators per Factor_Mapping_Guide §F5:
      Insider Activity        (30%)
      Altman Z-Score          (25%)
      Free Cash Flow          (20%)
      Debt / Equity           (15%)
      Institutional Ownership (10%)

    Caps and hard blocks:
      - C-suite officer sale >$1M     → score capped at 72
      - CEO/CFO sale >$10M            → score capped at 65
      - Altman Z in grey zone 1.8-2.0 → score capped at 75
      - Altman Z < 1.8 (distress)     → f5_blocked = True (hard block on new capital)

    Returns 503 when SEC_API_KEY or ALPHAVANTAGE_API_KEY is not configured.
    """
    settings = get_settings()
    if not settings.sec_api_key:
        raise HTTPException(
            status_code=503,
            detail="Fundamental analysis unavailable: SEC_API_KEY is not configured.",
        )
    if not settings.alphavantage_api_key:
        raise HTTPException(
            status_code=503,
            detail="Fundamental analysis unavailable: ALPHAVANTAGE_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = FundamentalService(
        sec_api_key=settings.sec_api_key,
        alphavantage_key=settings.alphavantage_api_key,
    )
    return await service.compute_fundamental(normalised)
