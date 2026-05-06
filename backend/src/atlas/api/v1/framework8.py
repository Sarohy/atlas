"""API route for Framework 8 — Insider Buying Detector.

GET /api/v1/framework8/{ticker}

Returns the insider activity analysis for a given ticker:
  - buying_bonus:            Additive score bonus from insider purchases (0-5)
  - clustered_selling_note:  Display-only note when multiple C-suite insiders
                             sell without a 10b5-1 plan; null otherwise
  - source:                  "sec_edgar" | "default"

All tickers are evaluated live against SEC EDGAR's free public API
(submissions + Form 4 XML). No API key is required.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.framework8 import Framework8Response
from atlas.services.framework8_service import Framework8Service

router = APIRouter(prefix="/framework8", tags=["framework8"])


@router.get("/{ticker}", response_model=Framework8Response)
async def get_framework8(ticker: str) -> Framework8Response:
    """Return the Framework 8 insider activity analysis for *ticker*.

    All tickers are evaluated live against SEC EDGAR's free public API
    (submissions + Form 4 XML). No API key is required.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    settings = get_settings()
    service = Framework8Service(sec_api_key=settings.sec_api_key or "")
    result = await service.compute(normalised)

    return Framework8Response(
        ticker=result.ticker,
        buying_bonus=result.buying_bonus,
        clustered_selling_note=result.clustered_selling_note,
        source=result.source,
    )
