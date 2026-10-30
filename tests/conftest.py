import pytest
from unittest.mock import AsyncMock, MagicMock
import aiohttp

class MockResponse:
    """Mock an aiohttp ClientResponse object with async context manager support."""
    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json_data = json_data if json_data is not None else {}
        self._text_data = text_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=self.status,
                message=f"HTTP {self.status}"
            )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.fixture
def mock_response():
    """Factory fixture for creating MockResponse instances."""
    def _create(status=200, json_data=None, text_data=""):
        return MockResponse(status=status, json_data=json_data, text_data=text_data)
    return _create
