from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import jwt
import logging
from urllib.parse import urlencode

from app.api.auth_deps import SECRET_KEY, ALGORITHM

from app.infrastructure.config import settings
from app.infrastructure.database import get_db_session
from app.adapters.database_repo import OrgRepository, UserRepository
from app.domain.entities import Organization, User
from app.usecases.github_auth import GitHubAuthorizationExpiredError, GitHubTokenService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.get("/login")
async def login():
    if not settings.github_client_id:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")

    github_auth_url = "https://github.com/login/oauth/authorize?" + urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": "read:org,repo",
        }
    )
    return RedirectResponse(github_auth_url)


@router.get("/callback")
async def callback(
    code: str,
    session: AsyncSession = Depends(get_db_session),
):
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")

    token_service = GitHubTokenService()
    try:
        token_payload = await token_service.exchange_code_for_tokens(code)
        github_user = await token_service.fetch_github_user(token_payload.access_token)
        orgs = await token_service.fetch_user_orgs(token_payload.access_token)
    except GitHubAuthorizationExpiredError as exc:
        logger.warning(
            "GitHub token exchange failed: redirect_uri=%s client_id_suffix=%s code_len=%s detail=%s",
            settings.github_redirect_uri,
            (settings.github_client_id or "")[-6:],
            len(code),
            str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc))

    # Save user to database
    user_repo = UserRepository(session)
    user = User(
        id=str(uuid.uuid4()),
        github_id=github_user["id"],
        username=github_user["login"],
        email=github_user.get("email"),
        role="admin",
        github_access_token=token_payload.access_token,
        github_refresh_token=token_payload.refresh_token,
        github_access_token_expires_at=token_payload.access_token_expires_at,
        github_refresh_token_expires_at=token_payload.refresh_token_expires_at,
    )
    saved_user = await user_repo.save(user)

    org_repo = OrgRepository(session)
    accessible_accounts = {
        saved_user.username: Organization(
            id=saved_user.username,
            github_id=saved_user.github_id,
            name=saved_user.username,
            login=saved_user.username,
            github_access_token=token_payload.access_token,
            token_owner_user_id=saved_user.id,
        )
    }
    for org in orgs:
        accessible_accounts[org["login"]] = Organization(
            id=org["login"],
            github_id=org["id"],
            name=org.get("login") or org.get("name") or org["login"],
            login=org["login"],
            github_access_token=token_payload.access_token,
            token_owner_user_id=saved_user.id,
        )

    saved_orgs = await org_repo.save_all(list(accessible_accounts.values()))

    # Create JWT Token
    payload = {
        "sub": saved_user.id,
        "gh_id": saved_user.github_id,
    }
    app_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": app_token,
        "user": {
            "id": saved_user.id,
            "username": saved_user.username,
            "github_id": saved_user.github_id,
        },
        "organizations": [
            {"id": org.github_id, "login": org.login} for org in saved_orgs
        ],
    }
