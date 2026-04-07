"""Aggregated v1 API router."""

from fastapi import APIRouter

from atlas.api.v1 import health

router = APIRouter()
router.include_router(health.router, tags=["health"])
