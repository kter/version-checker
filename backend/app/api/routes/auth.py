from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import uuid
import jwt

from app.api.auth_deps import SECRET_KEY, ALGORITHM

from app.infrastructure.config import settings
from app.infrastructure.database import get_db_session
from app.adapters.database_repo import OrgRepository, UserRepository
from app.domain.entities import Organization, User

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

REDIRECT_URI = "http://localhost:3000/auth/callback"


@router.get("/login")
async def login():
    if not settings.github_client_id:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")

    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=read:org,repo"
    )
    return RedirectResponse(github_auth_url)


@router.get("/callback")
async def callback(
    code: str,
    session: AsyncSession = Depends(get_db_session),
):
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
        )
        token_data = token_res.json()

        if "error" in token_data:
            raise HTTPException(
                status_code=400,
                detail=token_data.get("error_description", token_data["error"]),
            )

        access_token = token_data.get("access_token")

        # Fetch GitHub user profile
        user_res = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        github_user = user_res.json()

        # Save user to database
        user_repo = UserRepository(session)
        user = User(
            id=str(uuid.uuid4()),
            github_id=github_user["id"],
            username=github_user["login"],
            email=github_user.get("email"),
            role="admin",
        )
        saved_user = await user_repo.save(user)

        # Fetch user's organizations
        orgs_res = await client.get(
            "https://api.github.com/user/orgs",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        orgs = orgs_res.json()
        org_repo = OrgRepository(session)
        saved_orgs = await org_repo.save_all(
            [
                Organization(
                    id=org["login"],
                    github_id=org["id"],
                    name=org.get("login") or org.get("name") or org["login"],
                    login=org["login"],
                    github_access_token=access_token,
                )
                for org in orgs
            ]
        )

        # Create JWT Token
        payload = {
            "sub": saved_user.id,
            "gh_id": saved_user.github_id,
            "ght": access_token,  # Storing GitHub token in JWT to use it for later org validation
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
