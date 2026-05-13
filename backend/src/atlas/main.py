"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas.api.v1.router import router as v1_router
from atlas.config import get_settings
from atlas.core.logging import configure_logging, get_logger
from atlas.core.scheduler import start_scheduler, stop_scheduler
from atlas.db.session import AsyncSessionLocal
from atlas.services.regime_modifier_service import load_geo_flag_from_db


def _parse_allowed_origins(raw_allowed_origins: str) -> list[str]:
    """Return a normalized list of allowed CORS origins from a CSV env var."""
    return [origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan — start and stop background services."""
    # Restore the persisted geopolitical flag so Framework 29 S5 survives restarts.
    try:
        async with AsyncSessionLocal() as session:
            await load_geo_flag_from_db(session)
    except Exception:  # noqa: BLE001
        pass  # DB may not be available in test environments

    await start_scheduler()
    yield
    await stop_scheduler()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings.environment)
    logger = get_logger(__name__)
    allowed_origins = _parse_allowed_origins(settings.allowed_origins)

    app = FastAPI(
        title="ATLAS Backend",
        description="Decision-support tool for active investing.",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # CORS — allow the Next.js dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(v1_router, prefix="/api/v1")

    logger.info("ATLAS backend booted", environment=settings.environment)

    return app

