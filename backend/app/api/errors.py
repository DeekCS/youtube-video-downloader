"""Global exception handlers for API errors."""
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.models.video import ErrorResponse
from app.services.errors import (
    FormatNotAvailableError,
    InvalidUrlError,
    UnsupportedPlatformError,
    VideoDownloaderError,
    VideoNotFoundError,
    YtdlpFailedError,
)

logger = get_logger(__name__)


async def video_downloader_error_handler(
    request: Request, exc: VideoDownloaderError
) -> JSONResponse:
    """Handle all VideoDownloaderError exceptions.

    Args:
        request: FastAPI request
        exc: Domain exception

    Returns:
        JSON response with error details
    """
    # Map exceptions to HTTP status codes
    status_code_map = {
        "INVALID_URL": status.HTTP_400_BAD_REQUEST,
        "UNSUPPORTED_PLATFORM": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "FORMAT_NOT_AVAILABLE": status.HTTP_404_NOT_FOUND,
        "YTDLP_FAILED": status.HTTP_502_BAD_GATEWAY,
        "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    status_code = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Log error (excluding INVALID_URL which is expected user error)
    if exc.code not in ["INVALID_URL"]:
        logger.warning(f"Domain error: {exc.code} - {exc.message}")

    error_response = ErrorResponse(code=exc.code, message=exc.message)

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: Unexpected exception

    Returns:
        JSON response with generic error
    """
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    error_response = ErrorResponse(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
