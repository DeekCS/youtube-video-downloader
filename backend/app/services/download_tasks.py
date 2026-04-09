"""In-memory task store for tracking download progress.

Each merged download gets a ``DownloadTask`` that is updated in real-time
by the yt-dlp subprocess reader thread.  The SSE endpoint polls the task
and streams progress events to the browser.
"""

import shutil
import threading
import time
from dataclasses import dataclass, field

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
# Global store  (dict + lock keeps things simple for a self-hosted app)
# ---------------------------------------------------------------------------

_tasks: dict[str, DownloadTask] = {}
_lock = threading.Lock()


def create_task(
    task_id: str,
    filename: str = "",
    content_type: str = "video/mp4",
) -> DownloadTask:
    """Create and register a new download task."""
    task = DownloadTask(
        task_id=task_id,
        filename=filename,
        content_type=content_type,
    )
    with _lock:
        _tasks[task_id] = task
    return task


def get_task(task_id: str) -> DownloadTask | None:
    """Get a task by ID (returns ``None`` if not found)."""
    with _lock:
        return _tasks.get(task_id)


def remove_task(task_id: str) -> DownloadTask | None:
    """Remove a task from the store and return it.

    Does **not** clean up temp files — the caller decides when to do that.
    """
    with _lock:
        return _tasks.pop(task_id, None)


def cleanup_stale(max_age: int = 1800) -> None:
    """Remove tasks older than *max_age* seconds and delete their temp dirs."""
    now = time.time()
    stale_ids: list[str] = []
    with _lock:
        for tid, task in _tasks.items():
            if now - task.created_at > max_age:
                stale_ids.append(tid)

    for tid in stale_ids:
        task = remove_task(tid)
        if task and task.temp_dir:
            shutil.rmtree(task.temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up stale download task {tid}")


def cleanup_all() -> None:
    """Remove ALL tasks and clean up their temp dirs.

    Called during graceful shutdown to ensure no orphaned temp
    directories remain on disk.
    """
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

