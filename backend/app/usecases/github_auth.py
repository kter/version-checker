from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

import httpx

from app.domain.entities import User
from app.domain.interfaces import IUserRepository
from app.infrastructure.config import settings

GITHUB_REAUTH_REQUIRED_DETAIL = "GitHub authorization expired. Please sign in again."
GITHUB_TOKEN_REFRESH_LEEWAY = timedelta(minutes=5)


class GitHubAuthorizationExpiredError(Exception):
    pass


@dataclass(frozen=True)
class GitHubTokenPayload:
    access_token: str
    refresh_token: Optional[str]
    access_token_expires_at: Optional[datetime]
    refresh_token_expires_at: Optional[datetime]


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _expires_at_from_seconds(seconds: Any) -> Optional[datetime]:
    if seconds in (None, ""):
        return None
    return _utcnow_naive() + timedelta(seconds=int(seconds))


class GitHubTokenService:
    async def exchange_code_for_tokens(self, code: str) -> GitHubTokenPayload:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_redirect_uri,
                },
            )
        payload = response.json()
        return self._parse_token_payload(payload)

    async def refresh_user_access_token(
        self,
        user_repository: IUserRepository,
        user: User,
    ) -> User:
        if not settings.github_client_id or not settings.github_client_secret:
            raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)
        if not user.github_refresh_token:
            raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)

        refresh_expires_at = user.github_refresh_token_expires_at
        if (
            refresh_expires_at is not None
            and refresh_expires_at <= _utcnow_naive() + GITHUB_TOKEN_REFRESH_LEEWAY
        ):
            raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": user.github_refresh_token,
                },
            )
        payload = response.json()
        token_payload = self._parse_token_payload(payload)
        user.github_access_token = token_payload.access_token
        user.github_refresh_token = (
            token_payload.refresh_token or user.github_refresh_token
        )
        user.github_access_token_expires_at = token_payload.access_token_expires_at
        user.github_refresh_token_expires_at = token_payload.refresh_token_expires_at
        return await user_repository.save(user)

    async def ensure_user_access_token(
        self,
        user_repository: IUserRepository,
        user: User,
        *,
        force_refresh: bool = False,
    ) -> User:
        if not user.github_access_token and not user.github_refresh_token:
            raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)

        if force_refresh:
            if not user.github_refresh_token:
                raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)
            return await self.refresh_user_access_token(user_repository, user)

        access_expires_at = user.github_access_token_expires_at
        if access_expires_at is None:
            if user.github_access_token:
                return user
            return await self.refresh_if_possible(user_repository, user)

        if access_expires_at > _utcnow_naive() + GITHUB_TOKEN_REFRESH_LEEWAY:
            return user

        return await self.refresh_if_possible(user_repository, user)

    async def refresh_if_possible(
        self,
        user_repository: IUserRepository,
        user: User,
    ) -> User:
        if user.github_refresh_token:
            return await self.refresh_user_access_token(user_repository, user)
        if user.github_access_token:
            return user
        raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)

    async def fetch_github_user(self, access_token: str) -> Dict[str, Any]:
        return await self._fetch_json(
            "https://api.github.com/user",
            access_token,
            accept="application/json",
        )

    async def fetch_user_orgs(self, access_token: str) -> list[dict[str, Any]]:
        payload = await self._fetch_json(
            "https://api.github.com/user/orgs",
            access_token,
            accept="application/json",
        )
        return payload if isinstance(payload, list) else []

    async def _fetch_json(
        self,
        url: str,
        access_token: str,
        *,
        accept: str = "application/vnd.github+json",
    ) -> Any:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": accept,
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if response.status_code == 401:
            raise GitHubAuthorizationExpiredError(GITHUB_REAUTH_REQUIRED_DETAIL)
        response.raise_for_status()
        return response.json()

    def _parse_token_payload(self, payload: Dict[str, Any]) -> GitHubTokenPayload:
        if "error" in payload or not payload.get("access_token"):
            raise GitHubAuthorizationExpiredError(
                payload.get("error_description", GITHUB_REAUTH_REQUIRED_DETAIL)
            )
        return GitHubTokenPayload(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            access_token_expires_at=_expires_at_from_seconds(payload.get("expires_in")),
            refresh_token_expires_at=_expires_at_from_seconds(
                payload.get("refresh_token_expires_in")
            ),
        )
