"""API route for Framework 3 — Position Sizing.

GET /api/v1/position-sizing/{ticker}[?base_score=n]

Maps a Framework 1 conviction score to a human-readable position action using
the Framework 3 band rules (Factor_Mapping_Guide §Framework3).

When ``base_score`` is supplied the Framework 1 recompute is skipped entirely,
ensuring Framework 3 is always in sync with the score the UI already holds.
When omitted, the Framework 1 score is computed fresh.

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
) -> PositionSizingResponse:
    """Return a Framework 3 position-sizing recommendation for ``ticker``.

    Pass ``?base_score=<n>`` to reuse the Framework 1 score already held by
    the UI — this avoids a second independent computation and guarantees
    Framework 3 stays in sync with Framework 1.

    When ``base_score`` is omitted, Framework 1 is recomputed from scratch.

    Score-to-action bands (Factor_Mapping_Guide §Framework3):
      > 90        MAXIMUM POSITION      — Add on every dip
      80 – 90     HOLD FULL             — Eligible for adds
      70 – 79     HOLD                  — No new adds
      60 – 69     REDUCE 25-50%         — Reduce 25-50%
      55 – 59     REDUCE AGGRESSIVELY   — Reduce aggressively
      < 55        EXIT                  — Exit immediately

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
    )
