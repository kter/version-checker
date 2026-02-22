"""Integration tests for API endpoints using TestClient.

These tests use mocked dependencies to avoid needing real AWS/DB connections.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.domain.entities import Repository, EolStatus
from datetime import datetime


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def app_with_mocks(mock_db_session):
    """Create FastAPI app with mocked dependencies."""
    # Patch database module before importing app
    with patch("app.infrastructure.database.get_engine"), patch(
        "app.infrastructure.database.get_session_maker"
    ), patch("app.infrastructure.init_db.init_db", new_callable=AsyncMock):
        from app.main import app
        from app.infrastructure.database import get_db_session

        async def override_get_db_session():
            yield mock_db_session

        app.dependency_overrides[get_db_session] = override_get_db_session
        yield app
        app.dependency_overrides.clear()


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check(self, app_with_mocks):
        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_login_redirects_to_github(self, app_with_mocks):
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.github_client_id = "test-client-id"
            mock_settings.github_client_secret = "test-secret"

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test", follow_redirects=False
            ) as client:
                response = await client.get("/api/v1/auth/login")

            assert response.status_code == 307
            location = response.headers["location"]
            assert "github.com/login/oauth/authorize" in location
            assert "client_id=test-client-id" in location

    @pytest.mark.asyncio
    async def test_login_fails_without_credentials(self, app_with_mocks):
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.github_client_id = None

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/auth/login")

            assert response.status_code == 500
            assert "OAuth credentials not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_callback_fails_without_credentials(self, app_with_mocks):
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.github_client_id = None
            mock_settings.github_client_secret = None

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/auth/callback?code=test-code")

            assert response.status_code == 500


class TestScanEndpoints:
    @pytest.mark.asyncio
    async def test_get_scan_results_empty(self, app_with_mocks, mock_db_session):
        # Mock the repo repository to return empty list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Mock the DynamoDB cache
        with patch("app.api.routes.scan.DynamoEolCacheRepository") as MockCache:
            MockCache.return_value = AsyncMock()
            MockCache.return_value.get_eol_status.return_value = []

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/scan/orgs/test-org")

        assert response.status_code == 200
        assert response.json() == {"statuses": []}

    @pytest.mark.asyncio
    async def test_post_scan_triggers_scan(self, app_with_mocks, mock_db_session):
        # Mock the repo repository to return empty list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch("app.api.routes.scan.DynamoEolCacheRepository") as MockCache:
            MockCache.return_value = AsyncMock()
            MockCache.return_value.get_eol_status.return_value = []

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/scan/orgs/test-org")

        assert response.status_code == 200
        assert response.json() == {"statuses": []}
