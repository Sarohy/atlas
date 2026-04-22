"""Aggregated v1 API router."""

from fastapi import APIRouter

from atlas.api.v1 import (
    analyst,
    auth,
    cash_floor,
    clusters,
    conviction_action,
    earnings,
    framework7,
    framework8,
    framework13,
    framework14,
    framework_score,
    fundamental,
    health,
    market_conditions,
    momentum,
    options_flow,
    portfolio,
    position_sizing,
    regime_modifier,
    ticker_search,
    tickers,
    tranche_sizing,
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
router.include_router(framework7.router)
router.include_router(framework8.router)
router.include_router(framework13.router)
router.include_router(framework14.router)
router.include_router(position_sizing.router)
router.include_router(tranche_sizing.router)
router.include_router(regime_modifier.router)
router.include_router(cash_floor.router)
router.include_router(conviction_action.router)
router.include_router(market_conditions.router)
