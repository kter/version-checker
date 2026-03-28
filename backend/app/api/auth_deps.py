import jwt
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from typing import Dict, Any

from app.infrastructure.config import settings
from app.infrastructure.database import get_db_session
from app.adapters.database_repo import UserRepository
from app.domain.entities import User

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

        # We also stored the GitHub token to make API requests later
        github_access_token = payload.get("ght")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        repo = UserRepository(session)
        # Note: UserRepository uses find_by_github_id, but our ID is uuid.
        # We need to adapt it. We will fetch by uuid if needed, or by github_id.
        # Alternatively, let's just use the repo's find_by_github_id if we store github_id in sub.
        github_id = payload.get("gh_id")
        user = await repo.find_by_github_id(int(github_id))

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        # Attach token to the user object dynamically for downstream API calls
        user.github_access_token = github_access_token
        return user

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


async def verify_org_access(
    org_id: str, user: User = Depends(get_current_user)
) -> User:
    """
    Verify if the authenticated user has access to the specified organization.
    Uses the user's GitHub access token to query /user/orgs and check if org_id is present.
    In a high-scale app, we might cache this in DynamoDB or the DB.
    """
    if not hasattr(user, "github_access_token") or not user.github_access_token:
        raise HTTPException(status_code=401, detail="GitHub access token missing")

    async with httpx.AsyncClient() as client:
        orgs_res = await client.get(
            "https://api.github.com/user/orgs",
            headers={
                "Authorization": f"Bearer {user.github_access_token}",
                "Accept": "application/json",
            },
        )
        if orgs_res.status_code != 200:
            raise HTTPException(
                status_code=401, detail="Failed to fetch user orgs from GitHub"
            )

        orgs = orgs_res.json()
        org_ids = [str(org["id"]) for org in orgs]
        org_logins = [org["login"] for org in orgs]

        # We check both ID and login just in case the client passes the login string
        if org_id not in org_ids and org_id not in org_logins:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have access to this organization",
            )

        return user
