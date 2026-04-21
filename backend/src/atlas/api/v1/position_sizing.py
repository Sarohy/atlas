"""API route for Framework 3 — Score Action Map.

GET /api/v1/position-sizing/{ticker}[?base_score=n&concentration_cap_active=false]

Maps a Framework 1 conviction score to a position-sizing action using
the Framework 3 Score Action Map v7.3.4.

When ``base_score`` is supplied the Framework 1 recompute is skipped,
ensuring Framework 3 is always in sync with the score the UI already holds.
When omitted, the Framework 1 score is computed fresh.

``concentration_cap_active`` is read from the Framework 14 concentration-cap
result supplied by the caller; defaults to False when not provided.

Returns 503 when POLYGON_API_KEY is not configured (required for Framework 1).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.position_sizing import PositionSizingResponse
from atlas.services.framework_score_service import FrameworkScoreService
from atlas.services.position_sizing_service import compute_position_sizing

router = APIRouter(prefix="/position-sizing", tags=["position-sizing"])


@router.get("/{ticker}", response_model=PositionSizingResponse)
async def get_position_sizing(
    ticker: str,
    base_score: int | None = None,
    concentration_cap_active: bool = False,
) -> PositionSizingResponse:
    """Return a Framework 3 Score Action Map result for ``ticker``.

    Pass ``?base_score=<n>`` to reuse the Framework 1 score already held by
    the UI — this avoids a second independent computation and guarantees
    Framework 3 stays in sync with Framework 1.

    Pass ``?concentration_cap_active=true`` when Framework 14 has flagged a
    concentration cap for this position; Tier 1 adds will be blocked.

    Score-to-action bands (v7.3.4):
      >= 85       TIER_1         - Core position, LEAPS eligible
      78 - 84     TIER_2_GREY    - Grey zone, 3-model consensus required
      70 - 77     TIER_2         - GTC adds permitted
      55 - 69     TIER_3         - Small position only
      < 55        WATCHLIST      - Exit rules active (see Framework 16)

    Returns 503 when POLYGON_API_KEY is not configured.
    """
    settings = get_settings()

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    if base_score is not None:
        # Frontend passed the Framework 1 score — use it directly.
        conviction_score = max(0, min(100, base_score))
    else:
        if not settings.polygon_api_key:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Position Sizing unavailable: POLYGON_API_KEY is not configured. "
                    "This key is required for Framework 1 scoring."
                ),
            )
        framework_service = FrameworkScoreService(
            polygon_api_key=settings.polygon_api_key,
            alphavantage_api_key=settings.alphavantage_api_key or "",
            transcript_api_key=settings.earnings_transcript_api_key or "",
            benzinga_api_key=settings.benzinga_api_key or "",
            unusual_whales_api_key=settings.unusual_whales_api_key or "",
            sec_api_key=settings.sec_api_key or "",
        )
        framework_result = await framework_service.compute_framework_score(normalised)
        conviction_score = framework_result.final_score

    return compute_position_sizing(
        ticker=normalised,
        conviction_score=conviction_score,
        concentration_cap_active=concentration_cap_active,
    )
