# Redis Performance Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace in-memory task state and format cache with Redis, enabling 4 uvicorn workers, cache persistence across restarts, and adding 30s frontend API timeouts.

**Architecture:** Redis stores download task progress as hash keys (`ytdl:task:{id}`) with 2h TTL and format cache as string keys (`ytdl:formats:{sha256}`). All workers share the same Redis instance. In-memory dict and TTLCache are kept as automatic fallbacks when Redis is unavailable.

**Tech Stack:** `redis[hiredis]>=5.0.0` (sync + asyncio), `docker redis:7-alpine`, `AbortController` (browser-native)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/pyproject.toml` | Modify | Add `redis[hiredis]` dependency |
| `backend/app/core/config.py` | Modify | Add `REDIS_URL`, `REDIS_ENABLED` settings |
| `backend/app/core/redis.py` | **Create** | Connection pool, sync client, `init_redis`, `close_redis`, `is_redis_available` |
| `backend/app/services/download_tasks.py` | Modify | Add `update_task()`, make CRUD Redis-backed with in-memory fallback, add serialization helpers |
| `backend/app/services/yt_dlp_service.py` | Modify | Replace `TTLCache` reads/writes with Redis + TTLCache fallback; add throttled `update_task()` calls in progress loops |
| `backend/app/api/v1/endpoints/videos.py` | Modify | Call `update_task()` in `_run()` exception handler |
| `backend/app/main.py` | Modify | Call `init_redis()` / `close_redis()` in `lifespan` |
| `backend/app/models/video.py` | Modify | Add `redis_ok: bool` field to `HealthResponse` |
| `backend/app/core/health.py` | Modify | Ping Redis and include `redis_ok` in health response |
| `backend/Dockerfile` | Modify | Change `UVICORN_WORKERS=1` → `UVICORN_WORKERS=4` |
| `backend/.env.example` | Modify | Add `REDIS_URL`, `REDIS_ENABLED` entries |
| `docker-compose.yml` | Modify | Add Redis service; add resource limits; set `UVICORN_WORKERS=4`; add `REDIS_URL` |
| `frontend/lib/api-client.ts` | Modify | Wrap `fetchFormats` and `startDownload` with `AbortController` 30s timeout |
| `backend/tests/test_download_tasks.py` | Modify | Update `test_cleanup_stale` to use `update_task()` instead of direct field mutation |
| `backend/tests/test_redis_integration.py` | **Create** | Test Redis-backed CRUD, fallback to in-memory, format cache hit/miss |

---

## Task 1: Add redis dependency and config settings

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add redis to pyproject.toml**

In `backend/pyproject.toml`, add to `dependencies`:
```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "yt-dlp>=2024.12.0",
    "python-multipart>=0.0.12",
    "sse-starlette>=2.1.0",
    "cachetools>=5.3.0",
    "slowapi>=0.1.9",
    "redis[hiredis]>=5.0.0",
]
```

- [ ] **Step 2: Install the dependency**

```bash
cd backend
uv pip install --system redis[hiredis]
```

Expected: installs `redis` and `hiredis` without errors.

- [ ] **Step 3: Add config fields to config.py**

In `backend/app/core/config.py`, add after the `YTDLP_FORMATS_CACHE_MAXSIZE` field (before the closing of the `Settings` class):

```python
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (redis://host:port/db)",
    )
    REDIS_ENABLED: bool = Field(
        default=True,
        description="Set False to skip Redis and use in-memory fallback",
    )
```

- [ ] **Step 4: Add to .env.example**

Append to `backend/.env.example`:
```
# Redis (required for multi-worker support; set REDIS_ENABLED=false to disable)
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
```

- [ ] **Step 5: Commit**

```bash
cd /path/to/repo
git add backend/pyproject.toml backend/app/core/config.py backend/.env.example
git commit -m "chore: add redis dependency and config settings"
```

---

## Task 2: Create Redis connection module

**Files:**
- Create: `backend/app/core/redis.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_redis_integration.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_redis_integration.py::TestRedisModule -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` for `app.core.redis`.

- [ ] **Step 3: Create `backend/app/core/redis.py`**

```python
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

