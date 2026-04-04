from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth_deps import verify_org_access
from app.domain.entities import Organization, User


class TestVerifyOrgAccess:
    @pytest.mark.asyncio
    async def test_allows_personal_account_without_org_lookup(self):
        user = User(
            id="u1",
            github_id=123,
            username="octocat",
            github_access_token="gho_test",
        )

        session = AsyncMock()
        user_repo = MagicMock()
        org_repo = MagicMock()
        org_repo.save_all = AsyncMock()
        token_service = MagicMock()
        token_service.ensure_user_access_token = AsyncMock(return_value=user)

        with patch("app.api.auth_deps.UserRepository", return_value=user_repo), patch(
            "app.api.auth_deps.OrgRepository", return_value=org_repo
        ), patch(
            "app.api.auth_deps.GitHubTokenService", return_value=token_service
        ), patch(
            "app.api.auth_deps.httpx.AsyncClient"
        ) as mock_client_cls:
            result = await verify_org_access("octocat", user, session)

        assert result == user
        mock_client_cls.assert_not_called()
        org_repo.find_by_login.assert_not_called()

    @pytest.mark.asyncio
    async def test_allows_saved_organization_without_github_lookup(self):
        user = User(
            id="u1",
            github_id=123,
            username="octocat",
            github_access_token="gho_test",
        )
        session = AsyncMock()
        user_repo = MagicMock()
        org_repo = MagicMock()
        org_repo.find_by_login = AsyncMock(
            return_value=Organization(
                id="acme",
                github_id=1,
                name="acme",
                login="acme",
                token_owner_user_id="u1",
            )
        )
        org_repo.save_all = AsyncMock()
        token_service = MagicMock()
        token_service.ensure_user_access_token = AsyncMock(return_value=user)

        with patch("app.api.auth_deps.UserRepository", return_value=user_repo), patch(
            "app.api.auth_deps.OrgRepository", return_value=org_repo
        ), patch(
            "app.api.auth_deps.GitHubTokenService", return_value=token_service
        ), patch(
            "app.api.auth_deps.httpx.AsyncClient"
        ) as mock_client_cls:
            result = await verify_org_access("acme", user, session)

        assert result == user
        org_repo.find_by_login.assert_awaited_once_with("acme")
        mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_syncs_organizations_from_github_when_missing_locally(self):
        user = User(
            id="u1",
            github_id=123,
            username="octocat",
            github_access_token="gho_test",
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{"id": 1, "login": "acme"}]),
        )
        session = AsyncMock()
        user_repo = MagicMock()
        org_repo = MagicMock()
        org_repo.find_by_login = AsyncMock(
            side_effect=[
                None,
                Organization(
                    id="acme",
                    github_id=1,
                    name="acme",
                    login="acme",
                    token_owner_user_id="u1",
                ),
            ]
        )
        org_repo.save_all = AsyncMock()
        token_service = MagicMock()
        token_service.ensure_user_access_token = AsyncMock(return_value=user)

        with patch("app.api.auth_deps.UserRepository", return_value=user_repo), patch(
            "app.api.auth_deps.OrgRepository", return_value=org_repo
        ), patch(
            "app.api.auth_deps.GitHubTokenService", return_value=token_service
        ), patch(
            "app.api.auth_deps.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            result = await verify_org_access("acme", user, session)

        assert result == user
        org_repo.save_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_denies_unknown_organization_after_github_sync(self):
        user = User(
            id="u1",
            github_id=123,
            username="octocat",
            github_access_token="gho_test",
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[{"id": 1, "login": "acme"}]),
        )
        session = AsyncMock()
        user_repo = MagicMock()
        org_repo = MagicMock()
        org_repo.find_by_login = AsyncMock(side_effect=[None, None])
        org_repo.find_by_github_id = AsyncMock(return_value=None)
        org_repo.save_all = AsyncMock()
        token_service = MagicMock()
        token_service.ensure_user_access_token = AsyncMock(return_value=user)

        with patch("app.api.auth_deps.UserRepository", return_value=user_repo), patch(
            "app.api.auth_deps.OrgRepository", return_value=org_repo
        ), patch(
            "app.api.auth_deps.GitHubTokenService", return_value=token_service
        ), patch(
            "app.api.auth_deps.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await verify_org_access("other-org", user, session)

        assert exc_info.value.status_code == 403
