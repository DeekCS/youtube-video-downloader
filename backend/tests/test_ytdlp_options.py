"""Tests for yt-dlp option builder (extractor_args, DASH preference)."""

from unittest.mock import patch

from app.core.config import settings
from app.services.yt_dlp_service import YtDlpService


class TestBuildYdlOptions:
    def test_dash_flag_adds_hls_to_skip(self) -> None:
        """YTDLP_USE_DASH_FORMATS merges skip=hls into youtube extractor_args."""
        with (
            patch.object(settings, "YTDLP_USE_DASH_FORMATS", True),
            patch.object(settings, "YTDLP_YOUTUBE_PLAYER_CLIENT", ""),
            patch(
                "app.services.yt_dlp_service.youtube_extractor_args",
                return_value=None,
            ),
        ):
            opts = YtDlpService._build_ydl_options()

        skip = opts["extractor_args"]["youtube"]["skip"]
        assert "hls" in skip

    def test_dash_merges_with_player_client(self) -> None:
        """skip=hls is appended without dropping youtube player_client."""
        with patch.object(settings, "YTDLP_USE_DASH_FORMATS", True):
            opts = YtDlpService._build_ydl_options()

        youtube = opts["extractor_args"]["youtube"]
        assert "player_client" in youtube
        assert "hls" in youtube["skip"]
