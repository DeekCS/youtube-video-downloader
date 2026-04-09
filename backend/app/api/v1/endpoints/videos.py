"""Video-related API endpoints."""
import asyncio
import json
import os
import re
import shutil
import threading
import uuid
from collections.abc import AsyncIterator
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.models.video import DownloadRequest, FormatsRequest, VideoInfo
from app.services.download_tasks import (
    cleanup_stale,
    create_task,
    get_task,
    remove_task,
)
from app.services.yt_dlp_service import YtDlpService

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/formats",
    response_model=VideoInfo,
    status_code=status.HTTP_200_OK,
    summary="Fetch video formats",
    description="Retrieve metadata and available formats for a video URL",
    responses={
        200: {
            "description": "Successfully retrieved video information and formats",
            "model": VideoInfo,
        },
        400: {"description": "Invalid URL"},
        404: {"description": "Video not found"},
        422: {"description": "Unsupported platform"},
        429: {"description": "Rate limit exceeded"},
        502: {"description": "yt-dlp failed to process the video"},
    },
)
@limiter.limit("10/minute")
async def fetch_formats(request: Request, body: FormatsRequest) -> VideoInfo:
    """Fetch available formats for a video URL.

    Args:
        request: Request containing the video URL

    Returns:
        Video metadata and list of available formats

    Raises:
        Various VideoDownloaderError exceptions (handled by global handler)
    """
    # Run blocking yt-dlp call in a thread to avoid blocking the event loop
    video_info = await asyncio.to_thread(YtDlpService.fetch_formats, body.url)
    return video_info


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe use in Content-Disposition header.

    Args:
        filename: Raw filename

    Returns:
        Sanitized filename safe for headers (ASCII only)
    """
    # Remove or replace unsafe characters - only keep ASCII alphanumeric, spaces, hyphens, dots
    # Use ASCII flag to ensure only ASCII characters are matched
    filename = re.sub(r'[^a-zA-Z0-9\s\-\.]', '', filename, flags=re.ASCII)
    # Replace whitespace with underscores
    filename = re.sub(r'\s+', '_', filename)
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename or "download"


def _build_content_disposition(filename: str) -> str:
    """Build Content-Disposition header with proper encoding for non-ASCII filenames.

    Uses RFC 5987 encoding to support Unicode filenames while maintaining
    compatibility with older browsers.

    Args:
        filename: Original filename (may contain Unicode characters)

    Returns:
        Properly encoded Content-Disposition header value
    """
    # Create ASCII-safe fallback
    ascii_filename = _sanitize_filename(filename)

    # URL-encode the original filename for modern browsers (RFC 5987)
    # This preserves Unicode characters by percent-encoding them
    # Use safe='' to encode all special characters including spaces
    encoded_filename = quote(filename, safe='')

    # Return header with both formats for maximum compatibility
    # filename= for older browsers, filename*= for modern browsers
    return f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"


async def _stream_file(
    file_path: str,
    temp_dir: str,
) -> AsyncIterator[bytes]:
    """Stream a temp file to the client, then clean up.

    Args:
        file_path: Path to the downloaded file
        temp_dir: Temp directory to remove after streaming

    Yields:
        Chunks of file data
    """
    chunk_size = settings.YTDLP_STREAM_CHUNK_SIZE
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = await asyncio.to_thread(f.read, chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



# ---------------------------------------------------------------------------
# Progress-tracked download endpoints (all formats)
# ---------------------------------------------------------------------------

# Deduplication: map (url, format_id) -> existing download_id so that rapid
# repeated requests for the same format are coalesced into a single task.
_active_downloads: dict[tuple[str, str], str] = {}
_active_downloads_lock = threading.Lock()


@router.post(
    "/download/start",
    summary="Start a download with progress tracking",
    description="Starts a download in the background (merged or single-stream) and returns a download ID for progress tracking",
    responses={
        200: {"description": "Download started"},
        400: {"description": "Invalid request"},
        404: {"description": "Format not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("5/minute")
async def start_download(request: Request, body: DownloadRequest) -> dict:
    """Start a download with progress tracking.

    Returns a ``download_id`` the client uses to poll progress via SSE
    and ultimately fetch the completed file.  If an identical download is
    already in flight, the existing task ID is returned so the client
    simply re-subscribes to the existing SSE stream.

    Handles **all** formats (merged and single-stream).  By downloading
    to server disk first, the browser receives the file over a fast
    local transfer instead of being exposed to YouTube throttling.
    """
    # Housekeeping: remove stale tasks
    cleanup_stale()

    video_info = YtDlpService.get_cached_formats(body.url)
    if video_info is None:
        video_info = await asyncio.to_thread(
            YtDlpService.fetch_formats, body.url
        )

    selected_format = next(
        (fmt for fmt in video_info.formats if fmt.id == body.format_id),
        None,
    )
    if not selected_format:
        from app.services.errors import FormatNotAvailableError

        raise FormatNotAvailableError(
            f"Format '{body.format_id}' not found in available formats"
        )

    dedup_key = (body.url, body.format_id)
    is_merged = YtDlpService.is_merged_format(body.format_id)

    # Determine filename and content type based on format type
    if is_merged:
        ext = "mp4"
        content_type = "video/mp4"
    else:
        ext = selected_format.mime_type.split("/")[-1]
        content_type = selected_format.mime_type or "application/octet-stream"

    filename = f"{video_info.title}.{ext}"

    # --- Deduplication: return existing task if still active ---
    with _active_downloads_lock:
        existing_id = _active_downloads.get(dedup_key)
        if existing_id:
            existing_task = get_task(existing_id)
            if existing_task and existing_task.status not in ("completed", "failed"):
                logger.info(
                    f"Reusing existing download task {existing_id} for {dedup_key[1]}"
                )
                return {"download_id": existing_id, "filename": existing_task.filename}
        # No live task — create a new one
        task_id = uuid.uuid4().hex[:16]
        _active_downloads[dedup_key] = task_id

    task = create_task(task_id, filename=filename, content_type=content_type)

    def _run() -> None:
        try:
            if is_merged:
                YtDlpService.download_merged_with_progress(
                    body.url, body.format_id, task
                )
            else:
                YtDlpService.download_single_with_progress(
                    body.url, body.format_id, task
                )
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
        finally:
            # Release the deduplication slot once the download is finished
            with _active_downloads_lock:
                if _active_downloads.get(dedup_key) == task_id:
                    del _active_downloads[dedup_key]

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"download_id": task_id, "filename": filename}


@router.get(
    "/download/{download_id}/progress",
    summary="Stream download progress via SSE",
    description="Server-Sent Events stream with real-time download progress",
)
async def download_progress(
    download_id: str, request: Request
) -> EventSourceResponse:
    """SSE endpoint streaming progress events for a download task."""
    task = get_task(download_id)
    if not task:
        raise HTTPException(status_code=404, detail="Download not found")

    async def _event_generator():
        while True:
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected for task {download_id}")
                break

            t = get_task(download_id)
            if not t:
                break

            data = {
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

    return EventSourceResponse(_event_generator())


@router.get(
    "/download/{download_id}/file",
    summary="Download completed file",
    description="Serve a completed download file and clean up server resources",
    responses={
        200: {"description": "File stream"},
        404: {"description": "Download not found"},
        409: {"description": "Download not yet complete"},
    },
)
async def download_file(download_id: str) -> StreamingResponse:
    """Serve the completed file for a finished download task."""
    task = get_task(download_id)
    if not task:
        raise HTTPException(status_code=404, detail="Download not found")

    if task.status != "completed":
        raise HTTPException(
            status_code=409, detail="Download not yet complete"
        )

    if not task.file_path or not os.path.exists(task.file_path):
        remove_task(download_id)
        raise HTTPException(
            status_code=410, detail="File no longer available"
        )

    filename = task.filename
    content_type = task.content_type
    file_size = task.file_size
    file_path = task.file_path
    temp_dir = task.temp_dir or os.path.dirname(file_path)

    # Remove from task store; _stream_file cleans the temp dir after streaming
    remove_task(download_id)

    return StreamingResponse(
        _stream_file(file_path, temp_dir),
        media_type=content_type,
        headers={
            "Content-Disposition": _build_content_disposition(filename),
            "Content-Length": str(file_size),
        },
    )
