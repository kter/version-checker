from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.entities import User
from app.usecases.github_auth import (
    GITHUB_REAUTH_REQUIRED_DETAIL,
    GitHubAuthorizationExpiredError,
    GitHubTokenService,
)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TestGitHubTokenService:
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_returns_refresh_metadata(self):
        service = GitHubTokenService()
        mock_client = AsyncMock()
        mock_client.post.return_value = MagicMock(
            json=MagicMock(
                return_value={
                    "access_token": "ghu_test",
                    "refresh_token": "ghr_test",
                    "expires_in": 3600,
                    "refresh_token_expires_in": 7200,
                }
            )
        )

        with patch("app.usecases.github_auth.settings") as mock_settings, patch(
            "app.usecases.github_auth.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_settings.github_client_id = "client-id"
            mock_settings.github_client_secret = "client-secret"
            mock_settings.github_redirect_uri = "http://localhost:3000/auth/callback"
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            payload = await service.exchange_code_for_tokens("test-code")

        assert payload.access_token == "ghu_test"
        assert payload.refresh_token == "ghr_test"
        assert payload.access_token_expires_at is not None
        assert payload.refresh_token_expires_at is not None

    @pytest.mark.asyncio
    async def test_ensure_user_access_token_refreshes_expired_token(self):
        service = GitHubTokenService()
        user_repository = AsyncMock()
        expired_user = User(
            id="u1",
            github_id=1,
            username="octocat",
            github_access_token="ghu_old",
            github_refresh_token="ghr_old",
            github_access_token_expires_at=_utcnow_naive() - timedelta(minutes=1),
            github_refresh_token_expires_at=_utcnow_naive() + timedelta(days=1),
        )
        saved_user = User(
            id="u1",
            github_id=1,
            username="octocat",
            github_access_token="ghu_new",
            github_refresh_token="ghr_new",
            github_access_token_expires_at=_utcnow_naive() + timedelta(hours=1),
            github_refresh_token_expires_at=_utcnow_naive() + timedelta(days=30),
        )
        user_repository.save = AsyncMock(return_value=saved_user)
        mock_client = AsyncMock()
        mock_client.post.return_value = MagicMock(
            json=MagicMock(
                return_value={
                    "access_token": "ghu_new",
                    "refresh_token": "ghr_new",
                    "expires_in": 3600,
                    "refresh_token_expires_in": 86400,
                }
            )
        )

        with patch("app.usecases.github_auth.settings") as mock_settings, patch(
            "app.usecases.github_auth.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_settings.github_client_id = "client-id"
            mock_settings.github_client_secret = "client-secret"
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            refreshed_user = await service.ensure_user_access_token(
                user_repository,
                expired_user,
            )

        assert refreshed_user == saved_user
        user_repository.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_force_refresh_requires_refresh_token(self):
        service = GitHubTokenService()
        user_repository = AsyncMock()
        user = User(
            id="u1",
            github_id=1,
            username="octocat",
            github_access_token="ghu_only",
        )

        with pytest.raises(
            GitHubAuthorizationExpiredError,
            match=GITHUB_REAUTH_REQUIRED_DETAIL,
        ):
            await service.ensure_user_access_token(
                user_repository,
                user,
                force_refresh=True,
            )
