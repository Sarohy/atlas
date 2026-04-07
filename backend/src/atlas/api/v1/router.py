"""Aggregated v1 API router."""

from fastapi import APIRouter

from atlas.api.v1 import health, positions, tickers

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(positions.router)
router.include_router(tickers.router)