_sync_client: redis.Redis | None = None  # type: ignore[type-arg]
_async_client: aioredis.Redis | None = None  # type: ignore[type-arg]
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
            client: redis.Redis = redis.Redis.from_url(  # type: ignore[type-arg]
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


def close_redis() -> None:
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
            import asyncio
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(_async_client.aclose())
        except Exception:
            pass
        _async_client = None


def is_redis_available() -> bool:
    """Return True if Redis is connected and usable."""
    return _redis_available and _sync_client is not None


def get_sync_redis() -> "redis.Redis | None":  # type: ignore[type-arg]
    """Return the sync Redis client, or None if unavailable."""
    return _sync_client if _redis_available else None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
python -m pytest tests/test_redis_integration.py::TestRedisModule -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/redis.py backend/tests/test_redis_integration.py
git commit -m "feat: add Redis connection module with in-memory fallback"
```

---

## Task 3: Update download_tasks.py with Redis backing

**Files:**
- Modify: `backend/app/services/download_tasks.py`
- Modify: `backend/tests/test_download_tasks.py`

- [ ] **Step 1: Add Redis task tests**

Add to `backend/tests/test_redis_integration.py`:
```python
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
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_redis_integration.py::TestRedisDownloadTasks -v 2>&1 | head -30
```

Expected: `AttributeError: module has no attribute 'update_task'` or similar.

- [ ] **Step 3: Rewrite `backend/app/services/download_tasks.py`**

Replace the entire file with:

```python
"""Task store for tracking download progress.

Each merged download gets a ``DownloadTask`` that is updated in real-time
by the yt-dlp subprocess reader thread.  The SSE endpoint polls the task
and streams progress events to the browser.

State is persisted to Redis when available, enabling multiple uvicorn workers.
Falls back to an in-memory dict when Redis is unreachable.
"""

import shutil
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DownloadTask:
    """Tracks the state and progress of a single download."""

    task_id: str
    # Status values: pending | downloading | merging | completed | failed
    status: str = "pending"
    # Phase hints: video | audio | merge | (empty string)
    phase: str = ""
    # 0-100 overall estimated progress
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    file_path: str | None = None
    temp_dir: str | None = None
    filename: str = ""
    content_type: str = "video/mp4"
    file_size: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# In-memory store (fallback when Redis is unavailable)
# ---------------------------------------------------------------------------

_tasks: dict[str, DownloadTask] = {}
_lock = threading.Lock()

_REDIS_KEY_PREFIX = "ytdl:task:"
_REDIS_TTL = 7200  # 2 hours


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _task_to_dict(task: DownloadTask) -> dict[str, str]:
    """Serialize a DownloadTask to a flat string dict for Redis HSET."""
    return {
        "task_id": task.task_id,
        "status": task.status,
        "phase": task.phase,
        "progress": str(task.progress),
        "speed": task.speed,
        "eta": task.eta,
        "file_path": task.file_path or "",
        "temp_dir": task.temp_dir or "",
        "filename": task.filename,
        "content_type": task.content_type,
        "file_size": str(task.file_size),
        "downloaded_bytes": str(task.downloaded_bytes),
        "total_bytes": str(task.total_bytes),
        "error": task.error or "",
        "created_at": str(task.created_at),
    }


def _dict_to_task(data: dict[str, str]) -> DownloadTask:
    """Deserialize a Redis hash dict back to a DownloadTask."""
    return DownloadTask(
        task_id=data["task_id"],
        status=data.get("status", "pending"),
        phase=data.get("phase", ""),
        progress=float(data.get("progress", "0.0")),
        speed=data.get("speed", ""),
        eta=data.get("eta", ""),
        file_path=data.get("file_path") or None,
        temp_dir=data.get("temp_dir") or None,
        filename=data.get("filename", ""),
        content_type=data.get("content_type", "video/mp4"),
        file_size=int(data.get("file_size", "0")),
        downloaded_bytes=int(data.get("downloaded_bytes", "0")),
        total_bytes=int(data.get("total_bytes", "0")),
        error=data.get("error") or None,
        created_at=float(data.get("created_at", str(time.time()))),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_task(
    task_id: str,
    filename: str = "",
    content_type: str = "video/mp4",
) -> DownloadTask:
    """Create and register a new download task in Redis (with in-memory fallback)."""
    from app.core.redis import get_sync_redis

    task = DownloadTask(
        task_id=task_id,
        filename=filename,
        content_type=content_type,
    )

    r = get_sync_redis()
    if r is not None:
        try:
            r.hset(f"{_REDIS_KEY_PREFIX}{task_id}", mapping=_task_to_dict(task))
            r.expire(f"{_REDIS_KEY_PREFIX}{task_id}", _REDIS_TTL)
        except Exception as exc:
            logger.debug(f"Redis create_task error for {task_id}: {exc}")

    with _lock:
        _tasks[task_id] = task

    return task


def get_task(task_id: str) -> DownloadTask | None:
    """Fetch a task by ID — Redis first, in-memory fallback."""
    from app.core.redis import get_sync_redis

    r = get_sync_redis()
    if r is not None:
        try:
            data = r.hgetall(f"{_REDIS_KEY_PREFIX}{task_id}")
            if data:
                return _dict_to_task(data)
        except Exception as exc:
            logger.debug(f"Redis get_task error for {task_id}: {exc}")

    with _lock:
        return _tasks.get(task_id)


def update_task(task_id: str, **fields: Any) -> None:
    """Update specific fields on a task in Redis and in-memory store.

    Used by background download threads to push progress without holding
    a reference to the original DownloadTask object.
    """
    from app.core.redis import get_sync_redis

    r = get_sync_redis()
    if r is not None:
        try:
            str_fields = {
                k: str(v) if v is not None else ""
                for k, v in fields.items()
            }
            r.hset(f"{_REDIS_KEY_PREFIX}{task_id}", mapping=str_fields)
            r.expire(f"{_REDIS_KEY_PREFIX}{task_id}", _REDIS_TTL)
        except Exception as exc:
            logger.debug(f"Redis update_task error for {task_id}: {exc}")

    with _lock:
        task = _tasks.get(task_id)
        if task is not None:
            for k, v in fields.items():
                setattr(task, k, v)


def remove_task(task_id: str) -> DownloadTask | None:
    """Remove a task from the store and return it.

    Does **not** clean up temp files — the caller decides when to do that.
    """
    from app.core.redis import get_sync_redis

    r = get_sync_redis()
    if r is not None:
        try:
            r.delete(f"{_REDIS_KEY_PREFIX}{task_id}")
        except Exception as exc:
            logger.debug(f"Redis remove_task error for {task_id}: {exc}")

    with _lock:
        return _tasks.pop(task_id, None)


def cleanup_stale(max_age: int = 1800) -> None:
    """Remove tasks older than *max_age* seconds and delete their temp dirs."""
    from app.core.redis import get_sync_redis

    now = time.time()

    # Clean up Redis entries
    r = get_sync_redis()
    if r is not None:
        try:
            for key in r.scan_iter(f"{_REDIS_KEY_PREFIX}*", count=100):
                try:
                    created_at_raw = r.hget(key, "created_at")
                    if created_at_raw and now - float(created_at_raw) > max_age:
                        temp_dir = r.hget(key, "temp_dir")
                        r.delete(key)
                        if temp_dir:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            logger.info(f"Cleaned up stale Redis task {key}")
                except Exception:
                    pass
        except Exception as exc:
            logger.debug(f"Redis cleanup_stale scan error: {exc}")

    # Clean up in-memory entries
    stale_ids: list[str] = []
    with _lock:
        for tid, task in _tasks.items():
            if now - task.created_at > max_age:
                stale_ids.append(tid)

    for tid in stale_ids:
        task = remove_task(tid)
        if task and task.temp_dir:
            shutil.rmtree(task.temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up stale in-memory task {tid}")


def cleanup_all() -> None:
    """Remove ALL tasks and clean up their temp dirs. Called during graceful shutdown."""
    with _lock:
        all_ids = list(_tasks.keys())

    removed = 0
    for tid in all_ids:
        task = remove_task(tid)
        if task and task.temp_dir:
            shutil.rmtree(task.temp_dir, ignore_errors=True)
            removed += 1

    if removed:
        logger.info(f"Shutdown cleanup: removed {removed} download tasks")
```

- [ ] **Step 4: Update the existing cleanup_stale test in `backend/tests/test_download_tasks.py`**

The old test mutates `task.created_at` directly. Replace it with:

```python
def test_cleanup_stale_removes_old_tasks(self, tmp_path: object) -> None:
    from app.core import redis as redis_mod
    redis_mod._redis_available = False  # force in-memory for this test

    tid = "stale-1"
    dt.create_task(tid)
    # Use update_task instead of direct field mutation (works with Redis backend)
    dt.update_task(tid, created_at=time.time() - 4000, temp_dir=str(tmp_path))

    dt.cleanup_stale(max_age=3600)

    assert dt.get_task(tid) is None
```

- [ ] **Step 5: Run all download_tasks tests**

```bash
cd backend
python -m pytest tests/test_download_tasks.py tests/test_redis_integration.py::TestRedisDownloadTasks -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/download_tasks.py backend/tests/test_download_tasks.py backend/tests/test_redis_integration.py
git commit -m "feat: Redis-backed download task store with in-memory fallback"
```

---

## Task 4: Update YtDlpService — Redis format cache + throttled progress updates

**Files:**
- Modify: `backend/app/services/yt_dlp_service.py`

- [ ] **Step 1: Add format cache tests**

Add to `backend/tests/test_redis_integration.py`:
```python
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
```

- [ ] **Step 2: Run format cache tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_redis_integration.py::TestRedisFormatCache -v 2>&1 | head -20
```

Expected: `test_cache_set_writes_to_redis_when_available` fails (Redis write not yet implemented).

- [ ] **Step 3: Update `get_cached_formats` in yt_dlp_service.py**

Replace the existing `get_cached_formats` classmethod (lines ~86–92) with:

```python
@classmethod
def get_cached_formats(cls, url: str) -> VideoInfo | None:
    """Return cached VideoInfo for *url*, or None. Tries Redis first."""
    from app.core.redis import get_sync_redis

    normalized_url = cls.normalize_url(url)

    r = get_sync_redis()
    if r is not None and cls._cache_enabled():
        try:
            import hashlib
            key = f"ytdl:formats:{hashlib.sha256(normalized_url.encode()).hexdigest()}"
            raw = r.get(key)
            if raw:
                return VideoInfo.model_validate_json(raw)
        except Exception as exc:
            logger.debug(f"Redis format cache get error: {exc}")

    if not cls._cache_enabled():
        return None
    with cls._formats_cache_lock:
        return cls._get_cache().get(normalized_url)
```

- [ ] **Step 4: Update `_cache_set_formats` in yt_dlp_service.py**

Replace the existing `_cache_set_formats` classmethod (lines ~95–100) with:

```python
@classmethod
def _cache_set_formats(cls, normalized_url: str, video_info: VideoInfo) -> None:
    """Store *video_info* in Redis cache and in-memory fallback."""
    from app.core.redis import get_sync_redis

    r = get_sync_redis()
    if r is not None and cls._cache_enabled():
        try:
            import hashlib
            key = f"ytdl:formats:{hashlib.sha256(normalized_url.encode()).hexdigest()}"
            r.setex(key, settings.YTDLP_FORMATS_CACHE_TTL_SECONDS, video_info.model_dump_json())
        except Exception as exc:
            logger.debug(f"Redis format cache set error: {exc}")

    if not cls._cache_enabled():
        return
    with cls._formats_cache_lock:
        cls._get_cache()[normalized_url] = video_info
```

- [ ] **Step 5: Add throttled `update_task()` flush to `download_merged_with_progress`**

At the top of the `_read_stdout()` closure inside `download_merged_with_progress` (just before the `while True:` loop), add a throttle variable and helper. Replace the function from line ~847 (`def _read_stdout() -> None:`) through the end of the closure with:

```python
        def _read_stdout() -> None:
            """Background thread: parse yt-dlp stdout for progress."""
            nonlocal stream_index
            import time as _time
            from app.services.download_tasks import update_task as _update_task

            _last_flush = [0.0]

            def _flush(force: bool = False) -> None:
                now = _time.monotonic()
                if force or now - _last_flush[0] >= 1.0:
                    _update_task(
                        task.task_id,
                        status=task.status,
                        phase=task.phase,
                        progress=task.progress,
                        speed=task.speed,
                        eta=task.eta,
                        downloaded_bytes=task.downloaded_bytes,
                        total_bytes=task.total_bytes,
                    )
                    _last_flush[0] = now

            if process.stdout is None:
                return
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue

                    if DESTINATION_RE.search(line):
                        stream_index += 1
                        if is_two_stream:
                            task.phase = "video" if stream_index == 0 else "audio"
                        task.speed = ""
                        task.eta = ""
                        _flush(force=True)
                        continue

                    if MERGER_RE.search(line):
                        task.status = "merging"
                        task.phase = "merge"
                        task.progress = 92.0
                        task.speed = ""
                        task.eta = ""
                        _flush(force=True)
                        continue

                    pct_m = PROGRESS_PCT_RE.search(line)
                    if pct_m:
                        raw = float(pct_m.group(1))
                        if is_two_stream:
                            if stream_index <= 0:
                                task.progress = raw * 0.65
                            else:
                                task.progress = 65.0 + raw * 0.25
                        else:
                            task.progress = raw * 0.90
                        task.progress = min(task.progress, 91.0)

                        size_m = SIZE_OF_RE.search(line)
                        if size_m:
                            stream_bytes = parse_size_bytes(size_m.group(1), size_m.group(2))
                            if is_two_stream:
                                if stream_index <= 0:
                                    task.total_bytes = stream_bytes
                                elif stream_bytes > 0:
                                    base = task.total_bytes
                                    if base < stream_bytes * 5:
                                        task.total_bytes = base + stream_bytes
                            else:
                                task.total_bytes = stream_bytes
                            task.downloaded_bytes = int(task.total_bytes * task.progress / 100.0)

                        spd_m = SPEED_RE.search(line)
                        if spd_m:
                            task.speed = spd_m.group(1)
                        eta_m = ETA_RE.search(line)
                        if eta_m:
                            task.eta = eta_m.group(1)
                        _flush()
            except Exception:
                pass
```

Also update the `task.status = "failed"` / `task.status = "completed"` lines at the end of `download_merged_with_progress` to flush to Redis immediately. After each mutation block, add a `update_task()` call:

Replace the timeout block (~lines 931–935):
```python
        except subprocess.TimeoutExpired:
            process.kill()
            shutil.rmtree(temp_dir, ignore_errors=True)
            task.status = "failed"
            task.error = "Download timed out (1-hour limit)"
            from app.services.download_tasks import update_task as _update_task
            _update_task(task.task_id, status="failed", error="Download timed out (1-hour limit)")
            return
```

Replace the return_code != 0 block (~lines 939–946):
```python
        if return_code != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            task.status = "failed"
            task.error = "Download failed"
            from app.services.download_tasks import update_task as _update_task
            _update_task(task.task_id, status="failed", error="Download failed")
            logger.error(f"Progress download failed ({return_code}) for {safe_url}")
            return
```

Replace the no-files block (~lines 951–955) and the completion block (~lines 957–968):
```python
        files = [f for f in os.listdir(temp_dir) if not f.startswith(".")]
        if not files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            task.status = "failed"
            task.error = "Download produced no output"
            from app.services.download_tasks import update_task as _update_task
            _update_task(task.task_id, status="failed", error="Download produced no output")
            return

        paths = [os.path.join(temp_dir, f) for f in files]
        actual_path = max(paths, key=os.path.getsize)
        task.file_path = actual_path
        task.temp_dir = temp_dir
        task.file_size = os.path.getsize(actual_path)
        task.progress = 100.0
        task.status = "completed"
        task.speed = ""
        task.eta = ""
        from app.services.download_tasks import update_task as _update_task
        _update_task(
            task.task_id,
            file_path=actual_path,
            temp_dir=temp_dir,
            file_size=task.file_size,
            progress=100.0,
            status="completed",
            speed="",
            eta="",
        )
        logger.info(f"Progress download complete: {task.file_size:,} bytes for {safe_url}")
```

- [ ] **Step 6: Apply same flush pattern to `download_single_with_progress`**

In `download_single_with_progress`, replace `_read_stdout` closure with throttled version:

```python
        def _read_stdout() -> None:
            """Background thread: parse yt-dlp stdout for progress."""
            import time as _time
            from app.services.download_tasks import update_task as _update_task

            _last_flush = [0.0]

            def _flush(force: bool = False) -> None:
                now = _time.monotonic()
                if force or now - _last_flush[0] >= 1.0:
                    _update_task(
                        task.task_id,
                        progress=task.progress,
                        speed=task.speed,
                        eta=task.eta,
                        downloaded_bytes=task.downloaded_bytes,
                        total_bytes=task.total_bytes,
                        status=task.status,
                    )
                    _last_flush[0] = now

            if process.stdout is None:
                return
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue

                    pct_m = PROGRESS_PCT_RE.search(line)
                    if pct_m:
                        raw = float(pct_m.group(1))
                        task.progress = min(raw, 99.0)

                        size_m = SIZE_OF_RE.search(line)
                        if size_m:
                            task.total_bytes = parse_size_bytes(size_m.group(1), size_m.group(2))
                            task.downloaded_bytes = int(task.total_bytes * task.progress / 100.0)

                        spd_m = SPEED_RE.search(line)
                        if spd_m:
                            task.speed = spd_m.group(1)
                        eta_m = ETA_RE.search(line)
                        if eta_m:
                            task.eta = eta_m.group(1)
                        _flush()
            except Exception:
                pass
```

Also add `update_task()` calls at status-change points (timeout, failure, completion) following the same pattern as in `download_merged_with_progress` above.

Also add at the initial status set (~line 1040):
```python
        task.status = "downloading"
        task.phase = ""
        from app.services.download_tasks import update_task as _update_task
        _update_task(task.task_id, status="downloading", phase="")
```

Also add at the initial status set in `download_merged_with_progress` (~line 829):
```python
        task.status = "downloading"
        task.phase = "video" if is_two_stream else ""
        from app.services.download_tasks import update_task as _update_task
        _update_task(task.task_id, status="downloading", phase=task.phase)
```

- [ ] **Step 7: Run format cache and existing service tests**

```bash
cd backend
python -m pytest tests/test_redis_integration.py::TestRedisFormatCache tests/test_services.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/yt_dlp_service.py
git commit -m "feat: Redis format cache with TTLCache fallback; throttled progress flush to Redis"
```

---

## Task 5: Update videos.py — flush task state in _run() exception handler

**Files:**
- Modify: `backend/app/api/v1/endpoints/videos.py`

- [ ] **Step 1: Update imports at the top of videos.py**

Add `update_task` to the existing import from `download_tasks`:
```python
from app.services.download_tasks import (
    cleanup_stale,
    create_task,
    get_task,
    remove_task,
    update_task,
)
```

- [ ] **Step 2: Update the `_run()` exception handler in `start_download`**

Replace the existing `_run()` function (lines ~234–251):
```python
    def _run() -> None:
        try:
            if is_merged:
                YtDlpService.download_merged_with_progress(
                    normalized_url, body.format_id, task
                )
            else:
                YtDlpService.download_single_with_progress(
                    normalized_url, body.format_id, task
                )
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            update_task(task.task_id, status="failed", error=str(exc))
        finally:
            with _active_downloads_lock:
                if _active_downloads.get(dedup_key) == task_id:
                    del _active_downloads[dedup_key]
```

- [ ] **Step 3: Run the API tests**

```bash
cd backend
python -m pytest tests/test_api.py -v
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/endpoints/videos.py
git commit -m "feat: flush task failure state to Redis in download exception handler"
```

---

## Task 6: Update main.py lifespan to init/close Redis

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update the lifespan function**

Replace the existing `lifespan` function in `backend/app/main.py`:
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    from app.core.redis import close_redis, init_redis

    # Startup
    logger.info(f"Starting application in {settings.ENV} mode")
    logger.info(f"API v1 prefix: {settings.API_V1_PREFIX}")
    logger.info(f"CORS origins: {settings.cors_origins_list}")

    init_redis()
    _cleanup_orphaned_temp_dirs()

    yield

    # Shutdown
    logger.info("Shutting down application — cleaning up downloads…")
    cleanup_all()
    _cleanup_orphaned_temp_dirs()
    close_redis()
    logger.info("Shutdown complete")
```

- [ ] **Step 2: Verify app starts without Redis (graceful fallback)**

```bash
cd backend
REDIS_ENABLED=false python -c "
from app.main import create_app
app = create_app()
print('App created OK')
"
```

Expected: `App created OK` printed without errors.

- [ ] **Step 3: Run all tests**

```bash
cd backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass (Redis tests use mocks, not a live Redis server).

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: initialize and close Redis connection in app lifespan"
```

---

## Task 7: Add Redis health check

**Files:**
- Modify: `backend/app/models/video.py`
- Modify: `backend/app/core/health.py`

- [ ] **Step 1: Add `redis_ok` to HealthResponse model**

In `backend/app/models/video.py`, update `HealthResponse`:
```python
class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy"] = Field(
        default="healthy",
        description="Health status of the service",
    )
    version: str = Field(
        default="0.1.0",
        description="API version",
    )
    ffmpeg_ok: bool = Field(
        default=True,
        description="Whether the ffmpeg binary is available on PATH",
    )
    yt_dlp_cli_ok: bool = Field(
        default=True,
        description="Whether the yt-dlp CLI responds to --version",
    )
    yt_dlp_version: str | None = Field(
        default=None,
        description="Reported yt-dlp CLI version string, if available",
    )
    redis_ok: bool = Field(
        default=False,
        description="Whether Redis is reachable",
    )
```

- [ ] **Step 2: Update `run_health_checks` in health.py**

Replace the entire `backend/app/core/health.py` with:
```python
"""Runtime dependency checks for the health endpoint."""

import shutil
import subprocess
from typing import Final

from app.core.version import __version__
from app.models.video import HealthResponse

_YTDLP_TIMEOUT_SEC: Final[float] = 5.0


def run_health_checks() -> HealthResponse:
    """Return health payload including ffmpeg, yt-dlp CLI, and Redis availability."""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ytdlp_version: str | None = None
    ytdlp_cli_ok = False
    try:
        proc = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=_YTDLP_TIMEOUT_SEC,
            check=False,
        )
        if proc.returncode == 0 and (proc.stdout or "").strip():
            ytdlp_cli_ok = True
            ytdlp_version = (proc.stdout or "").strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired):
        ytdlp_cli_ok = False

    redis_ok = False
    try:
        from app.core.redis import get_sync_redis
        r = get_sync_redis()
        if r is not None:
            r.ping()
            redis_ok = True
    except Exception:
        redis_ok = False

    deps_ok = ffmpeg_ok and ytdlp_cli_ok
    return HealthResponse(
        status="healthy" if deps_ok else "unhealthy",
        version=__version__,
        ffmpeg_ok=ffmpeg_ok,
        yt_dlp_cli_ok=ytdlp_cli_ok,
        yt_dlp_version=ytdlp_version,
        redis_ok=redis_ok,
    )
