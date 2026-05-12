"""Tests for Redis connection module."""
from unittest.mock import MagicMock, patch


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

    def test_close_redis_clears_clients(self) -> None:
        import asyncio

        from app.core import redis as redis_mod

        async def _noop() -> None:
            pass

        mock_sync = MagicMock()
        mock_async = MagicMock()
        mock_async.aclose = MagicMock(return_value=_noop())

        redis_mod._sync_client = mock_sync
        redis_mod._async_client = mock_async
        redis_mod._redis_available = True

        asyncio.run(redis_mod.close_redis())

        assert redis_mod._sync_client is None
        assert redis_mod._async_client is None


class TestRedisDownloadTasks:
    def setup_method(self) -> None:
        """Reset in-memory state before each test."""
        import app.services.download_tasks as dt
        with dt._lock:
            dt._tasks.clear()

    def test_create_task_returns_dataclass(self) -> None:
        import app.services.download_tasks as dt
        from app.core import redis as redis_mod
        redis_mod._redis_available = False  # force in-memory

        task = dt.create_task("t1", filename="x.mp4")
        assert task.task_id == "t1"
        assert task.filename == "x.mp4"
        assert task.status == "pending"

    def test_update_task_changes_in_memory_fields(self) -> None:
        import app.services.download_tasks as dt
        from app.core import redis as redis_mod
        redis_mod._redis_available = False

        dt.create_task("t2")
        dt.update_task("t2", status="downloading", progress=50.0)
        task = dt.get_task("t2")
        assert task is not None
        assert task.status == "downloading"
        assert task.progress == 50.0

    def test_get_task_returns_none_for_missing(self) -> None:
        import app.services.download_tasks as dt
        from app.core import redis as redis_mod
        redis_mod._redis_available = False

        assert dt.get_task("does-not-exist") is None

    def test_remove_task_deletes_from_store(self) -> None:
        import app.services.download_tasks as dt
        from app.core import redis as redis_mod
        redis_mod._redis_available = False

        dt.create_task("t3")
        removed = dt.remove_task("t3")
        assert removed is not None
        assert dt.get_task("t3") is None

    def test_update_task_writes_to_redis_when_available(self) -> None:
        import app.services.download_tasks as dt
        from app.core import redis as redis_mod

        mock_redis = MagicMock()
        redis_mod._sync_client = mock_redis
        redis_mod._redis_available = True

        try:
            dt.create_task("t4")
            dt.update_task("t4", status="downloading")
            mock_redis.hset.assert_called()
        finally:
            redis_mod._redis_available = False
            redis_mod._sync_client = None


class TestRedisFormatCache:
    def test_get_cached_formats_returns_none_when_cache_miss(self) -> None:
        from app.core import redis as redis_mod
        from app.services.yt_dlp_service import YtDlpService

        redis_mod._redis_available = False
        YtDlpService._formats_cache = None  # clear in-memory cache

        result = YtDlpService.get_cached_formats("https://example.com/video")
        assert result is None

    def test_cache_set_and_get_roundtrip_in_memory(self) -> None:
        from app.core import redis as redis_mod
        from app.models.video import Format, VideoInfo
        from app.services.yt_dlp_service import YtDlpService

        redis_mod._redis_available = False
        YtDlpService._formats_cache = None

        url = "https://www.youtube.com/watch?v=test123"
        video_info = VideoInfo(
            title="Test",
            thumbnail_url=None,
            duration_seconds=60,
            video_id="test123",
            formats=[Format(id="22", quality_label="720p", mime_type="video/mp4",
                           filesize_bytes=None, is_audio_only=False, is_video_only=False)],
        )
        YtDlpService._cache_set_formats(url, video_info)
        result = YtDlpService.get_cached_formats(url)
        assert result is not None
        assert result.title == "Test"

    def test_cache_set_writes_to_redis_when_available(self) -> None:
        from app.core import redis as redis_mod
        from app.models.video import Format, VideoInfo
        from app.services.yt_dlp_service import YtDlpService

        mock_redis = MagicMock()
        redis_mod._sync_client = mock_redis
        redis_mod._redis_available = True

        try:
            url = "https://www.youtube.com/watch?v=abc"
            video_info = VideoInfo(
                title="Redis Test",
                thumbnail_url=None,
                duration_seconds=30,
                video_id="abc",
                formats=[Format(id="22", quality_label="720p", mime_type="video/mp4",
                               filesize_bytes=None, is_audio_only=False, is_video_only=False)],
            )
            YtDlpService._cache_set_formats(url, video_info)
            mock_redis.setex.assert_called_once()
        finally:
            redis_mod._redis_available = False
            redis_mod._sync_client = None
