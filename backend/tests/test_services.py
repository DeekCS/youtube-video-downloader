"""Tests for the yt-dlp service layer."""
from unittest.mock import MagicMock, patch

import pytest

from app.models.video import Format, VideoInfo
from app.services.errors import InvalidUrlError, VideoNotFoundError, YtdlpFailedError
from app.services.yt_dlp_service import YtDlpService


class TestNormalizeUrl:
    """Tests for URL normalization and validation."""

    def test_normalize_url_basic(self) -> None:
        """Test basic URL normalization."""
        url = "  https://www.youtube.com/watch?v=test  "
        result = YtDlpService.normalize_url(url)
        assert result == "https://www.youtube.com/watch?v=test"

    def test_normalize_url_invalid_scheme(self) -> None:
        """Test rejection of invalid URL schemes."""
        with pytest.raises(InvalidUrlError, match="scheme not allowed"):
            YtDlpService.normalize_url("ftp://example.com/video")

    def test_normalize_url_localhost_blocked(self) -> None:
        """Test blocking of localhost URLs."""
        with pytest.raises(InvalidUrlError, match="Localhost"):
            YtDlpService.normalize_url("http://localhost:8080/video")

    def test_normalize_url_private_ip_blocked(self) -> None:
        """Test blocking of private IP addresses."""
        with pytest.raises(InvalidUrlError, match="Private network"):
            YtDlpService.normalize_url("http://192.168.1.1/video")


class TestFetchFormats:
    """Tests for fetching video formats."""

    @patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
    def test_fetch_formats_success(self, mock_ydl_class: MagicMock) -> None:
        """Test successful format fetching."""
        # Mock yt-dlp response
        mock_info = {
            "title": "Test Video",
            "thumbnail": "https://example.com/thumb.jpg",
            "duration": 180,
            "formats": [
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "filesize": 12345678,
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "abr": 128,
                    "vcodec": "none",
                    "acodec": "mp4a",
                    "filesize": 5000000,
                },
            ],
        }

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Execute
        result = YtDlpService.fetch_formats("https://www.youtube.com/watch?v=test")

        # Assertions
        assert isinstance(result, VideoInfo)
        assert result.title == "Test Video"
        assert result.thumbnail_url == "https://example.com/thumb.jpg"
        assert result.duration_seconds == 180

        # Merged formats are prepended (Best Available + 720p tier = 2 merged)
        # plus 2 original formats = 4 total
        merged_fmts = [f for f in result.formats if "merged" in f.quality_label.lower() or "best available" in f.quality_label.lower()]
        assert len(merged_fmts) >= 1  # At least Best Available merged
        raw_fmts = [f for f in result.formats if f.id in ("22", "140")]
        assert len(raw_fmts) == 2

        # Check video format
        video_fmt = next(f for f in result.formats if f.id == "22")
        assert video_fmt.quality_label == "720p"
        assert video_fmt.mime_type == "video/mp4"
        assert video_fmt.filesize_bytes == 12345678
        assert not video_fmt.is_audio_only

        # Check audio format
        audio_fmt = next(f for f in result.formats if f.id == "140")
        assert audio_fmt.quality_label == "128kbps"
        assert audio_fmt.is_audio_only

    @patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
    def test_fetch_formats_video_not_found(self, mock_ydl_class: MagicMock) -> None:
        """Test handling of video not found error."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = Exception("Video unavailable")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Should raise VideoNotFoundError or YtdlpFailedError
        with pytest.raises((VideoNotFoundError, YtdlpFailedError)):
            YtDlpService.fetch_formats("https://www.youtube.com/watch?v=invalid")
