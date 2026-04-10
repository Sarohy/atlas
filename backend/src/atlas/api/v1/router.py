"""Aggregated v1 API router."""

from fastapi import APIRouter

from atlas.api.v1 import (
    analyst,
    auth,
    clusters,
    earnings,
    framework_score,
    fundamental,
    health,
    market_conditions,
    momentum,
    options_flow,
    portfolio,
    regime_modifier,
    ticker_search,
    tickers,
    watchlist,
)

router = APIRouter()
router.include_router(auth.router, tags=["auth"])
router.include_router(health.router, tags=["health"])
router.include_router(portfolio.router)
router.include_router(tickers.router)
router.include_router(ticker_search.router)
router.include_router(clusters.router)
router.include_router(watchlist.router)
router.include_router(momentum.router)
router.include_router(earnings.router)
router.include_router(analyst.router)
router.include_router(options_flow.router)
router.include_router(fundamental.router)
router.include_router(framework_score.router)
router.include_router(regime_modifier.router)
router.include_router(market_conditions.router)
