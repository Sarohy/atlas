"""API routes for the ATLAS Overbought / Extension Overlay.

GET /api/v1/extension-overlay/{ticker}[?atlas_score={n}]

Returns the Extension Risk Score, flag (GREEN/YELLOW/RED/EXTREME_RED), and —
when an ATLAS conviction score is supplied — an action recommendation that
pairs fundamental quality with technical entry timing.

Returns 503 when POLYGON_API_KEY is not configured (required for price bars).
"""

from fastapi import APIRouter, HTTPException

from atlas.config import get_settings
from atlas.schemas.extension_overlay import ExtensionOverlayResponse
from atlas.services.extension_overlay_service import ExtensionOverlayService

router = APIRouter(prefix="/extension-overlay", tags=["extension-overlay"])


@router.get("/{ticker}", response_model=ExtensionOverlayResponse)
async def get_extension_overlay(
    ticker: str, atlas_score: int | None = None, f4_score: int | None = None
) -> ExtensionOverlayResponse:
    """Compute the Overbought / Extension Overlay for a single ticker.

    Pass ``?atlas_score={n}`` (the name's final ATLAS conviction score) to get
    an action recommendation from the quality x timing matrix; omit it for the
    raw extension metrics and flag only.

    Pass ``?f4_score={n}`` (the F4 Options Flow Persistence score) so the action
    reflects flow confirmation: a non-extended high-conviction name is a full ADD
    only when flow confirms, otherwise STARTER / WATCH (add on F4 confirmation).
    """
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(
            status_code=503,
            detail="Extension overlay unavailable: POLYGON_API_KEY is not configured.",
        )

    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    if atlas_score is not None and not (0 <= atlas_score <= 100):
        raise HTTPException(status_code=422, detail="atlas_score must be between 0 and 100.")

    if f4_score is not None and not (0 <= f4_score <= 100):
        raise HTTPException(status_code=422, detail="f4_score must be between 0 and 100.")

    # The UW key is optional — IV rank is reported as a DATA_GAP when it is unset.
    service = ExtensionOverlayService(
        api_key=settings.polygon_api_key,
        uw_api_key=settings.unusual_whales_api_key or "",
    )
    return await service.compute_overlay(
        normalised, atlas_score=atlas_score, f4_score=f4_score
    )
