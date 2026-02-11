"""Test configuration and fixtures."""
from typing import Generator

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
