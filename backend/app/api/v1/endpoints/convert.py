"""File conversion endpoints using ffmpeg."""
import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections.abc import AsyncIterator
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.services.download_tasks import (
    cleanup_stale,
    create_task,
    get_task,
    remove_task,
)

logger = get_logger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Format configuration
# ---------------------------------------------------------------------------

SUPPORTED_INPUT_EXTENSIONS = {
    "mp4", "mkv", "webm", "avi", "mov", "flv", "wmv", "mpeg", "mpg",
    "3gp", "m4v", "ts", "mp3", "aac", "m4a", "wav", "ogg", "flac", "opus",
}

OUTPUT_FORMATS: dict[str, dict] = {
    "mp4": {
        "ext": "mp4",
        "mime": "video/mp4",
        "ffmpeg_args": ["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart"],
    },
    "mkv": {
        "ext": "mkv",
        "mime": "video/x-matroska",
        "ffmpeg_args": ["-c:v", "copy", "-c:a", "copy"],
    },
    "webm": {
        "ext": "webm",
        "mime": "video/webm",
        "ffmpeg_args": ["-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0", "-c:a", "libopus"],
    },
    "avi": {
        "ext": "avi",
        "mime": "video/x-msvideo",
        "ffmpeg_args": ["-c:v", "mpeg4", "-c:a", "mp3"],
    },
    "mov": {
        "ext": "mov",
        "mime": "video/quicktime",
        "ffmpeg_args": ["-c:v", "copy", "-c:a", "copy"],
    },
    "mp3": {
        "ext": "mp3",
        "mime": "audio/mpeg",
        "ffmpeg_args": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    },
    "aac": {
        "ext": "aac",
        "mime": "audio/aac",
        "ffmpeg_args": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    },
    "m4a": {
        "ext": "m4a",
        "mime": "audio/mp4",
        "ffmpeg_args": ["-vn", "-c:a", "aac", "-movflags", "+faststart"],
    },
    "wav": {
        "ext": "wav",
        "mime": "audio/wav",
        "ffmpeg_args": ["-vn", "-c:a", "pcm_s16le"],
    },
    "ogg": {
        "ext": "ogg",
        "mime": "audio/ogg",
        "ffmpeg_args": ["-vn", "-c:a", "libvorbis", "-q:a", "4"],
    },
    "flac": {
        "ext": "flac",
        "mime": "audio/flac",
        "ffmpeg_args": ["-vn", "-c:a", "flac"],
    },
}

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_filename(name: str) -> str:
    """Return a filesystem-safe ASCII filename (no directory separators)."""
    name = re.sub(r"[^a-zA-Z0-9\s\-\.]", "", name, flags=re.ASCII)
    name = re.sub(r"\s+", "_", name)
    return (name[:200] if len(name) > 200 else name) or "output"


