"""Video-related API endpoints."""
import asyncio
import os
import re
import shutil
import threading
from typing import Any, AsyncIterator
from urllib.parse import quote

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.models.video import DownloadRequest, FormatsRequest, VideoInfo
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
        502: {"description": "yt-dlp failed to process the video"},
    },
)
async def fetch_formats(request: FormatsRequest) -> VideoInfo:
    """Fetch available formats for a video URL.

    Args:
        request: Request containing the video URL

    Returns:
        Video metadata and list of available formats

    Raises:
        Various VideoDownloaderError exceptions (handled by global handler)
    """
    # Run blocking yt-dlp call in a thread to avoid blocking the event loop
    video_info = await asyncio.to_thread(YtDlpService.fetch_formats, request.url)
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
        def _read_chunks() -> bytes:
            with open(file_path, "rb") as f:
                return f.read(chunk_size)

        with open(file_path, "rb") as f:
            while True:
                chunk = await asyncio.to_thread(f.read, chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _stream_download(
    url: str,
    format_id: str,
    filename: str,
) -> AsyncIterator[bytes]:
    """Stream video download from yt-dlp subprocess.

    Args:
        url: Video URL
        format_id: Format ID to download
        filename: Base filename for logging

    Yields:
        Chunks of video data
    """
    chunk_size = settings.YTDLP_STREAM_CHUNK_SIZE

    process = YtDlpService.download_format(url, format_id)

    stderr_buffer = bytearray()
    stderr_limit = 64 * 1024  # keep last ~64KB for error logs
    stderr_stop = threading.Event()

    def _drain_stderr_blocking() -> None:
        if process.stderr is None:
            return
        try:
            while not stderr_stop.is_set():
                data = process.stderr.read(4096)
                if not data:
                    break
                if len(stderr_buffer) < stderr_limit:
                    remaining = stderr_limit - len(stderr_buffer)
                    stderr_buffer.extend(data[:remaining])
        except Exception:
            # Best-effort; stderr draining is non-critical
            return

    stderr_thread = threading.Thread(target=_drain_stderr_blocking, daemon=True)
    stderr_thread.start()

    try:
        while True:
            if process.stdout is None:
                break

            chunk = await asyncio.to_thread(process.stdout.read, chunk_size)
            if not chunk:
                break
            yield chunk

        return_code = await asyncio.to_thread(process.wait)

        if return_code != 0:
            stderr_text = stderr_buffer.decode(errors="replace")
            logger.error(
                f"yt-dlp download failed ({return_code}) for {filename}: {stderr_text}"
            )

    except Exception as e:
        logger.error(f"Error during download stream: {e}")
        # Terminate the process if still running
        if process.poll() is None:
            process.terminate()
            await asyncio.to_thread(process.wait)
        raise

    finally:
        # Ensure cleanup
        stderr_stop.set()
        if process.poll() is None:
            process.terminate()
            await asyncio.to_thread(process.wait)
        # Give the stderr drainer a moment to exit
        stderr_thread.join(timeout=0.5)


@router.post(
    "/download",
    summary="Download video (POST)",
    description="Download a video in the specified format (POST method)",
    responses={
        200: {"description": "Video file stream"},
        400: {"description": "Invalid request"},
        404: {"description": "Video or format not found"},
        502: {"description": "Download failed"},
    },
)
async def download_video_post(request: DownloadRequest) -> StreamingResponse:
    """Download a video in the specified format.

    Args:
        request: Download request with URL and format ID

    Returns:
        Streaming response with video file
    """
    # Prefer cached info from /formats to reduce slow-start latency
    video_info = YtDlpService.get_cached_formats(request.url)
    if video_info is None:
        video_info = await asyncio.to_thread(YtDlpService.fetch_formats, request.url)

    # Find the requested format
    selected_format = next(
        (fmt for fmt in video_info.formats if fmt.id == request.format_id),
        None,
    )

    if not selected_format:
        from app.services.errors import FormatNotAvailableError
        raise FormatNotAvailableError(
            f"Format '{request.format_id}' not found in available formats"
        )

    # Build filename - keep original title for proper encoding
    is_merged_format = (
        "+" in request.format_id
        or request.format_id in {"best", "bestvideo"}
        or request.format_id.startswith("best[")
        or request.format_id.startswith("bestvideo[")
    )
    if is_merged_format:
        ext = "mp4"
        content_type = "video/mp4"
    else:
        ext = selected_format.mime_type.split("/")[-1]
        content_type = selected_format.mime_type or "application/octet-stream"
    filename = f"{video_info.title}.{ext}"

    logger.info(f"Streaming download: {filename} ({request.format_id})")

    if is_merged_format:
        # Merged formats: download to temp file first, then stream.
        # yt-dlp/ffmpeg can't pipe proper MP4 to stdout (falls back to
        # MPEG-TS).  Temp-file lets ffmpeg write real MP4 with faststart.
        file_path, temp_dir = await asyncio.to_thread(
            YtDlpService.download_merged_to_file,
            request.url,
            request.format_id,
        )
        file_size = os.path.getsize(file_path)

        return StreamingResponse(
            _stream_file(file_path, temp_dir),
            media_type=content_type,
            headers={
                "Content-Disposition": _build_content_disposition(filename),
                "Content-Length": str(file_size),
                "X-Format-ID": request.format_id,
            },
        )

    # Single-stream formats: pipe directly from yt-dlp stdout.
    return StreamingResponse(
        _stream_download(request.url, request.format_id, filename),
        media_type=content_type,
        headers={
            "Content-Disposition": _build_content_disposition(filename),
            "X-Format-ID": request.format_id,
        },
    )


@router.get(
    "/download",
    summary="Download video (GET)",
    description="Download a video in the specified format (GET method for browser navigation)",
    responses={
        200: {"description": "Video file stream"},
        400: {"description": "Invalid request"},
        404: {"description": "Video or format not found"},
        502: {"description": "Download failed"},
    },
)
async def download_video_get(
    url: str = Query(..., description="Video URL", min_length=10, max_length=2048),
    format_id: str = Query(..., description="Format ID from formats list", min_length=1, max_length=500),
) -> StreamingResponse:
    """Download a video via GET request (for browser navigation).

    Args:
        url: Video URL
        format_id: Format ID to download

    Returns:
        Streaming response with video file
    """
    # Reuse the POST endpoint logic
    request = DownloadRequest(url=url, format_id=format_id)
    return await download_video_post(request)




