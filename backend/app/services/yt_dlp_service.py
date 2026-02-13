"""yt-dlp integration service for video metadata extraction and downloads."""
import hashlib
import ipaddress
import json
import re
import subprocess
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

import yt_dlp

from app.core.config import settings
from app.core.logging import get_logger
from app.models.video import Format, VideoInfo
from app.services.errors import (
    FormatNotAvailableError,
    InvalidUrlError,
    UnsupportedPlatformError,
    VideoNotFoundError,
    YtdlpFailedError,
)

logger = get_logger(__name__)


class YtDlpService:
    """Service for interacting with yt-dlp."""

    _formats_cache: dict[str, tuple[float, VideoInfo]] = {}
    _formats_cache_lock = threading.Lock()

    @classmethod
    def _cache_get_formats(cls, normalized_url: str) -> VideoInfo | None:
        ttl = settings.YTDLP_FORMATS_CACHE_TTL_SECONDS
        maxsize = settings.YTDLP_FORMATS_CACHE_MAXSIZE
        if ttl <= 0 or maxsize <= 0:
            return None

        now = time.time()
        with cls._formats_cache_lock:
            cached = cls._formats_cache.get(normalized_url)
            if not cached:
                return None

            expires_at, video_info = cached
            if expires_at <= now:
                cls._formats_cache.pop(normalized_url, None)
                return None
            return video_info

    @classmethod
    def _cache_set_formats(cls, normalized_url: str, video_info: VideoInfo) -> None:
        ttl = settings.YTDLP_FORMATS_CACHE_TTL_SECONDS
        maxsize = settings.YTDLP_FORMATS_CACHE_MAXSIZE
        if ttl <= 0 or maxsize <= 0:
            return

        now = time.time()
        expires_at = now + ttl

        with cls._formats_cache_lock:
            cls._formats_cache[normalized_url] = (expires_at, video_info)

            # Best-effort pruning: drop expired first, then drop oldest.
            if len(cls._formats_cache) <= maxsize:
                return

            expired_keys = [k for k, (exp, _) in cls._formats_cache.items() if exp <= now]
            for k in expired_keys:
                cls._formats_cache.pop(k, None)

            if len(cls._formats_cache) <= maxsize:
                return

            # Remove entries with earliest expiry until within maxsize.
            overflow = len(cls._formats_cache) - maxsize
            for k, _ in sorted(cls._formats_cache.items(), key=lambda item: item[1][0])[:overflow]:
                cls._formats_cache.pop(k, None)

    @classmethod
    def get_cached_formats(cls, url: str) -> VideoInfo | None:
        normalized_url = cls.normalize_url(url)
        return cls._cache_get_formats(normalized_url)

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize and validate a URL for safety.

        Args:
            url: Raw URL string from user input

        Returns:
            Normalized URL string

        Raises:
            InvalidUrlError: If URL is malformed or blocked
        """
        url = url.strip()

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            logger.warning(f"Failed to parse URL: {e}")
            raise InvalidUrlError("Malformed URL")

        # Validate scheme
        if parsed.scheme.lower() not in settings.allowed_schemes_list:
            raise InvalidUrlError(
                f"URL scheme not allowed. Allowed schemes: {', '.join(settings.allowed_schemes_list)}"
            )

        # Validate hostname
        if not parsed.hostname:
            raise InvalidUrlError("URL must have a valid hostname")

        # SSRF protection: block private networks
        if settings.BLOCK_PRIVATE_NETWORKS:
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    logger.warning(f"Blocked private network URL: {parsed.hostname}")
                    raise InvalidUrlError("Private network URLs are not allowed")
            except ValueError:
                # Not an IP address, hostname is OK
                pass

            # Block localhost and common private hostnames
            blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
            if parsed.hostname.lower() in blocked_hosts:
                raise InvalidUrlError("Localhost URLs are not allowed")

        return url

    @staticmethod
    def _sanitize_url_for_logging(url: str) -> str:
        """Create a safe version of URL for logging (hide query params).

        Args:
            url: Full URL

        Returns:
            Sanitized URL string for logging
        """
        try:
            parsed = urlparse(url)
            # Create hash of full URL for tracking
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
            return f"{parsed.scheme}://{parsed.hostname}{parsed.path} (hash:{url_hash})"
        except Exception:
            return "invalid-url"

    @staticmethod
    def _normalize_format(raw_format: dict[str, Any]) -> Format:
        """Normalize a yt-dlp format dict to our Format model.

        Args:
            raw_format: Raw format dict from yt-dlp

        Returns:
            Normalized Format instance
        """
        # Extract format ID (prefer format_id over id)
        format_id = str(raw_format.get("format_id") or raw_format.get("id") or "unknown")

        # Build quality label
        quality_label = raw_format.get("format_note") or raw_format.get("quality") or "unknown"
        if raw_format.get("height"):
            quality_label = f"{raw_format['height']}p"
        elif raw_format.get("abr"):  # Audio bitrate
            quality_label = f"{int(raw_format['abr'])}kbps"

        # Determine mime type
        ext = raw_format.get("ext", "unknown")
        vcodec = raw_format.get("vcodec", "none")
        acodec = raw_format.get("acodec", "none")

        if vcodec != "none" and acodec != "none":
            mime_type = f"video/{ext}"
        elif vcodec != "none":
            mime_type = f"video/{ext}"
        elif acodec != "none":
            mime_type = f"audio/{ext}"
        else:
            mime_type = f"application/{ext}"

        # Some platforms report container-only streams without codec info.
        # Treat common video containers as video for UI/selection purposes.
        if mime_type.startswith("application/") and ext in {"mp4", "m4v", "mov"}:
            mime_type = f"video/{ext}"

        # File size (may not be available)
        filesize = raw_format.get("filesize") or raw_format.get("filesize_approx")

        # Audio/video only flags
        is_audio_only = acodec != "none" and vcodec == "none"
        is_video_only = vcodec != "none" and acodec == "none"

        return Format(
            id=format_id,
            quality_label=quality_label,
            mime_type=mime_type,
            filesize_bytes=filesize,
            is_audio_only=is_audio_only,
            is_video_only=is_video_only,
        )

    @classmethod
    def fetch_formats(cls, url: str) -> VideoInfo:
        """Fetch video metadata and available formats.

        Args:
            url: Video URL to fetch formats for

        Returns:
            VideoInfo with title, thumbnail, duration, and formats

        Raises:
            InvalidUrlError: If URL is invalid or blocked
            UnsupportedPlatformError: If platform not supported
            VideoNotFoundError: If video not found
            YtdlpFailedError: If yt-dlp fails unexpectedly
        """
        # Normalize and validate URL
        url = cls.normalize_url(url)

        # Fast path: serve from short-lived cache
        cached = cls._cache_get_formats(url)
        if cached is not None:
            return cached

        safe_url = cls._sanitize_url_for_logging(url)

        logger.info(f"Fetching formats for: {safe_url}")

        # Configure yt-dlp options with speed optimizations
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,  # Only download single video, not playlists
            "extract_flat": False,
            # Speed optimizations (applied to format extraction too)
            "concurrent_fragments": settings.YTDLP_CONCURRENT_FRAGMENTS,
            "fragment_retries": settings.YTDLP_FRAGMENT_RETRIES,
            "socket_timeout": settings.YTDLP_SOCKET_TIMEOUT,
        }

        # Prefer free formats if configured
        if settings.YTDLP_PREFER_FREE_FORMATS:
            ydl_opts["prefer_free_formats"] = True

        # User agent spoofing
        if settings.YTDLP_USER_AGENT:
            ydl_opts["http_headers"] = {"User-Agent": settings.YTDLP_USER_AGENT}

        # Advanced YouTube extractor arguments
        # Note: For format listing, DON'T use iOS client as it can cause extraction failures
        # iOS client should only be used during actual downloads for anti-throttling
        youtube_extractor_args: dict[str, Any] = {}

        # Note: Don't force DASH formats or iOS client during format extraction
        # These optimizations are only applied during actual downloads in build_download_command

        if youtube_extractor_args:
            ydl_opts["extractor_args"] = {"youtube": youtube_extractor_args}

        # Add browser cookies if configured
        if settings.YTDLP_COOKIES_FROM_BROWSER:
            ydl_opts["cookiesfrombrowser"] = (settings.YTDLP_COOKIES_FROM_BROWSER,)

        # Add proxy if configured
        if settings.YTDLP_PROXY:
            ydl_opts["proxy"] = settings.YTDLP_PROXY

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise VideoNotFoundError()

                # Extract video metadata
                title = info.get("title", "Unknown Title")
                thumbnail = info.get("thumbnail")
                duration_raw = info.get("duration")  # in seconds
                duration = None
                if isinstance(duration_raw, (int, float)):
                    duration = int(duration_raw)

                # Extract and normalize formats
                raw_formats = info.get("formats", [])
                if not raw_formats:
                    raise FormatNotAvailableError("No formats available for this video")

                # Filter and normalize formats (exclude formats without format_id)
                formats: list[Format] = []
                seen_ids: set[str] = set()

                for raw_fmt in raw_formats:
                    try:
                        fmt = cls._normalize_format(raw_fmt)
                        # Deduplicate by format ID
                        if fmt.id not in seen_ids and fmt.id != "unknown":
                            formats.append(fmt)
                            seen_ids.add(fmt.id)
                    except Exception as e:
                        logger.debug(f"Skipping malformed format: {e}")
                        continue

                if not formats:
                    raise FormatNotAvailableError("No valid formats found")

                # Add special merged selectors that combine video+audio via ffmpeg
                merged_formats = []

                # Collect available video resolutions (both combined and video-only)
                available_heights: set[int] = set()
                for f in formats:
                    match = re.search(r"(\d+)p", f.quality_label)
                    if match and "video" in f.mime_type:
                        available_heights.add(int(match.group(1)))

                # Define merged quality tiers (highest first)
                merge_tiers = [
                    (2160, "4K Ultra HD (2160p)", "merged-2160"),
                    (1440, "QHD (1440p)",         "merged-1440"),
                    (1080, "Full HD (1080p)",      "merged-1080"),
                    (720,  "HD (720p)",            "merged-720"),
                    (480,  "SD (480p)",            "merged-480"),
                ]

                # Always add a "Best Quality" merged option
                merged_formats.append(Format(
                    id="bestvideo+bestaudio/best",
                    quality_label="Best Available (Merged)",
                    mime_type="video/mp4",
                    filesize_bytes=None,
                    is_audio_only=False,
                    is_video_only=False,
                ))

                for height, label, fmt_id in merge_tiers:
                    if height in available_heights:
                        merged_formats.append(Format(
                            id=f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
                            quality_label=f"{label} (Merged)",
                            mime_type="video/mp4",
                            filesize_bytes=None,
                            is_audio_only=False,
                            is_video_only=False,
                        ))

                # Prepend merged formats to the list
                formats = merged_formats + formats

                # Sort formats: merged first (best available first, then by resolution desc),
                # then video formats (by quality), then audio
                def _sort_height(f: Format) -> int:
                    """Extract resolution height for sorting. Uses NNNp pattern to avoid '4' from '4K'."""
                    m = re.search(r"(\d+)p", f.quality_label)
                    return int(m.group(1)) if m else 0

                formats.sort(
                    key=lambda f: (
                        0 if "best available" in f.quality_label.lower() else (
                            1 if "merged" in f.quality_label.lower() else 2
                        ),
                        f.is_audio_only,  # Audio last
                        -_sort_height(f),
                    )
                )

                logger.info(f"Successfully fetched {len(formats)} formats for: {safe_url}")

                video_info = VideoInfo(
                    title=title,
                    thumbnail_url=thumbnail,
                    duration_seconds=duration,
                    formats=formats,
                )

                cls._cache_set_formats(url, video_info)
                return video_info

        except yt_dlp.utils.UnsupportedError as e:
            logger.warning(f"Unsupported platform for {safe_url}: {e}")
            raise UnsupportedPlatformError(str(e))

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "unavailable" in error_msg or "private" in error_msg:
                logger.warning(f"Video not found: {safe_url}")
                raise VideoNotFoundError()
            elif "requested format is not available" in error_msg or "format" in error_msg:
                # This can happen with livestreams or region-restricted content
                logger.warning(f"Format not available for {safe_url}: {e}")
                # Try to provide a more helpful error message
                if "/live/" in url or "livestream" in error_msg:
                    raise YtdlpFailedError("This livestream may not be available yet or has ended. Please try again later.")
                else:
                    raise FormatNotAvailableError(f"No formats available: {e}")
            else:
                logger.error(f"yt-dlp download error for {safe_url}: {e}")
                raise YtdlpFailedError(f"Failed to fetch video information: {e}")

        except (FormatNotAvailableError, InvalidUrlError, UnsupportedPlatformError, VideoNotFoundError):
            # Re-raise domain exceptions as-is
            raise

        except Exception as e:
            logger.error(f"Unexpected error fetching formats for {safe_url}: {e}", exc_info=True)
            raise YtdlpFailedError(f"Unexpected error: {e}")

    @classmethod
    def download_format(
        cls,
        url: str,
        format_id: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None
    ) -> subprocess.Popen[bytes]:
        """Start streaming download of a specific format.

        Args:
            url: Video URL
            format_id: Format ID to download
            progress_callback: Optional callback for progress updates

        Returns:
            Subprocess handle streaming to stdout

        Raises:
            InvalidUrlError: If URL is invalid
            YtdlpFailedError: If download fails to start
        """
        cmd = cls.build_download_command(url=url, format_id=format_id, progress=bool(progress_callback))
        safe_url = cls._sanitize_url_for_logging(cls.normalize_url(url))
        logger.info(f"Starting download for format {format_id} from {safe_url}")

        try:
            # Start subprocess with stdout pipe
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return process

        except Exception as e:
            logger.error(f"Failed to start download process for {safe_url}: {e}")
            raise YtdlpFailedError(f"Failed to start download: {e}")

    @classmethod
    def build_download_command(cls, url: str, format_id: str, progress: bool = False) -> list[str]:
        """Build a yt-dlp command that streams the selected format to stdout."""
        normalized_url = cls.normalize_url(url)

        # Determine if this is a merged format (video+audio via ffmpeg)
        format_spec = format_id
        is_merged_format = (
            "+" in format_id
            or format_id in ["best", "bestvideo", "bestaudio"]
            or format_id.startswith("bestvideo[")
            or format_id.startswith("best[")
        )

        cmd: list[str] = [
            "yt-dlp",
            "-f", format_spec,
            "-o", "-",  # Output to stdout
            "-c",  # Continue/resume interrupted downloads
            "--no-warnings",
            "--quiet",
            "--no-playlist",
            "--concurrent-fragments", str(settings.YTDLP_CONCURRENT_FRAGMENTS),
            "--throttled-rate", settings.YTDLP_THROTTLED_RATE,  # Auto-bypass throttling
            "--buffer-size", settings.YTDLP_BUFFER_SIZE,
            "--socket-timeout", str(settings.YTDLP_SOCKET_TIMEOUT),
            "--retries", str(settings.YTDLP_RETRIES),
            "--fragment-retries", str(settings.YTDLP_FRAGMENT_RETRIES),
            "--extractor-retries", str(settings.YTDLP_EXTRACTOR_RETRIES),
            "--file-access-retries", str(settings.YTDLP_FILE_ACCESS_RETRIES),
        ]

        # Network optimizations
        if settings.YTDLP_SLEEP_REQUESTS > 0:
            cmd.extend(["--sleep-requests", str(settings.YTDLP_SLEEP_REQUESTS)])

        # User agent spoofing
        if settings.YTDLP_USER_AGENT:
            cmd.extend(["--user-agent", settings.YTDLP_USER_AGENT])

        # Prefer free formats
        if settings.YTDLP_PREFER_FREE_FORMATS:
            cmd.append("--prefer-free-formats")

        if settings.YTDLP_HTTP_CHUNK_SIZE:
            cmd.extend(["--http-chunk-size", settings.YTDLP_HTTP_CHUNK_SIZE])

        # SponsorBlock: skip sponsor segments to reduce download time
        if settings.YTDLP_SPONSORBLOCK_REMOVE:
            cmd.extend(["--sponsorblock-remove", settings.YTDLP_SPONSORBLOCK_REMOVE])

        # If this is a merged format (video+audio), tell yt-dlp to merge into MP4
        if is_merged_format:
            cmd.extend(["--merge-output-format", "mp4"])

        # Advanced YouTube extractor arguments for better anti-throttling
        # Note: iOS client can cause "format not available" errors for some videos
        # Only use it as a fallback, not by default
        extractor_args = []

        # Note: Don't use player_skip by default as it can cause extraction failures
        # Note: Don't force DASH formats by default as it can cause compatibility issues
        # These optimizations should be enabled selectively based on video/platform

        if extractor_args:
            cmd.extend(["--extractor-args", f"youtube:{','.join(extractor_args)}"])

        # Use browser cookies if configured (can bypass throttling)
        if settings.YTDLP_COOKIES_FROM_BROWSER:
            cmd.extend(["--cookies-from-browser", settings.YTDLP_COOKIES_FROM_BROWSER])

        # Add proxy if configured (can help with regional throttling)
        if settings.YTDLP_PROXY:
            cmd.extend(["--proxy", settings.YTDLP_PROXY])

        if progress:
            cmd.extend(["--newline", "--progress"])

        cmd.append(normalized_url)
        return cmd
