from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import os
import httpx

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
# The redirect URI registered in your GitHub App
REDIRECT_URI = "http://localhost:3000/auth/callback" 

@router.get("/login")
async def login():
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")
    
    # Typically state should be a random string to prevent CSRF
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(github_auth_url)

@router.get("/callback")
async def callback(code: str):
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")
        
    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI
            }
        )
        token_data = token_res.json()
        
        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data["error_description"])
            
        access_token = token_data.get("access_token")
        
        # In a real app we'd fetch the user's details, save them using the user_repository,
        # fetch their organizations, verify their RBAC rules, generate an internal JWT token,
        # and set it as an HTTP-only cookie or return it to the frontend.
        
        return {"access_token": access_token, "message": "Login successful. JWT token generation pending implementation details."}
