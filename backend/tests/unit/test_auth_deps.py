from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth_deps import verify_org_access
from app.domain.entities import User


class TestVerifyOrgAccess:
    @pytest.mark.asyncio
    async def test_allows_personal_account_without_org_lookup(self):
        user = User(
            id="u1",
            github_id=123,
            username="octocat",
            github_access_token="gho_test",
        )

        with patch("app.api.auth_deps.httpx.AsyncClient") as mock_client_cls:
            result = await verify_org_access("octocat", user)

        assert result == user
        mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_denies_unknown_organization(self):
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

        with patch("app.api.auth_deps.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await verify_org_access("other-org", user)

        assert exc_info.value.status_code == 403
