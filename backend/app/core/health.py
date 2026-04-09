"""Runtime dependency checks for the health endpoint."""

import shutil
import subprocess
from typing import Final

from app.core.version import __version__
from app.models.video import HealthResponse

_YTDLP_TIMEOUT_SEC: Final[float] = 5.0


def run_health_checks() -> HealthResponse:
    """Return health payload including ffmpeg and yt-dlp CLI availability."""
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

    deps_ok = ffmpeg_ok and ytdlp_cli_ok
    return HealthResponse(
        status="healthy" if deps_ok else "unhealthy",
        version=__version__,
        ffmpeg_ok=ffmpeg_ok,
        yt_dlp_cli_ok=ytdlp_cli_ok,
        yt_dlp_version=ytdlp_version,
    )