```

- [ ] **Step 3: Run API tests**

```bash
cd backend
python -m pytest tests/test_api.py -v -k "health"
```

Expected: health tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/video.py backend/app/core/health.py
git commit -m "feat: add redis_ok field to health check response"
```

---

## Task 8: Update Dockerfile and docker-compose.yml

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update Dockerfile worker count**

In `backend/Dockerfile`, replace:
```dockerfile
# In-memory download tasks require a single worker unless you use external task storage.
ENV UVICORN_WORKERS=1
```
With:
```dockerfile
# Redis-backed task state enables multiple workers.
ENV UVICORN_WORKERS=4
```

- [ ] **Step 2: Update docker-compose.yml**

Replace the entire `docker-compose.yml` with:
```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: >
      redis-server
      --appendonly yes
      --maxmemory 128mb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    mem_limit: 192m

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENV=${ENV:-production}
      - DEBUG=${DEBUG:-false}
      - API_V1_PREFIX=/api/v1
      - CORS_ORIGINS=${CORS_ORIGINS:-http://localhost:3000}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - PORT=${PORT:-8000}
      - UVICORN_WORKERS=${UVICORN_WORKERS:-4}
      - REDIS_URL=redis://redis:6379/0
      - REDIS_ENABLED=true
      # yt-dlp speed tuning (aggressive + anti-throttling)
      - YTDLP_CONCURRENT_FRAGMENTS=32
      - YTDLP_HTTP_CHUNK_SIZE=
      - YTDLP_STREAM_CHUNK_SIZE=2097152
      - YTDLP_BUFFER_SIZE=1M
      - YTDLP_SOCKET_TIMEOUT=60
      - YTDLP_FILE_ACCESS_RETRIES=5
      - YTDLP_THROTTLED_RATE=50K
      - YTDLP_USE_IOS_CLIENT=false
      - YTDLP_YOUTUBE_PLAYER_CLIENT=tv_embedded
      - YTDLP_PREFER_FREE_FORMATS=true
      - YTDLP_USER_AGENT=Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    mem_limit: 1g

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_BASE: ${NEXT_PUBLIC_API_BASE:-http://localhost:8000/api/v1}
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=${NODE_ENV:-production}
      - NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE:-http://localhost:8000/api/v1}
      - PORT=3000
      - HOSTNAME=0.0.0.0
    command: node server.js
    depends_on:
      backend:
        condition: service_healthy

volumes:
  redis_data:

networks:
  default:
    name: video-downloader-network
```

