"""Tests for Redis connection module."""
from unittest.mock import MagicMock, patch

import pytest


class TestRedisModule:
    def test_is_redis_available_false_when_disabled(self) -> None:
        from app.core import redis as redis_mod

        with patch("app.core.redis.settings") as mock_settings:
            mock_settings.REDIS_ENABLED = False
            redis_mod._redis_available = False
            assert redis_mod.is_redis_available() is False

    def test_get_sync_redis_returns_none_when_unavailable(self) -> None:
        from app.core import redis as redis_mod

        redis_mod._redis_available = False
        assert redis_mod.get_sync_redis() is None

    def test_init_redis_sets_available_on_successful_ping(self) -> None:
        from app.core import redis as redis_mod

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch("app.core.redis.settings") as mock_settings, \
             patch("redis.Redis.from_url", return_value=mock_client), \
             patch("redis.asyncio.Redis.from_url", return_value=MagicMock()):
            mock_settings.REDIS_ENABLED = True
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            redis_mod._redis_available = False
            redis_mod._sync_client = None
            redis_mod.init_redis()
            assert redis_mod._redis_available is True

    def test_init_redis_stays_unavailable_on_connection_error(self) -> None:
        from app.core import redis as redis_mod

        with patch("app.core.redis.settings") as mock_settings, \
             patch("redis.Redis.from_url", side_effect=ConnectionError("refused")):
            mock_settings.REDIS_ENABLED = True
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            redis_mod._redis_available = False
            redis_mod._sync_client = None
            redis_mod.init_redis()
            assert redis_mod._redis_available is False
