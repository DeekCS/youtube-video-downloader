"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import generic_exception_handler, video_downloader_error_handler
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.models.video import HealthResponse
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

    yield

    # Shutdown
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Video Downloader API",
        description="Self-hosted multi-platform video downloader using yt-dlp",
        version="0.1.0",
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
        return HealthResponse(status="healthy", version="0.1.0")

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
