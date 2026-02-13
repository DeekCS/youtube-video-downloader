"""yt-dlp integration service for video metadata extraction and downloads."""

import hashlib
import ipaddress
import re
import subprocess
import threading
from typing import Any, Callable
from urllib.parse import urlparse

import yt_dlp
from cachetools import TTLCache

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CODEC_NONE = "none"
CODEC_UNKNOWN = "unknown"
FORMAT_ID_UNKNOWN = "unknown"

MIME_VIDEO_PREFIX = "video/"
MIME_AUDIO_PREFIX = "audio/"
MIME_APPLICATION_PREFIX = "application/"

VIDEO_CONTAINER_EXTS = {"mp4", "m4v", "mov"}

BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

# Regex for safe format-id values (prevents command injection)
FORMAT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9+\[\]<>=^:/\-_.]+$")

# Merged quality tiers: (height, label, internal_id)
MERGE_TIERS = [
    (2160, "4K Ultra HD (2160p)", "merged-2160"),
    (1440, "QHD (1440p)",         "merged-1440"),
    (1080, "Full HD (1080p)",      "merged-1080"),
    (720,  "HD (720p)",            "merged-720"),
    (480,  "SD (480p)",            "merged-480"),
]


class YtDlpService:
    """Service for interacting with yt-dlp."""

    _formats_cache: TTLCache | None = None
    _formats_cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Cache helpers (backed by cachetools.TTLCache)
    # ------------------------------------------------------------------

    @classmethod
    def _get_cache(cls) -> TTLCache:
        """Lazy-initialise and return the TTL cache."""
        if cls._formats_cache is None:
            cls._formats_cache = TTLCache(
                maxsize=max(1, settings.YTDLP_FORMATS_CACHE_MAXSIZE),
                ttl=max(1, settings.YTDLP_FORMATS_CACHE_TTL_SECONDS),
            )
        return cls._formats_cache

    @classmethod
    def _cache_enabled(cls) -> bool:
        """Return True when caching is configured on."""
        return (
            settings.YTDLP_FORMATS_CACHE_TTL_SECONDS > 0
            and settings.YTDLP_FORMATS_CACHE_MAXSIZE > 0
        )

    @classmethod
    def get_cached_formats(cls, url: str) -> VideoInfo | None:
        """Return cached VideoInfo for *url*, or None."""
        normalized_url = cls.normalize_url(url)
        if not cls._cache_enabled():
            return None
        with cls._formats_cache_lock:
            return cls._get_cache().get(normalized_url)

    @classmethod
    def _cache_set_formats(cls, normalized_url: str, video_info: VideoInfo) -> None:
        """Store *video_info* in the cache under *normalized_url*."""
        if not cls._cache_enabled():
            return
        with cls._formats_cache_lock:
            cls._get_cache()[normalized_url] = video_info

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

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

        try:
            parsed = urlparse(url)
        except Exception as e:
            logger.warning(f"Failed to parse URL: {e}")
            raise InvalidUrlError("Malformed URL")

        if parsed.scheme.lower() not in settings.allowed_schemes_list:
            raise InvalidUrlError(
                f"URL scheme not allowed. Allowed schemes: "
                f"{', '.join(settings.allowed_schemes_list)}"
            )

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

            if parsed.hostname.lower() in BLOCKED_HOSTNAMES:
                raise InvalidUrlError("Localhost URLs are not allowed")

        return url

    @staticmethod
    def _sanitize_url_for_logging(url: str) -> str:
        """Create a safe version of URL for logging (hide query params)."""
        try:
            parsed = urlparse(url)
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
            return f"{parsed.scheme}://{parsed.hostname}{parsed.path} (hash:{url_hash})"
        except Exception:
            return "invalid-url"

    # ------------------------------------------------------------------
    # Format normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_quality_label(raw_format: dict[str, Any]) -> str:
        """Extract human-readable quality label from format dict."""
        if height := raw_format.get("height"):
            return f"{height}p"
        if abr := raw_format.get("abr"):
            return f"{int(abr)}kbps"
        return (
            raw_format.get("format_note")
            or raw_format.get("quality")
            or CODEC_UNKNOWN
        )

    @staticmethod
    def _determine_mime_type(raw_format: dict[str, Any]) -> str:
        """Determine MIME type from format metadata."""
        ext = raw_format.get("ext", CODEC_UNKNOWN)
        vcodec = raw_format.get("vcodec", CODEC_NONE)
        acodec = raw_format.get("acodec", CODEC_NONE)

        if vcodec != CODEC_NONE:
            return f"{MIME_VIDEO_PREFIX}{ext}"
        if acodec != CODEC_NONE:
            return f"{MIME_AUDIO_PREFIX}{ext}"
        # Container-only streams: treat common video containers as video
        if ext in VIDEO_CONTAINER_EXTS:
            return f"{MIME_VIDEO_PREFIX}{ext}"
        return f"{MIME_APPLICATION_PREFIX}{ext}"

    @staticmethod
    def _normalize_format(raw_format: dict[str, Any]) -> Format:
        """Normalize a yt-dlp format dict to our Format model."""
        format_id = str(
            raw_format.get("format_id")
            or raw_format.get("id")
            or FORMAT_ID_UNKNOWN
        )
        quality_label = YtDlpService._extract_quality_label(raw_format)
        mime_type = YtDlpService._determine_mime_type(raw_format)
        filesize = raw_format.get("filesize") or raw_format.get("filesize_approx")

        vcodec = raw_format.get("vcodec", CODEC_NONE)
        acodec = raw_format.get("acodec", CODEC_NONE)

        return Format(
            id=format_id,
            quality_label=quality_label,
            mime_type=mime_type,
            filesize_bytes=filesize,
            is_audio_only=(acodec != CODEC_NONE and vcodec == CODEC_NONE),
            is_video_only=(vcodec != CODEC_NONE and acodec == CODEC_NONE),
        )

    @classmethod
    def _normalize_formats(
        cls, raw_formats: list[dict[str, Any]]
    ) -> list[Format]:
        """Normalize and deduplicate formats from yt-dlp output."""
        if not raw_formats:
            raise FormatNotAvailableError("No formats available for this video")

        formats: list[Format] = []
        seen_ids: set[str] = set()

        for raw_fmt in raw_formats:
            try:
                fmt = cls._normalize_format(raw_fmt)
                if fmt.id not in seen_ids and fmt.id != FORMAT_ID_UNKNOWN:
                    formats.append(fmt)
                    seen_ids.add(fmt.id)
            except Exception as e:
                logger.debug(f"Skipping malformed format: {e}")
                continue

        if not formats:
            raise FormatNotAvailableError("No valid formats found")

        return formats

    # ------------------------------------------------------------------
    # Merged-format construction
    # ------------------------------------------------------------------

    @staticmethod
    def _create_merged_formats(formats: list[Format]) -> list[Format]:
        """Create merged format options (video+audio via ffmpeg).

        Prefer H.264 (avc1) + AAC (mp4a) codecs for maximum player
        compatibility (QuickTime, iOS, older browsers), with fallbacks
        to any available codec combination.
        """
        merged_formats: list[Format] = []

        available_heights: set[int] = {
            int(match.group(1))
            for f in formats
            if (match := re.search(r"(\d+)p", f.quality_label))
            and MIME_VIDEO_PREFIX in f.mime_type
        }

        # Best-available merged option
        merged_formats.append(Format(
            id=(
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                "/bestvideo[vcodec^=avc1]+bestaudio"
                "/bestvideo+bestaudio/best"
            ),
            quality_label="Best Available (Merged)",
            mime_type="video/mp4",
            filesize_bytes=None,
            is_audio_only=False,
            is_video_only=False,
        ))

        # Resolution-specific merged formats
        for height, label, _fmt_id in MERGE_TIERS:
            if height in available_heights:
                merged_formats.append(Format(
                    id=(
                        f"bestvideo[height<={height}][vcodec^=avc1]"
                        f"+bestaudio[acodec^=mp4a]"
                        f"/bestvideo[height<={height}][vcodec^=avc1]+bestaudio"
                        f"/bestvideo[height<={height}]+bestaudio"
                        f"/best[height<={height}]/best"
                    ),
                    quality_label=f"{label} (Merged)",
                    mime_type="video/mp4",
                    filesize_bytes=None,
                    is_audio_only=False,
                    is_video_only=False,
                ))

        return merged_formats

    @staticmethod
    def _sort_formats(formats: list[Format]) -> None:
        """Sort formats in-place: merged first, then by quality descending."""

        def _sort_key(f: Format) -> tuple:
            height_match = re.search(r"(\d+)p", f.quality_label)
            height = int(height_match.group(1)) if height_match else 0
            priority = (
                0 if "best available" in f.quality_label.lower()
                else 1 if "merged" in f.quality_label.lower()
                else 2
            )
            return (priority, f.is_audio_only, -height)

        formats.sort(key=_sort_key)

    # ------------------------------------------------------------------
    # yt-dlp option builders
    # ------------------------------------------------------------------

    @classmethod
    def _build_ydl_options(cls) -> dict[str, Any]:
        """Build yt-dlp configuration options for format extraction."""
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
            "concurrent_fragments": settings.YTDLP_CONCURRENT_FRAGMENTS,
            "fragment_retries": settings.YTDLP_FRAGMENT_RETRIES,
            "socket_timeout": settings.YTDLP_SOCKET_TIMEOUT,
        }

        if settings.YTDLP_PREFER_FREE_FORMATS:
            ydl_opts["prefer_free_formats"] = True

        if settings.YTDLP_USER_AGENT:
            ydl_opts["http_headers"] = {"User-Agent": settings.YTDLP_USER_AGENT}

        if settings.YTDLP_COOKIES_FROM_BROWSER:
            ydl_opts["cookiesfrombrowser"] = (settings.YTDLP_COOKIES_FROM_BROWSER,)

        if settings.YTDLP_PROXY:
            ydl_opts["proxy"] = settings.YTDLP_PROXY

        return ydl_opts

    # ------------------------------------------------------------------
    # Video info extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_duration(duration_raw: Any) -> int | None:
        """Extract and validate duration in seconds."""
        if isinstance(duration_raw, (int, float)):
            return int(duration_raw)
        return None

    @classmethod
    def _extract_video_info(cls, info: dict[str, Any]) -> VideoInfo:
        """Extract and normalize video information from yt-dlp output."""
        title = info.get("title", "Unknown Title")
        thumbnail = info.get("thumbnail")
        duration = cls._extract_duration(info.get("duration"))

        formats = cls._normalize_formats(info.get("formats", []))
        merged_formats = cls._create_merged_formats(formats)
        all_formats = merged_formats + formats
        cls._sort_formats(all_formats)

        return VideoInfo(
            title=title,
            thumbnail_url=thumbnail,
            duration_seconds=duration,
            formats=all_formats,
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @classmethod
    def _handle_fetch_error(
        cls, error: Exception, safe_url: str, url: str
    ) -> None:
        """Handle and transform yt-dlp errors into domain exceptions.

        Always raises; return type is ``None`` only for the type-checker.
        """
        if isinstance(error, yt_dlp.utils.UnsupportedError):
            logger.warning(f"Unsupported platform for {safe_url}: {error}")
            raise UnsupportedPlatformError(str(error))

        if isinstance(error, yt_dlp.utils.DownloadError):
            error_msg = str(error).lower()

            if any(kw in error_msg for kw in ("not found", "unavailable", "private")):
                logger.warning(f"Video not found: {safe_url}")
                raise VideoNotFoundError()

            if "livestream" in error_msg or "/live/" in url:
                raise YtdlpFailedError(
                    "This livestream may not be available yet or has ended. "
                    "Please try again later."
                )

            if "format" in error_msg:
                logger.warning(f"Format not available for {safe_url}: {error}")
                raise FormatNotAvailableError(f"No formats available: {error}")

            logger.error(f"yt-dlp download error for {safe_url}: {error}")
            raise YtdlpFailedError(f"Failed to fetch video information: {error}")

        if isinstance(
            error,
            (
                FormatNotAvailableError,
                InvalidUrlError,
                UnsupportedPlatformError,
                VideoNotFoundError,
            ),
        ):
            raise error

        logger.error(
            f"Unexpected error fetching formats for {safe_url}: {error}",
            exc_info=True,
        )
        raise YtdlpFailedError(f"Unexpected error: {error}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        url = cls.normalize_url(url)

        cached = cls.get_cached_formats(url)
        if cached is not None:
            return cached

        safe_url = cls._sanitize_url_for_logging(url)
        logger.info(f"Fetching formats for: {safe_url}")

        ydl_opts = cls._build_ydl_options()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise VideoNotFoundError()

                video_info = cls._extract_video_info(info)
                cls._cache_set_formats(url, video_info)

                logger.info(
                    f"Successfully fetched {len(video_info.formats)} formats "
                    f"for: {safe_url}"
                )
                return video_info

        except (
            FormatNotAvailableError,
            InvalidUrlError,
            UnsupportedPlatformError,
            VideoNotFoundError,
        ):
            raise

        except Exception as e:
            cls._handle_fetch_error(e, safe_url, url)
            # _handle_fetch_error always raises; this satisfies the
            # type-checker.
            raise  # pragma: no cover

    @classmethod
    def download_format(
        cls,
        url: str,
        format_id: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> subprocess.Popen[bytes]:
        """Start streaming download of a specific format.

        Args:
            url: Video URL
            format_id: Format ID to download
            progress_callback: Optional callback for progress updates

        Returns:
            Subprocess handle streaming to stdout

        Raises:
            InvalidUrlError: If URL or format_id is invalid
            YtdlpFailedError: If download fails to start
        """
        # Validate format_id to prevent command injection
        if not FORMAT_ID_PATTERN.match(format_id):
            raise InvalidUrlError("Invalid format_id")

        cmd = cls.build_download_command(
            url=url, format_id=format_id, progress=bool(progress_callback),
        )
        safe_url = cls._sanitize_url_for_logging(cls.normalize_url(url))
        logger.info(f"Starting download for format {format_id} from {safe_url}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # Prevent signal propagation
            )
            return process

        except Exception as e:
            logger.error(f"Failed to start download process for {safe_url}: {e}")
            raise YtdlpFailedError(f"Failed to start download: {e}")

    @classmethod
    def build_download_command(
        cls, url: str, format_id: str, progress: bool = False,
    ) -> list[str]:
        """Build a yt-dlp command that streams the selected format to stdout."""
        normalized_url = cls.normalize_url(url)

        format_spec = format_id
        is_merged_format = (
            "+" in format_id
            or format_id in ("best", "bestvideo", "bestaudio")
            or format_id.startswith("bestvideo[")
            or format_id.startswith("best[")
        )

        cmd: list[str] = [
            "yt-dlp",
            "-f", format_spec,
            "-o", "-",  # Output to stdout
            "-c",       # Continue/resume interrupted downloads
            "--no-warnings",
            "--quiet",
            "--no-playlist",
            "--concurrent-fragments", str(settings.YTDLP_CONCURRENT_FRAGMENTS),
            "--throttled-rate", settings.YTDLP_THROTTLED_RATE,
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

        # Merged format: merge into MP4 with QuickTime-compatible atom layout
        if is_merged_format:
            cmd.extend(["--merge-output-format", "mp4"])
            # Format selectors already prefer H.264 + AAC codecs.
            # Move moov atom to front for QuickTime compatibility.
            cmd.extend(["--ppa", "Merger+:-movflags +faststart"])

        # Browser cookies (can bypass throttling)
        if settings.YTDLP_COOKIES_FROM_BROWSER:
            cmd.extend(["--cookies-from-browser", settings.YTDLP_COOKIES_FROM_BROWSER])

        # Proxy (can help with regional throttling)
        if settings.YTDLP_PROXY:
            cmd.extend(["--proxy", settings.YTDLP_PROXY])

        if progress:
            cmd.extend(["--newline", "--progress"])

        cmd.append(normalized_url)
        return cmd
