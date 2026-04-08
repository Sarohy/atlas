"""Aggregated v1 API router."""

from fastapi import APIRouter

from atlas.api.v1 import auth, clusters, health, portfolio, ticker_search, tickers

router = APIRouter()
router.include_router(auth.router, tags=["auth"])
router.include_router(health.router, tags=["health"])
router.include_router(portfolio.router)
router.include_router(tickers.router)
router.include_router(ticker_search.router)
router.include_router(clusters.router)
