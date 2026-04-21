"""API route for Framework 8 — Insider Activity Flag.

GET /api/v1/framework8/{ticker}

Returns the insider activity analysis for a given ticker:
  - flag_active: True when discretionary insider selling detected
  - hard_pass:   True when pattern (many sales, zero buys) disqualifies ticker
  - filer_tier:  Seniority tier of the triggering filer
  - f5_cap:      Score cap to apply to Framework 5 (68 or 72)
  - source:      "hardcoded" | "sec_edgar" | "default"

Hardcoded tickers (NBIS, CRDO, FN, COHR, CF) bypass the API.
Returns 503 when SEC_API_KEY is not configured and ticker is not hardcoded.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.framework8 import Framework8Response
from atlas.services.framework8_service import Framework8Service, InsiderTier

router = APIRouter(prefix="/framework8", tags=["framework8"])

# Tickers that bypass the API (must mirror _HARDCODED_ACTIVE in the service).
_HARDCODED_ACTIVE: frozenset[str] = frozenset({"NBIS", "CRDO", "FN", "COHR", "CF"})


@router.get("/{ticker}", response_model=Framework8Response)
async def get_framework8(ticker: str) -> Framework8Response:
    """Return the Framework 8 insider activity analysis for *ticker*.

    Hardcoded tickers (NBIS, CRDO, FN, COHR, CF) are always available.
    For other tickers, SEC_API_KEY must be configured; returns 503 otherwise.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    settings = get_settings()
    service = Framework8Service(sec_api_key=settings.sec_api_key or "")
    result = await service.compute(normalised)

    return Framework8Response(
        ticker=result.ticker,
        flag_active=result.flag_active,
        hard_pass=result.hard_pass,
        filer_tier=result.filer_tier,
        largest_sale_usd=result.largest_sale_usd,
        f5_cap=result.f5_cap,
        source=result.source,
    )
