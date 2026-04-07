"""Aggregated v1 API router."""

from fastapi import APIRouter

from atlas.api.v1 import auth, health

router = APIRouter()
router.include_router(auth.router, tags=["auth"])
router.include_router(health.router, tags=["health"])
