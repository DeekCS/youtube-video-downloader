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
from typing import Any, cast

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
    playlist_title: str = ""
    total_entries: int = 0
    completed_entries: int = 0
    current_entry: str = ""
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
        "playlist_title": task.playlist_title,
        "total_entries": str(task.total_entries),
        "completed_entries": str(task.completed_entries),
        "current_entry": task.current_entry,
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
        playlist_title=data.get("playlist_title", ""),
        total_entries=int(data.get("total_entries", "0")),
        completed_entries=int(data.get("completed_entries", "0")),
        current_entry=data.get("current_entry", ""),
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
            data = cast("dict[str, str]", r.hgetall(f"{_REDIS_KEY_PREFIX}{task_id}"))
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
                    created_at_raw = cast("str | None", r.hget(key, "created_at"))
                    if created_at_raw and now - float(created_at_raw) > max_age:
                        temp_dir = cast("str | None", r.hget(key, "temp_dir"))
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
        with _lock:
            removed_task: DownloadTask | None = _tasks.pop(tid, None)
        if removed_task and removed_task.temp_dir:
            shutil.rmtree(removed_task.temp_dir, ignore_errors=True)
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
