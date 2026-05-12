"""Tests for in-memory download task registry."""
import time

from app.services import download_tasks as dt


class TestDownloadTasks:
    def test_create_and_get_task(self) -> None:
        t = dt.create_task("abc", filename="x.mp4")
        assert t.task_id == "abc"
        assert t.filename == "x.mp4"
        got = dt.get_task("abc")
        assert got is not None
        assert got.task_id == "abc"

    def test_remove_task(self) -> None:
        dt.create_task("rm-me")
        removed = dt.remove_task("rm-me")
        assert removed is not None
        assert dt.get_task("rm-me") is None

    def test_cleanup_stale_removes_old_tasks(self, tmp_path: object) -> None:
        from app.core import redis as redis_mod
        redis_mod._redis_available = False  # force in-memory for this test

        tid = "stale-1"
        dt.create_task(tid)
        # Use update_task instead of direct field mutation (works with Redis backend)
        dt.update_task(tid, created_at=time.time() - 4000, temp_dir=str(tmp_path))

        dt.cleanup_stale(max_age=3600)

        assert dt.get_task(tid) is None
