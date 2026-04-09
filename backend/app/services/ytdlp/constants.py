"""Shared constants and compiled regexes for yt-dlp integration."""

import re

CODEC_NONE = "none"
CODEC_UNKNOWN = "unknown"
FORMAT_ID_UNKNOWN = "unknown"

MIME_VIDEO_PREFIX = "video/"
MIME_AUDIO_PREFIX = "audio/"
MIME_APPLICATION_PREFIX = "application/"

VIDEO_CONTAINER_EXTS = {"mp4", "m4v", "mov"}

BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

FORMAT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9+\[\]<>=^:/\-_.]+$")

MERGE_TIERS: list[tuple[int, str, str]] = [
    (2160, "4K Ultra HD (2160p)", "merged-2160"),
    (1440, "QHD (1440p)", "merged-1440"),
    (1080, "Full HD (1080p)", "merged-1080"),
    (720, "HD (720p)", "merged-720"),
    (480, "SD (480p)", "merged-480"),
]

PROGRESS_PCT_RE = re.compile(r"\[download\]\s+([\d.]+)%")
SIZE_OF_RE = re.compile(r"of\s+~?([\d.]+)\s*(\S+)")
SPEED_RE = re.compile(r"at\s+([\d.]+\s*\S+/s)")
ETA_RE = re.compile(r"ETA\s+(\S+)")
DESTINATION_RE = re.compile(r"\[download\]\s+Destination:")
MERGER_RE = re.compile(r"\[Merger\]")
