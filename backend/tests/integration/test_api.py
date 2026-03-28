"""Integration tests for API endpoints using TestClient.

These tests use mocked dependencies to avoid needing real AWS/DB connections.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.domain.entities import Repository, EolStatus, User
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
        from app.api.auth_deps import verify_org_access
        from app.api.routes.scan import get_scan_usecase

        fake_usecase = MagicMock()
        fake_usecase.get_saved_results = AsyncMock(return_value=[])
        fake_usecase.repo_repository = MagicMock()
        fake_usecase.repo_repository.find_by_org = AsyncMock(return_value=[])

        async def override_usecase():
            return fake_usecase

        async def override_auth(org_id: str):
            return User(
                id="u1", github_id=1, username="alice", github_access_token="token"
            )

        app_with_mocks.dependency_overrides[get_scan_usecase] = override_usecase
        app_with_mocks.dependency_overrides[verify_org_access] = override_auth

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/scan/orgs/test-org")

        assert response.status_code == 200
        assert response.json() == {"statuses": []}

    @pytest.mark.asyncio
    async def test_post_scan_triggers_scan(self, app_with_mocks, mock_db_session):
        from app.api.auth_deps import verify_org_access
        from app.api.routes.scan import get_scan_usecase

        status = EolStatus(
            repo_id="repo-1",
            framework_name="Nuxt",
            current_version="3.16.0",
            is_eol=False,
            last_scanned_at=datetime(2026, 3, 28, 12, 0, 0),
            source_path="apps/web/package.json",
        )
        fake_usecase = MagicMock()
        fake_usecase.execute = AsyncMock(return_value=[status])
        fake_usecase.repo_repository = MagicMock()
        fake_usecase.repo_repository.find_by_org = AsyncMock(
            return_value=[
                Repository(
                    id="repo-1",
                    github_id=1,
                    name="web",
                    full_name="test-org/web",
                    org_id="test-org",
                    owner_login="test-org",
                    default_branch="main",
                )
            ]
        )

        async def override_usecase():
            return fake_usecase

        async def override_auth(org_id: str):
            return User(
                id="u1", github_id=1, username="alice", github_access_token="token"
            )

        app_with_mocks.dependency_overrides[get_scan_usecase] = override_usecase
        app_with_mocks.dependency_overrides[verify_org_access] = override_auth

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/scan/orgs/test-org")

        assert response.status_code == 200
        assert response.json() == {
            "statuses": [
                {
                    "repo_id": "test-org/web",
                    "framework": "Nuxt",
                    "version": "3.16.0",
                    "is_eol": False,
                    "eol_date": None,
                    "last_scanned_at": "2026-03-28T12:00:00",
                    "source_path": "apps/web/package.json",
                }
            ]
        }