- [ ] **Step 3: Verify docker-compose config is valid**

```bash
cd /path/to/repo
docker compose config --quiet
```

Expected: exits 0 with no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile docker-compose.yml
git commit -m "feat: enable 4 uvicorn workers; add Redis service to docker-compose"
```

---

## Task 9: Add AbortController timeouts to frontend API client

**Files:**
- Modify: `frontend/lib/api-client.ts`

- [ ] **Step 1: Update `fetchFormats` with timeout**

Replace the `fetchFormats` function (lines 83–127) in `frontend/lib/api-client.ts`:

```typescript
const API_TIMEOUT_MS = 30_000

/**
 * Fetch video formats from the backend.
 */
export async function fetchFormats(url: string): Promise<VideoInfo> {
  const validatedInput = FormatsRequestSchema.parse({ url })

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const response = await fetch(`${env.API_BASE}/videos/formats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: validatedInput.url }),
      signal: controller.signal,
    })

    const data = await response.json()

    if (!response.ok) {
      const errorData = ErrorResponseSchema.safeParse(data)
      if (errorData.success) {
        throw new ApiError(errorData.data.code, errorData.data.message, response.status)
      }
      throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred', response.status)
    }

    return VideoInfoSchema.parse(data)
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof z.ZodError) {
      throw new ApiError('INTERNAL_ERROR', 'Invalid response from server')
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('INTERNAL_ERROR', 'Request timed out after 30 seconds')
    }
    if (error instanceof Error) throw new ApiError('INTERNAL_ERROR', error.message)
    throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred')
  } finally {
    clearTimeout(timeoutId)
  }
}
```

- [ ] **Step 2: Update `startDownload` with timeout**

Replace the `startDownload` function (lines 164–193) in `frontend/lib/api-client.ts`:

```typescript
/**
 * Start a server-side download and receive a task id for SSE progress + file fetch.
 */
export async function startDownload(
  url: string,
  formatId: string
): Promise<{ downloadId: string; filename: string }> {
  const payload = StartDownloadRequestSchema.parse({
    url: url.trim(),
    format_id: formatId.trim(),
  })

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const response = await fetch(`${env.API_BASE}/videos/download/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: payload.url, format_id: payload.format_id }),
      signal: controller.signal,
    })

    const data: unknown = await response.json()

    if (!response.ok) {
      const parsed = ErrorResponseSchema.safeParse(data)
      if (parsed.success) {
        throw new ApiError(parsed.data.code, parsed.data.message, response.status)
      }
      throw new ApiError('INTERNAL_ERROR', 'Failed to start download', response.status)
    }

    const ok = StartDownloadResponseSchema.parse(data)
    return { downloadId: ok.download_id, filename: ok.filename }
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('INTERNAL_ERROR', 'Request timed out after 30 seconds')
    }
    if (error instanceof Error) throw new ApiError('INTERNAL_ERROR', error.message)
    throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred')
  } finally {
    clearTimeout(timeoutId)
  }
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors (exit 0).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api-client.ts
git commit -m "feat: add 30s AbortController timeout to fetchFormats and startDownload"
```

---

## Task 10: Run full test suite and verify

- [ ] **Step 1: Run all backend tests**

```bash
cd backend
python -m pytest tests/ -v --tb=short
```

Expected: all tests pass, no failures.

- [ ] **Step 2: Check mypy types**

```bash
cd backend
python -m mypy app/ --ignore-missing-imports 2>&1 | tail -20
```

Expected: no new type errors.

- [ ] **Step 3: Check ruff lint**

```bash
cd backend
python -m ruff check app/ tests/
```

Expected: no lint errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: ensure all tests pass after Redis integration

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Summary

After all tasks complete:

| What changed | Effect |
|---|---|
| Redis task store | Download progress visible across all 4 workers |
| Redis format cache | Cache survives restarts; shared across workers |
| 4 uvicorn workers | 4x concurrent request capacity |
| `docker-compose.yml` | Redis service included; `docker compose up` just works |
| Frontend 30s timeout | Hung requests surface as user-visible errors |
| Health endpoint | Reports `redis_ok` status |

To deploy to Railway: add a Redis service, set `REDIS_URL` env var on the backend service, deploy.
