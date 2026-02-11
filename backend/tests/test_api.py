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
        assert data["status"] == "healthy"
        assert "version" in data


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


class TestDownloadEndpoint:
    """Tests for video download endpoint."""

    @patch("app.api.v1.endpoints.videos.YtDlpService.download_format")
    @patch("app.api.v1.endpoints.videos.YtDlpService.fetch_formats")
    def test_download_video_post(
        self, mock_fetch: MagicMock, mock_download: MagicMock, client: TestClient
    ) -> None:
        """Test video download via POST."""
        # Mock format fetch
        mock_video_info = VideoInfo(
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
        mock_fetch.return_value = mock_video_info

        # Mock download (simplified - just check it's called)
        mock_process = MagicMock()
        mock_process.stdout = None
        mock_process.poll.return_value = 0
        mock_download.return_value = mock_process

        # Make request
        response = client.post(
            "/api/v1/videos/download",
            json={
                "url": "https://www.youtube.com/watch?v=test",
                "format_id": "22",
            },
        )

        # Check that download was initiated
        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "").lower()
        mock_download.assert_called_once()

    @patch("app.api.v1.endpoints.videos.YtDlpService.fetch_formats")
    def test_download_video_format_not_found(
        self, mock_fetch: MagicMock, client: TestClient
    ) -> None:
        """Test download with non-existent format ID."""
        mock_video_info = VideoInfo(
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
        mock_fetch.return_value = mock_video_info

        response = client.post(
            "/api/v1/videos/download",
            json={
                "url": "https://www.youtube.com/watch?v=test",
                "format_id": "999",  # Non-existent format
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "FORMAT_NOT_AVAILABLE"
