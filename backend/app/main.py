"""FastAPI application entry point."""
import glob
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.errors import generic_exception_handler, video_downloader_error_handler
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.health import run_health_checks
from app.core.logging import get_logger, setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.version import __version__
from app.models.video import HealthResponse
from app.services.download_tasks import cleanup_all
from app.services.errors import VideoDownloaderError

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup
    logger.info(f"Starting application in {settings.ENV} mode")
    logger.info(f"API v1 prefix: {settings.API_V1_PREFIX}")
    logger.info(f"CORS origins: {settings.cors_origins_list}")

    # Startup: clean up orphaned temp dirs from previous crashes
    _cleanup_orphaned_temp_dirs()

    yield

    # Shutdown: cancel in-flight downloads and clean up temp dirs
    logger.info("Shutting down application — cleaning up downloads…")
    cleanup_all()
    _cleanup_orphaned_temp_dirs()
    logger.info("Shutdown complete")


def _cleanup_orphaned_temp_dirs() -> None:
    """Remove leftover ytdl temp directories from previous runs."""
    import tempfile

    patterns = [
        f"{tempfile.gettempdir()}/ytdl_*",
        f"{tempfile.gettempdir()}/ytdl_single_*",
        f"{tempfile.gettempdir()}/ytdl_cli_*",
    ]
    removed = 0
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"Cleaned up {removed} orphaned temp directories")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Video Downloader API",
        description="Self-hosted multi-platform video downloader using yt-dlp",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Exception handlers
    app.add_exception_handler(VideoDownloaderError, video_downloader_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Include API routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Health check endpoint
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Health check",
        description="Check if the service is running",
    )
    async def health_check() -> HealthResponse:
        """Health check endpoint.

        Returns:
            Health status response
        """
        return run_health_checks()

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )
