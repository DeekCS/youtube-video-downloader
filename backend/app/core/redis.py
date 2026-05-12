"""Redis connection management with graceful in-memory fallback.

Provides a shared sync client (for background threads) and tracks availability.
If Redis is unreachable at startup, all callers fall back to in-memory state.
"""

import threading

import redis
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_sync_client: redis.Redis | None = None
_async_client: aioredis.Redis | None = None
_redis_available: bool = False
_init_lock = threading.Lock()


def init_redis() -> None:
    """Initialize Redis connection pool. Called once at app startup via lifespan."""
    global _sync_client, _async_client, _redis_available

    if not settings.REDIS_ENABLED:
        logger.info("Redis disabled by REDIS_ENABLED=false; using in-memory fallback")
        return

    with _init_lock:
        try:
            client: redis.Redis = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            _sync_client = client
            _async_client = aioredis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _redis_available = True
            logger.info(f"Redis connected: {settings.REDIS_URL}")
        except Exception as exc:
            logger.warning(
                f"Redis unavailable ({exc}); using in-memory fallback for task state and cache"
            )
            _redis_available = False


async def close_redis() -> None:
    """Close Redis connections. Called at app shutdown."""
    global _sync_client, _async_client

    if _sync_client is not None:
        try:
            _sync_client.close()
        except Exception:
            pass
        _sync_client = None

    if _async_client is not None:
        try:
            await _async_client.aclose()
        except Exception:
            pass
        _async_client = None


def is_redis_available() -> bool:
    """Return True if Redis is connected and usable."""
    return _redis_available and _sync_client is not None


def get_sync_redis() -> redis.Redis | None:
    """Return the sync Redis client, or None if unavailable."""
    return _sync_client if _redis_available else None
