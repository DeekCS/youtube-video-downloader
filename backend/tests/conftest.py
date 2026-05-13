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


def pytest_runtest_setup(item) -> None:
    """Clear cache before each test in TestFetchFormats."""
    if "TestFetchFormats" in item.nodeid:
        from app.services.yt_dlp_service import YtDlpService
        YtDlpService._formats_cache = None
