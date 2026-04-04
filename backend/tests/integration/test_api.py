"""Integration tests for API endpoints using TestClient.

These tests use mocked dependencies to avoid needing real AWS/DB connections.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.domain.entities import Repository, EolStatus, ScanJob, User
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
            mock_settings.github_redirect_uri = (
                "https://version-check.dev.devtools.site/auth/callback"
            )

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test", follow_redirects=False
            ) as client:
                response = await client.get("/api/v1/auth/login")

            assert response.status_code == 307
            location = response.headers["location"]
            assert "github.com/login/oauth/authorize" in location
            assert "client_id=test-client-id" in location
            assert (
                "redirect_uri=https%3A%2F%2Fversion-check.dev.devtools.site%2Fauth%2Fcallback"
                in location
            )

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

    @pytest.mark.asyncio
    async def test_callback_includes_personal_account_in_organizations(
        self, app_with_mocks
    ):
        with patch("app.api.routes.auth.settings") as mock_settings, patch(
            "app.api.routes.auth.UserRepository"
        ) as mock_user_repo_cls, patch(
            "app.api.routes.auth.OrgRepository"
        ) as mock_org_repo_cls, patch(
            "app.api.routes.auth.GitHubTokenService"
        ) as mock_token_service_cls:
            mock_settings.github_client_id = "test-client-id"
            mock_settings.github_client_secret = "test-secret"
            mock_settings.github_redirect_uri = (
                "https://version-check.dev.devtools.site/auth/callback"
            )

            mock_token_service = MagicMock()
            mock_token_service.exchange_code_for_tokens = AsyncMock(
                return_value=type(
                    "TokenPayload",
                    (),
                    {
                        "access_token": "gho_test",
                        "refresh_token": "ghr_test",
                        "access_token_expires_at": None,
                        "refresh_token_expires_at": None,
                    },
                )()
            )
            mock_token_service.fetch_github_user = AsyncMock(
                return_value={
                    "id": 123,
                    "login": "octocat",
                    "email": "octocat@example.com",
                }
            )
            mock_token_service.fetch_user_orgs = AsyncMock(
                return_value=[{"id": 456, "login": "acme", "name": "Acme"}]
            )
            mock_token_service_cls.return_value = mock_token_service

            saved_user = User(
                id="u1", github_id=123, username="octocat", email="octocat@example.com"
            )
            mock_user_repo = MagicMock()
            mock_user_repo.save = AsyncMock(return_value=saved_user)
            mock_user_repo_cls.return_value = mock_user_repo

            mock_org_repo = MagicMock()
            mock_org_repo.save_all = AsyncMock()
            mock_org_repo_cls.return_value = mock_org_repo
            mock_org_repo.save_all.return_value = [
                type(
                    "SavedOrg",
                    (),
                    {"github_id": 123, "login": "octocat"},
                )(),
                type(
                    "SavedOrg",
                    (),
                    {"github_id": 456, "login": "acme"},
                )(),
            ]

            transport = ASGITransport(app=app_with_mocks)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/auth/callback?code=test-code")

        assert response.status_code == 200
        assert response.json()["organizations"] == [
            {"id": 123, "login": "octocat"},
            {"id": 456, "login": "acme"},
        ]
        saved_accounts = mock_org_repo.save_all.await_args.args[0]
        assert [account.login for account in saved_accounts] == ["octocat", "acme"]


class TestScanEndpoints:
    @pytest.mark.asyncio
    async def test_get_scan_results_empty(self, app_with_mocks, mock_db_session):
        from app.api.auth_deps import verify_org_access
        from app.api.routes.scan import get_scan_job_service

        fake_service = MagicMock()
        fake_service.get_scan_results = AsyncMock(
            return_value={
                "repository_count": 1,
                "selected_repository_count": 1,
                "repositories": [],
                "latest_job": None,
            }
        )

        async def override_service():
            return fake_service

        async def override_auth(org_id: str):
            return User(
                id="u1", github_id=1, username="alice", github_access_token="token"
            )

        app_with_mocks.dependency_overrides[get_scan_job_service] = override_service
        app_with_mocks.dependency_overrides[verify_org_access] = override_auth

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/scan/orgs/test-org")

        assert response.status_code == 200
        assert response.json() == {
            "repository_count": 1,
            "selected_repository_count": 1,
            "repositories": [],
            "latest_job": None,
        }

    @pytest.mark.asyncio
    async def test_put_selection_updates_selection(
        self, app_with_mocks, mock_db_session
    ):
        from app.api.auth_deps import verify_org_access
        from app.api.routes.scan import get_scan_job_service

        fake_service = MagicMock()
        fake_service.update_selection = AsyncMock(
            return_value={"selected_repository_count": 1}
        )

        async def override_service():
            return fake_service

        async def override_auth(org_id: str):
            return User(
                id="u1", github_id=1, username="alice", github_access_token="token"
            )

        app_with_mocks.dependency_overrides[get_scan_job_service] = override_service
        app_with_mocks.dependency_overrides[verify_org_access] = override_auth

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                "/api/v1/scan/orgs/test-org/selection",
                json={"selected_repo_ids": ["repo-1"]},
            )

        assert response.status_code == 200
        assert response.json() == {"selected_repository_count": 1}

    @pytest.mark.asyncio
    async def test_post_scan_enqueues_job(self, app_with_mocks, mock_db_session):
        from app.api.auth_deps import verify_org_access
        from app.api.routes.scan import get_scan_job_service

        fake_service = MagicMock()
        fake_service.enqueue_scan = AsyncMock(
            return_value=ScanJob(
                id="job-1",
                org_id="test-org",
                requested_by="alice",
                status="queued",
                total_repos=0,
                completed_repos=0,
                failed_repos=0,
                created_at=datetime(2026, 3, 28, 12, 0, 0),
                updated_at=datetime(2026, 3, 28, 12, 0, 0),
            )
        )

        async def override_service():
            return fake_service

        async def override_auth(org_id: str):
            return User(
                id="u1", github_id=1, username="alice", github_access_token="token"
            )

        app_with_mocks.dependency_overrides[get_scan_job_service] = override_service
        app_with_mocks.dependency_overrides[verify_org_access] = override_auth

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/scan/orgs/test-org")

        assert response.status_code == 202
        assert response.json() == {
            "job_id": "job-1",
            "org_id": "test-org",
            "status": "queued",
            "total_repos": 0,
            "completed_repos": 0,
            "failed_repos": 0,
            "started_at": None,
            "finished_at": None,
            "error_message": None,
            "created_at": "2026-03-28T12:00:00+00:00",
            "updated_at": "2026-03-28T12:00:00+00:00",
        }

    @pytest.mark.asyncio
    async def test_get_scan_job_status(self, app_with_mocks, mock_db_session):
        from app.api.auth_deps import verify_org_access
        from app.api.routes.scan import get_scan_job_service

        fake_service = MagicMock()
        fake_service.get_job = AsyncMock(
            return_value=ScanJob(
                id="job-1",
                org_id="test-org",
                requested_by="alice",
                status="running",
                total_repos=4,
                completed_repos=1,
                failed_repos=0,
                started_at=datetime(2026, 3, 28, 12, 0, 0),
                created_at=datetime(2026, 3, 28, 11, 59, 55),
                updated_at=datetime(2026, 3, 28, 12, 0, 5),
            )
        )

        async def override_service():
            return fake_service

        async def override_auth(org_id: str):
            return User(
                id="u1", github_id=1, username="alice", github_access_token="token"
            )

        app_with_mocks.dependency_overrides[get_scan_job_service] = override_service
        app_with_mocks.dependency_overrides[verify_org_access] = override_auth

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/scan/orgs/test-org/jobs/job-1")

        assert response.status_code == 200
        assert response.json() == {
            "job_id": "job-1",
            "org_id": "test-org",
            "status": "running",
            "total_repos": 4,
            "completed_repos": 1,
            "failed_repos": 0,
            "started_at": "2026-03-28T12:00:00+00:00",
            "finished_at": None,
            "error_message": None,
            "created_at": "2026-03-28T11:59:55+00:00",
            "updated_at": "2026-03-28T12:00:05+00:00",
        }


class TestUsageEndpoints:
    @pytest.mark.asyncio
    async def test_get_current_month_usage(self, app_with_mocks, mock_db_session):
        from app.api.auth_deps import get_current_user

        mock_result = MagicMock()
        mock_result.scalar.return_value = 3456
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def override_current_user():
            return User(
                id="user-1",
                github_id=1,
                username="alice",
                github_access_token="token",
            )

        app_with_mocks.dependency_overrides[get_current_user] = override_current_user

        transport = ASGITransport(app=app_with_mocks)
        with patch(
            "app.api.routes.usage._current_month_window",
            return_value=(
                datetime(2026, 3, 1, 0, 0, 0),
                datetime(2026, 4, 1, 0, 0, 0),
            ),
        ):
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/usage/current-month")

        assert response.status_code == 200
        assert response.json() == {
            "year_month": "2026-03",
            "total_tokens": 3456,
            "period_start": "2026-03-01T00:00:00",
            "period_end": "2026-04-01T00:00:00",
        }
