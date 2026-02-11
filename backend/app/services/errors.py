"""Domain-specific exceptions for the services layer."""


class VideoDownloaderError(Exception):
    """Base exception for video downloader errors."""

    def __init__(self, message: str, code: str) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error message
            code: Stable error code for API responses
        """
        self.message = message
        self.code = code
        super().__init__(message)


class InvalidUrlError(VideoDownloaderError):
    """Raised when the provided URL is invalid or blocked."""

    def __init__(self, message: str = "The provided URL is invalid or blocked") -> None:
        super().__init__(message, "INVALID_URL")


class UnsupportedPlatformError(VideoDownloaderError):
    """Raised when the platform is not supported by yt-dlp."""

    def __init__(self, message: str = "This platform is not supported") -> None:
        super().__init__(message, "UNSUPPORTED_PLATFORM")


class VideoNotFoundError(VideoDownloaderError):
    """Raised when the video is not found or unavailable."""

    def __init__(self, message: str = "Video not found or unavailable") -> None:
        super().__init__(message, "NOT_FOUND")


class FormatNotAvailableError(VideoDownloaderError):
    """Raised when the requested format is not available."""

    def __init__(self, message: str = "The requested format is not available") -> None:
        super().__init__(message, "FORMAT_NOT_AVAILABLE")


class YtdlpFailedError(VideoDownloaderError):
    """Raised when yt-dlp execution fails unexpectedly."""

    def __init__(self, message: str = "Video processing failed") -> None:
        super().__init__(message, "YTDLP_FAILED")
