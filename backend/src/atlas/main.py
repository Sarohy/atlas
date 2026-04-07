"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas.api.v1.router import router as v1_router
from atlas.config import get_settings
from atlas.core.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings.environment)
    logger = get_logger(__name__)

    app = FastAPI(
        title="ATLAS Backend",
        description="Decision-support tool for active investing.",
        version="0.1.0",
    )

    # CORS — allow the Next.js dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(v1_router, prefix="/api/v1")

    logger.info("ATLAS backend booted", environment=settings.environment)

    return app
