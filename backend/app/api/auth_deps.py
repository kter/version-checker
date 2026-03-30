import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.infrastructure.config import settings
from app.infrastructure.database import get_db_session
from app.adapters.database_repo import UserRepository
from app.domain.entities import User
from app.usecases.github_auth import (
    GITHUB_REAUTH_REQUIRED_DETAIL,
    GitHubAuthorizationExpiredError,
    GitHubTokenService,
)

security = HTTPBearer()

SECRET_KEY = settings.github_client_secret or "local-dev-secret-key"
ALGORITHM = "HS256"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Validate JWT token and return the current User object."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        repo = UserRepository(session)
        user = await repo.find_by_id(str(user_id))
        if user is None and payload.get("gh_id") is not None:
            user = await repo.find_by_github_id(int(payload["gh_id"]))

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


async def verify_org_access(
    org_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Verify if the authenticated user has access to the specified account or organization.
    A personal GitHub account is always allowed for the logged-in user.
    In a high-scale app, we might cache this in DynamoDB or the DB.
    """
    repo = UserRepository(session)
    token_service = GitHubTokenService()
    try:
        user = await token_service.ensure_user_access_token(repo, user)
    except GitHubAuthorizationExpiredError:
        raise HTTPException(status_code=401, detail=GITHUB_REAUTH_REQUIRED_DETAIL)

    if org_id in {user.username, str(user.github_id)}:
        return user

    async with httpx.AsyncClient() as client:
        orgs = await _fetch_user_orgs(client, repo, token_service, user)
        org_ids = [str(org["id"]) for org in orgs]
        org_logins = [org["login"] for org in orgs]

        # We check both ID and login just in case the client passes the login string
        if org_id not in org_ids and org_id not in org_logins:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have access to this organization",
            )

        return user


async def _fetch_user_orgs(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    token_service: GitHubTokenService,
    user: User,
) -> list[dict]:
    response = await client.get(
        "https://api.github.com/user/orgs",
        headers={
            "Authorization": f"Bearer {user.github_access_token}",
            "Accept": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code != 401:
        raise HTTPException(
            status_code=401, detail="Failed to fetch user orgs from GitHub"
        )
    try:
        refreshed_user = await token_service.ensure_user_access_token(
            user_repository,
            user,
            force_refresh=True,
        )
    except GitHubAuthorizationExpiredError:
        raise HTTPException(status_code=401, detail=GITHUB_REAUTH_REQUIRED_DETAIL)

    retry_response = await client.get(
        "https://api.github.com/user/orgs",
        headers={
            "Authorization": f"Bearer {refreshed_user.github_access_token}",
            "Accept": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if retry_response.status_code == 200:
        user.github_access_token = refreshed_user.github_access_token
        user.github_refresh_token = refreshed_user.github_refresh_token
        user.github_access_token_expires_at = (
            refreshed_user.github_access_token_expires_at
        )
        user.github_refresh_token_expires_at = (
            refreshed_user.github_refresh_token_expires_at
        )
        return retry_response.json()
    raise HTTPException(status_code=401, detail=GITHUB_REAUTH_REQUIRED_DETAIL)
