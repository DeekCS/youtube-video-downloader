"""Per-IP rate limiting middleware using slowapi.

Provides decorators for API endpoints to protect against abuse and
denial-of-service.  Limits are intentionally generous for self-hosted
use but prevent automated scraping and runaway retries.
"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


def _key_func(request: Request) -> str:
    """Extract client IP for rate-limit bucketing.

    Uses ``get_remote_address`` which respects X-Forwarded-For behind
    proxies (Railway, Docker, etc.).
    """
    return get_remote_address(request)


# Shared limiter instance — imported by endpoint modules.
limiter = Limiter(key_func=_key_func)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return a structured JSON error when rate limit is hit."""
    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)}: {exc.detail}"
    )
    return JSONResponse(
        status_code=429,
        content={
            "code": "RATE_LIMITED",
            "message": "Too many requests. Please slow down and try again shortly.",
        },
    )
