"""Tests for API endpoints."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.models.video import Format, VideoInfo


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "unhealthy")
        assert "version" in data
        assert "ffmpeg_ok" in data
        assert "yt_dlp_cli_ok" in data
        assert "yt_dlp_version" in data


class TestFormatsEndpoint:
    """Tests for video formats endpoint."""

    @patch("app.api.v1.endpoints.videos.YtDlpService.fetch_formats")
    def test_fetch_formats_success(
        self, mock_fetch: MagicMock, client: TestClient
    ) -> None:
        """Test successful format fetching."""
        # Mock service response
        mock_video_info = VideoInfo(
            title="Test Video",
            thumbnail_url="https://example.com/thumb.jpg",
            duration_seconds=180,
            formats=[
                Format(
                    id="22",
                    quality_label="720p",
                    mime_type="video/mp4",
                    filesize_bytes=12345678,
                    is_audio_only=False,
                    is_video_only=False,
                )
            ],
        )
        mock_fetch.return_value = mock_video_info

        # Make request
        response = client.post(
            "/api/v1/videos/formats",
            json={"url": "https://www.youtube.com/watch?v=test"},
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Video"
        assert len(data["formats"]) == 1
        assert data["formats"][0]["id"] == "22"

    def test_fetch_formats_invalid_url(self, client: TestClient) -> None:
        """Test format fetching with invalid URL."""
        response = client.post(
            "/api/v1/videos/formats",
            json={"url": ""},
        )
        assert response.status_code == 422  # Validation error

    @patch("app.api.v1.endpoints.videos.YtDlpService.fetch_formats")
    def test_fetch_formats_service_error(
        self, mock_fetch: MagicMock, client: TestClient
    ) -> None:
        """Test format fetching when service raises an error."""
        from app.services.errors import VideoNotFoundError

        mock_fetch.side_effect = VideoNotFoundError()

        response = client.post(
            "/api/v1/videos/formats",
            json={"url": "https://www.youtube.com/watch?v=invalid"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "NOT_FOUND"
        assert "message" in data


class TestDownloadStartEndpoint:
    """Tests for progress-tracked download start endpoint."""

    @patch("app.api.v1.endpoints.videos.YtDlpService.download_single_with_progress")
    @patch("app.api.v1.endpoints.videos.YtDlpService.get_cached_formats", return_value=None)
    @patch("app.api.v1.endpoints.videos.YtDlpService.fetch_formats")
    def test_download_start_spawns_background_job(
        self,
        mock_fetch: MagicMock,
        _cached: MagicMock,
        _mock_dl: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /download/start returns a download_id (worker calls yt-dlp in a thread)."""
        mock_fetch.return_value = VideoInfo(
            title="Test Video",
            thumbnail_url=None,
            duration_seconds=180,
            formats=[
                Format(
                    id="22",
                    quality_label="720p",
                    mime_type="video/mp4",
                    filesize_bytes=12345678,
                    is_audio_only=False,
                    is_video_only=False,
                )
            ],
        )

        response = client.post(
            "/api/v1/videos/download/start",
            json={
                "url": "https://www.youtube.com/watch?v=test",
                "format_id": "22",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "download_id" in data
        assert "filename" in data

    @patch("app.api.v1.endpoints.videos.YtDlpService.get_cached_formats", return_value=None)
    @patch("app.api.v1.endpoints.videos.YtDlpService.fetch_formats")
    def test_download_start_format_not_found(
        self, mock_fetch: MagicMock, _cached: MagicMock, client: TestClient
    ) -> None:
        """Unknown format_id yields FORMAT_NOT_AVAILABLE."""
        mock_fetch.return_value = VideoInfo(
            title="Test Video",
            thumbnail_url=None,
            duration_seconds=180,
            formats=[
                Format(
                    id="22",
                    quality_label="720p",
                    mime_type="video/mp4",
                    filesize_bytes=12345678,
                    is_audio_only=False,
                    is_video_only=False,
                )
            ],
        )

        response = client.post(
            "/api/v1/videos/download/start",
            json={
                "url": "https://www.youtube.com/watch?v=test",
                "format_id": "999",
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "FORMAT_NOT_AVAILABLE"
