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


@pytest.mark.usefixtures("clear_formats_cache")
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

    @patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
    def test_fetch_formats_includes_platform(self, mock_ydl_class: MagicMock) -> None:
        """Test that VideoInfo includes platform from extractor_key."""
        mock_info = {
            "title": "Test Video",
            "thumbnail": None,
            "duration": 60,
            "extractor_key": "Youtube",
            "formats": [
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "filesize": 1000,
                }
            ],
        }
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = YtDlpService.fetch_formats("https://www.youtube.com/watch?v=test")

        assert result.platform == "Youtube"

    @patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
    def test_fetch_formats_platform_none_when_missing(self, mock_ydl_class: MagicMock) -> None:
        """Test that platform is None when extractor_key is absent."""
        mock_info = {
            "title": "Test Video",
            "thumbnail": None,
            "duration": 60,
            "formats": [
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "filesize": 1000,
                }
            ],
        }
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = YtDlpService.fetch_formats("https://www.youtube.com/watch?v=test")

        assert result.platform is None

    @patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
    def test_fetch_formats_strips_playlist_suffix(self, mock_ydl_class: MagicMock) -> None:
        """Test that platform strips :playlist suffix from extractor_key."""
        mock_info = {
            "title": "Test Playlist",
            "thumbnail": None,
            "duration": 60,
            "extractor_key": "Youtube:playlist",
            "formats": [
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "filesize": 1000,
                }
            ],
        }
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = YtDlpService.fetch_formats("https://www.youtube.com/playlist?list=test")

        assert result.platform == "Youtube"

    @patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
    def test_fetch_formats_falls_back_to_extractor(self, mock_ydl_class: MagicMock) -> None:
        """Test that platform falls back to extractor when extractor_key is missing."""
        mock_info = {
            "title": "Test Video",
            "thumbnail": None,
            "duration": 60,
            "extractor": "Vimeo",
            "formats": [
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "filesize": 1000,
                }
            ],
        }
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = YtDlpService.fetch_formats("https://vimeo.com/123456")

        assert result.platform == "Vimeo"


class TestBuildDownloadCommand:
    """Tests for download command construction (single-stream only)."""

    _URL = "https://www.youtube.com/watch?v=test"

    def test_single_stream_no_merge_flags(self) -> None:
        """Single-stream format IDs must NOT get merge flags."""
        single_ids = ["22", "140", "251", "bestaudio"]
        for fmt_id in single_ids:
            cmd = YtDlpService.build_download_command(self._URL, fmt_id)
            assert "--merge-output-format" not in cmd, (
                f"Unexpected --merge-output-format for single stream {fmt_id}"
            )
            assert "--ppa" not in cmd, (
                f"Unexpected --ppa for single stream {fmt_id}"
            )

    def test_stdout_output(self) -> None:
        """Command must write to stdout (-o -)."""
        cmd = YtDlpService.build_download_command(self._URL, "22")
        assert "-o" in cmd
        dash_o_idx = cmd.index("-o")
        assert cmd[dash_o_idx + 1] == "-"

    def test_format_spec_passed(self) -> None:
        """The format ID must be passed as the -f argument."""
        fmt_id = "22"
        cmd = YtDlpService.build_download_command(self._URL, fmt_id)
        f_idx = cmd.index("-f")
        assert cmd[f_idx + 1] == fmt_id


class TestMergedFormatSelectors:
    """Tests for merged format selector construction."""

    def _get_sample_formats(self) -> list[Format]:
        return [
            Format(id="137", quality_label="1080p", mime_type="video/mp4",
                   filesize_bytes=50000000, is_audio_only=False, is_video_only=True),
            Format(id="136", quality_label="720p", mime_type="video/mp4",
                   filesize_bytes=30000000, is_audio_only=False, is_video_only=True),
            Format(id="140", quality_label="128kbps", mime_type="audio/m4a",
                   filesize_bytes=5000000, is_audio_only=True, is_video_only=False),
        ]

    def test_avc_tiers_come_before_vp9_fallback(self) -> None:
        """AVC (H.264) tiers must appear before the codec-agnostic fallback tiers."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)

        for fmt in merged:
            tiers = fmt.id.split("/")
            last_avc_index = -1
            first_fallback_index = len(tiers)
            for i, tier in enumerate(tiers):
                t = tier.strip()
                if "avc" in t.lower():
                    last_avc_index = i
                # codec-agnostic fallback tiers have no vcodec filter
                if "vcodec" not in t and "bestvideo" in t:
                    first_fallback_index = min(first_fallback_index, i)
            if last_avc_index != -1 and first_fallback_index < len(tiers):
                assert last_avc_index < first_fallback_index, (
                    f"In '{fmt.quality_label}', AVC tier at index {last_avc_index} "
                    f"comes after VP9-fallback tier at index {first_fallback_index}. "
                    f"Full ID: {fmt.id}"
                )

    def test_vp9_fallback_present_in_all_merged_selectors(self) -> None:
        """Every merged selector must include a codec-agnostic fallback for VP9-only platforms."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)

        for fmt in merged:
            tiers = fmt.id.split("/")
            has_fallback = any(
                "vcodec" not in t.strip() and "bestvideo" in t.strip()
                for t in tiers
            )
            assert has_fallback, (
                f"Format '{fmt.quality_label}' has no codec-agnostic fallback "
                f"tier — VP9-only platforms (Instagram, etc.) will fail. "
                f"Full ID: {fmt.id}"
            )

    def test_merged_formats_generated_for_available_heights(self) -> None:
        """Merged formats are created for heights present in raw formats."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)

        labels = [f.quality_label for f in merged]
        assert any("Best Available" in label for label in labels)
        assert any("1080" in label for label in labels)
        assert any("720" in label for label in labels)
        # 480p is not available in sample, so no 480 tier
        assert not any("480" in label for label in labels)

    def test_merged_formats_all_mp4_mime(self) -> None:
        """All merged formats must have video/mp4 mime type."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)
        for fmt in merged:
            assert fmt.mime_type == "video/mp4"
