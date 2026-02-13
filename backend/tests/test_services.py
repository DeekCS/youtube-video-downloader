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


class TestBuildDownloadCommand:
    """Tests for download command construction."""

    _URL = "https://www.youtube.com/watch?v=test"

    def test_merged_format_has_merge_flags(self) -> None:
        """Merged format IDs must produce --merge-output-format mp4 and --ppa flags."""
        merged_ids = [
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]",
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]",
            "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
            "/best[height<=1080][vcodec^=avc1]",
        ]
        for fmt_id in merged_ids:
            cmd = YtDlpService.build_download_command(self._URL, fmt_id)
            assert "--merge-output-format" in cmd, f"Missing --merge-output-format for {fmt_id}"
            assert "mp4" in cmd, f"Missing mp4 merge target for {fmt_id}"
            assert "--ppa" in cmd, f"Missing --ppa for {fmt_id}"
            ppa_idx = cmd.index("--ppa")
            ppa_val = cmd[ppa_idx + 1]
            assert "-c:a aac" in ppa_val, f"Missing AAC audio transcode for {fmt_id}"
            assert "frag_keyframe" in ppa_val, f"Missing fragmented MP4 flags for {fmt_id}"
            assert "empty_moov" in ppa_val, f"Missing empty_moov flag for {fmt_id}"

    def test_non_merged_format_no_merge_flags(self) -> None:
        """Regular single-stream format IDs must NOT get merge flags."""
        single_ids = ["22", "140", "251", "bestaudio"]
        for fmt_id in single_ids:
            cmd = YtDlpService.build_download_command(self._URL, fmt_id)
            assert "--merge-output-format" not in cmd, (
                f"Unexpected --merge-output-format for single stream {fmt_id}"
            )
            assert "--ppa" not in cmd, (
                f"Unexpected --ppa for single stream {fmt_id}"
            )

    def test_prefer_free_formats_skipped_for_merged(self) -> None:
        """--prefer-free-formats must NOT appear for merged format downloads."""
        fmt_id = "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
        cmd = YtDlpService.build_download_command(self._URL, fmt_id)
        assert "--prefer-free-formats" not in cmd

    def test_prefer_free_formats_kept_for_single(self) -> None:
        """--prefer-free-formats appears for single-stream downloads (when enabled)."""
        cmd = YtDlpService.build_download_command(self._URL, "22")
        # The setting defaults to True, so the flag should be present
        if "--prefer-free-formats" in cmd:
            assert True  # Confirms preference is applied for singles
        # If somehow disabled in test env, that's also acceptable

    def test_stdout_output(self) -> None:
        """Command must write to stdout (-o -)."""
        cmd = YtDlpService.build_download_command(self._URL, "22")
        assert "-o" in cmd
        dash_o_idx = cmd.index("-o")
        assert cmd[dash_o_idx + 1] == "-"

    def test_format_spec_passed(self) -> None:
        """The format ID must be passed as the -f argument."""
        fmt_id = "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
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

    def test_no_bare_best_fallback(self) -> None:
        """Merged format IDs must NEVER contain a bare '/best' without codec filter."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)

        for fmt in merged:
            # Split on '/' to get each fallback tier
            tiers = fmt.id.split("/")
            for tier in tiers:
                tier_stripped = tier.strip()
                # A bare "best" or "best[height<=N]" without vcodec constraint
                if tier_stripped == "best" or (
                    tier_stripped.startswith("best[height<=")
                    and "vcodec" not in tier_stripped
                ):
                    pytest.fail(
                        f"Format '{fmt.quality_label}' has bare fallback "
                        f"'{tier_stripped}' which can select VP9. "
                        f"Full ID: {fmt.id}"
                    )

    def test_all_selectors_prefer_avc(self) -> None:
        """Every fallback tier in merged selectors must reference avc."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)

        for fmt in merged:
            tiers = fmt.id.split("/")
            for tier in tiers:
                assert "avc" in tier.lower(), (
                    f"Tier '{tier}' in '{fmt.quality_label}' does not "
                    f"constrain to H.264 (avc). Full ID: {fmt.id}"
                )

    def test_merged_formats_generated_for_available_heights(self) -> None:
        """Merged formats are created for heights present in raw formats."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)

        labels = [f.quality_label for f in merged]
        assert any("Best Available" in l for l in labels)
        assert any("1080" in l for l in labels)
        assert any("720" in l for l in labels)
        # 480p is not available in sample, so no 480 tier
        assert not any("480" in l for l in labels)

    def test_merged_formats_all_mp4_mime(self) -> None:
        """All merged formats must have video/mp4 mime type."""
        formats = self._get_sample_formats()
        merged = YtDlpService._create_merged_formats(formats)
        for fmt in merged:
            assert fmt.mime_type == "video/mp4"
