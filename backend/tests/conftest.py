"""Test configuration and fixtures."""
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app.

    Yields:
        TestClient instance
    """
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=False)
def clear_formats_cache() -> None:
    """Clear YtDlpService formats cache before test runs."""
    from app.services.yt_dlp_service import YtDlpService
    YtDlpService._formats_cache = None