def _probe_duration(input_path: str) -> float:
    """Return total duration in seconds via ffprobe (0.0 on failure)."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip() or 0)
    except Exception:
        return 0.0


def _run_ffmpeg_conversion(
    task_id: str,
    input_path: str,
    output_path: str,
    ffmpeg_args: list[str],
) -> None:
    """Run ffmpeg in a background thread and update task progress via out_time_ms."""
    task = get_task(task_id)
    if task is None:
        return

    duration_s = _probe_duration(input_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        *ffmpeg_args,
        "-progress", "pipe:1",
        "-nostats",
        output_path,
    ]

    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    ms = int(line.split("=", 1)[1])
                    current_s = ms / 1_000_000
                    if duration_s > 0:
                        pct = min(99.0, (current_s / duration_s) * 100)
                        task.progress = pct
                        task.status = "converting"
                        task.phase = "converting"
                except ValueError:
                    pass
            elif line == "progress=end":
                break

        proc.wait(timeout=3600)

        if proc.returncode != 0:
            stderr_out = proc.stderr.read() if proc.stderr else ""  # type: ignore[union-attr]
            logger.error("ffmpeg failed for task %s: %s", task_id, stderr_out[:500])
            task.status = "failed"
            task.error = "Conversion failed"
            return

        task.status = "completed"
        task.progress = 100.0
        task.file_path = output_path
        task.file_size = os.path.getsize(output_path)

    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        task.status = "failed"
        task.error = "Conversion timed out"
    except Exception as exc:
        logger.exception("Conversion error for task %s: %s", task_id, exc)
        task.status = "failed"
        task.error = str(exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/start",
    summary="Upload a file and start conversion",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Unsupported format or file type"},
        413: {"description": "File too large (> 2 GB)"},
    },
)
async def start_conversion(
    file: UploadFile = File(...),
    target_format: str = Form(...),
) -> dict:
    """Upload a local video/audio file and convert it to *target_format*.

    Returns ``{task_id, filename}`` — poll ``/{task_id}/progress`` (SSE) for
    progress and fetch ``/{task_id}/file`` when status is *completed*.
    """
    cleanup_stale()

    # --- validate target format ---
    target_format = target_format.lower().strip()
    if target_format not in OUTPUT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported output format '{target_format}'. "
                f"Supported: {', '.join(sorted(OUTPUT_FORMATS))}"
            ),
        )

    # --- validate input extension ---
    original_filename = (file.filename or "upload").strip()
    if "." not in original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have an extension.",
        )
    ext = original_filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_INPUT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported input file type '.{ext}'.",
        )

    # --- create temp dir ---
    temp_dir = tempfile.mkdtemp(prefix="ytdl_conv_")
    task_id = str(uuid.uuid4())

    base_name = original_filename.rsplit(".", 1)[0]
    out_ext = OUTPUT_FORMATS[target_format]["ext"]
    out_filename = f"{_sanitize_filename(base_name)}.{out_ext}"

    input_path = os.path.join(temp_dir, f"input.{ext}")
    output_path = os.path.join(temp_dir, out_filename)

    # --- stream upload to disk (avoid OOM for large files) ---
    total_bytes = 0
    try:
        with open(input_path, "wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large. Maximum upload size is 2 GB.",
                    )
                fh.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from exc

    # --- register task ---
    mime = OUTPUT_FORMATS[target_format]["mime"]
    task = create_task(task_id, filename=out_filename, content_type=mime)
    task.temp_dir = temp_dir
    task.status = "pending"

    # --- launch conversion thread ---
    ffmpeg_args = OUTPUT_FORMATS[target_format]["ffmpeg_args"]
    threading.Thread(
        target=_run_ffmpeg_conversion,
        args=(task_id, input_path, output_path, ffmpeg_args),
        daemon=True,
    ).start()

    return {"task_id": task_id, "filename": out_filename}


@router.get(
    "/{task_id}/progress",
    summary="SSE progress stream for a conversion task",
    description="Server-Sent Events stream using the same schema as /videos/download/{id}/progress",
)
async def conversion_progress(request: Request, task_id: str) -> EventSourceResponse:
    """Stream conversion progress events (same schema as download progress SSE)."""
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async def _gen() -> AsyncIterator[dict]:
        while True:
            if await request.is_disconnected():
                break

            t = get_task(task_id)
            if not t:
                break

            data: dict = {
                "status": t.status,
                "progress": round(t.progress, 1),
                "phase": t.phase,
                "speed": t.speed,
                "eta": t.eta,
                "file_size": t.file_size,
                "downloaded_bytes": t.downloaded_bytes,
                "total_bytes": t.total_bytes,
            }
            if t.error:
                data["error"] = t.error

            yield {"event": "progress", "data": json.dumps(data)}

            if t.status in ("completed", "failed"):
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(_gen())


@router.get(
    "/{task_id}/file",
    summary="Download the converted file",
    responses={
        200: {"description": "Converted file stream"},
        404: {"description": "Task not found"},
        409: {"description": "Conversion not yet complete"},
        410: {"description": "File no longer available"},
    },
)
async def get_converted_file(task_id: str) -> StreamingResponse:
    """Serve the completed converted file and clean up temp files after streaming."""
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="Conversion not yet complete")
    if not task.file_path or not os.path.exists(task.file_path):
        remove_task(task_id)
        raise HTTPException(status_code=410, detail="File no longer available")

    filename = task.filename
    content_type = task.content_type
    file_size = task.file_size
    file_path = task.file_path
    temp_dir = task.temp_dir or os.path.dirname(file_path)

    remove_task(task_id)

    ascii_name = _sanitize_filename(filename)
    encoded_name = quote(filename, safe="")
    content_disposition = (
        f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
    )

    async def _stream() -> AsyncIterator[bytes]:
        chunk_size = settings.YTDLP_STREAM_CHUNK_SIZE
        try:
            with open(file_path, "rb") as fh:
                while True:
                    chunk = await asyncio.to_thread(fh.read, chunk_size)
                    if not chunk:
                        break
                    yield chunk
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    headers: dict[str, str] = {"Content-Disposition": content_disposition}
    if file_size:
        headers["Content-Length"] = str(file_size)

    return StreamingResponse(
        _stream(),
        media_type=content_type,
        headers=headers,
    )
