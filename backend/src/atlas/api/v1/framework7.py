"""API route for Framework 7 — Earnings Gate Rule.

GET /api/v1/framework7/{ticker}[?score={n}]

Determines whether the investor may add to a position ahead of an upcoming
earnings release, based on:
  - Earnings date from Alpha Vantage EARNINGS_CALENDAR
  - Framework 1 regime-adjusted conviction score
  - Framework 8 insider activity flag

Gate status values
------------------
OPEN           → no gate active (no upcoming earnings or gate not yet triggered)
CLOSED         → gate active, score ≤ 80 — zero position adds
50% CAP        → gate active, score > 80 — adds permitted at 50% target weight
DOUBLE BLOCKED → gate active + insider_flag — no adds under any condition

The optional ``score`` query param lets the frontend pass the F1 display score
(already regime-adjusted) directly, skipping a redundant re-fetch.

Returns 503 when ALPHAVANTAGE_API_KEY is not configured.
"""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.framework7 import EarningsGate
from atlas.services.framework7_service import Framework7Service

router = APIRouter(prefix="/framework7", tags=["framework7"])


@router.get("/{ticker}", response_model=EarningsGate)
async def get_framework7(
    ticker: str,
    score: int | None = None,
) -> EarningsGate:
    """Return the Framework 7 Earnings Gate evaluation for ``ticker``.

    Query parameters
    ----------------
    score : int, optional
        Regime-adjusted Framework 1 score (0-100).  When provided, the
        backend uses this value directly and skips its own F1 fetch —
        ensuring the gate evaluates the same score the investor sees on the
        Framework 1 panel.

    Returns 503 when ALPHAVANTAGE_API_KEY is not configured (required for
    earnings date lookup).
    """
    settings = get_settings()

    if not settings.alphavantage_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Framework 7 unavailable: ALPHAVANTAGE_API_KEY is not configured. "
                "This key is required for earnings date lookup."
            ),
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    service = Framework7Service(
        alphavantage_api_key=settings.alphavantage_api_key,
        polygon_api_key=settings.polygon_api_key or "",
        transcript_api_key=settings.earnings_transcript_api_key or "",
        benzinga_api_key=settings.benzinga_api_key or "",
        unusual_whales_api_key=settings.unusual_whales_api_key or "",
        sec_api_key=settings.sec_api_key or "",
    )
    return await service.compute(normalised, provided_score=score)
