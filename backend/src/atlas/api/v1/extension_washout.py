"""API routes for the Extension & Washout Overlay (Spec v2).

GET /api/v1/extension-washout/{ticker}
    [?position_weight_pct={f}]   # live position weight (% NAV) for the §3.1 size gate
    [&negative_catalyst=true]    # operator-flagged negative catalyst (§7)

Display/posture overlay only — never modifies F1-F5 or the ATLAS score.
Returns 503 when POLYGON_API_KEY is not configured (required for price bars).
"""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.extension_washout import ExtensionWashoutResponse, WashoutReferenceResponse
from atlas.services.extension_washout_service import ExtensionWashoutService, build_reference

router = APIRouter(prefix="/extension-washout", tags=["extension-washout"])


@router.get("/reference", response_model=WashoutReferenceResponse)
async def get_extension_washout_reference() -> WashoutReferenceResponse:
    """Settings thresholds (§10) + Risk exception rows (per-name overrides)."""
    return build_reference()


@router.get("/{ticker}", response_model=ExtensionWashoutResponse)
async def get_extension_washout(
    ticker: str,
    position_weight_pct: float | None = None,
    negative_catalyst: bool = False,
    beta: float | None = None,
) -> ExtensionWashoutResponse:
    """Compute the Extension & Washout Overlay posture for a single ticker."""
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Extension washout overlay unavailable: POLYGON_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    if position_weight_pct is not None and not (0 <= position_weight_pct <= 100):
        raise HTTPException(
            status_code=422, detail="position_weight_pct must be between 0 and 100."
        )

    service = ExtensionWashoutService(
        api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key or "",
    )
    return await service.compute(
        normalised,
        position_weight_pct=position_weight_pct,
        negative_catalyst=negative_catalyst,
        beta=beta,
    )
