"""API routes for the Forward Growth Score (FGS).

GET /api/v1/forward-growth/{ticker}
    [?f5_score=&f4_score=&atlas_score=]
    [&backlog=&customer_quality=&product_ramp=]   # optional operator overrides

FGS is a parallel growth axis. Pass the live F5 (and ideally F4) scores to get the
F5 x FGS x F4 action-matrix bucket. Returns 503 when ALPHAVANTAGE_API_KEY is unset.
"""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.forward_growth import ForwardGrowthResponse
from atlas.services.forward_growth_service import ForwardGrowthService

router = APIRouter(prefix="/forward-growth", tags=["forward-growth"])


def _validate_score(value: int | None, name: str) -> None:
    if value is not None and not (0 <= value <= 100):
        raise HTTPException(status_code=422, detail=f"{name} must be between 0 and 100.")


@router.get("/{ticker}", response_model=ForwardGrowthResponse)
async def get_forward_growth(
    ticker: str,
    f5_score: int | None = None,
    f4_score: int | None = None,
    atlas_score: int | None = None,
    backlog: int | None = None,
    customer_quality: int | None = None,
    product_ramp: int | None = None,
) -> ForwardGrowthResponse:
    """Compute the Forward Growth Score (+ action bucket when F5/F4 supplied)."""
    settings = get_settings()
    if not settings.alphavantage_api_key:
        raise HTTPException(
            status_code=503,
            detail="Forward Growth Score unavailable: ALPHAVANTAGE_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    for value, name in (
        (f5_score, "f5_score"),
        (f4_score, "f4_score"),
        (atlas_score, "atlas_score"),
        (backlog, "backlog"),
        (customer_quality, "customer_quality"),
        (product_ramp, "product_ramp"),
    ):
        _validate_score(value, name)

    service = ForwardGrowthService(alphavantage_key=settings.alphavantage_api_key)
    return await service.compute_forward_growth(
        normalised,
        f5_score=f5_score,
        f4_score=f4_score,
        atlas_score=atlas_score,
        backlog_override=backlog,
        customer_quality_override=customer_quality,
        product_ramp_override=product_ramp,
    )
