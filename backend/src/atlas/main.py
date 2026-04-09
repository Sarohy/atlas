"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas.api.v1.router import router as v1_router
from atlas.config import get_settings
from atlas.core.logging import configure_logging, get_logger


def _parse_allowed_origins(raw_allowed_origins: str) -> list[str]:
    """Return a normalized list of allowed CORS origins from a CSV env var."""
    return [origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()]


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


if __name__ == "__main__":
    import multiprocessing

    import uvicorn

    uvicorn.run(
        "atlas.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=multiprocessing.cpu_count(),
    )
