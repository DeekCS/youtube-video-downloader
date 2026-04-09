"""YouTube-specific yt-dlp extractor / CLI options."""

from typing import Any

from app.core.config import settings


def youtube_player_clients() -> list[str] | None:
    """Return explicit YouTube player_client list, or None for yt-dlp defaults."""
    raw = settings.YTDLP_YOUTUBE_PLAYER_CLIENT.strip()
    if not raw:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


def youtube_extractor_args() -> dict[str, Any] | None:
    clients = youtube_player_clients()
    if not clients:
        return None
    return {"youtube": {"player_client": clients}}


def append_youtube_extractor_cli(cmd: list[str]) -> None:
    clients = youtube_player_clients()
    if not clients:
        return
    inner = ";".join(f"player_client={c}" for c in clients)
    cmd.extend(["--extractor-args", f"youtube:{inner}"])
