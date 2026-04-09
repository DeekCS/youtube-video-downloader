"""Disk space checks and yt-dlp progress size parsing."""

import shutil
import tempfile
from typing import Final

from app.services.errors import YtdlpFailedError

_SIZE_UNITS: Final[dict[str, float]] = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "kB": 1000,
    "k": 1000,
}

_MIN_FREE_DISK_BYTES = 500 * 1024 * 1024


def parse_size_bytes(value: str, unit: str) -> int:
    """Convert a size string like '422.93' + 'KiB' to integer bytes."""
    multiplier = _SIZE_UNITS.get(unit, 1)
    try:
        return int(float(value) * multiplier)
    except (ValueError, OverflowError):
        return 0


def check_disk_space() -> None:
    """Raise if temp directory disk is too full for a download."""
    free = shutil.disk_usage(tempfile.gettempdir()).free
    if free < _MIN_FREE_DISK_BYTES:
        free_mb = free // (1024 * 1024)
        raise YtdlpFailedError(
            f"Server disk space too low ({free_mb} MB free). "
            f"Please try again later."
        )
