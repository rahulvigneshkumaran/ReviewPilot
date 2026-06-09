from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import CredentialsException, UserNotFoundException
from app.core.security import create_access_token, decode_access_token, encrypt_token
from app.db.models import User
from app.db.schemas import Token, UserOut

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to validate the JWT access token and return the current user."""
    if not token:
        raise CredentialsException(detail="Not authenticated")
    
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise CredentialsException()
    
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise CredentialsException()
    
    # Query active user
    query = select(User).where(User.id == user_uuid, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundException()
    return user

@router.get("/login")
def login_redirect(redirect_uri: Optional[str] = None):
    """Redirect user to GitHub OAuth login page."""
    scope = "read:user,user:email,repo,write:repo_hook"
    github_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope={scope}"
    )
    if redirect_uri:
        github_url += f"&redirect_uri={redirect_uri}"
    return RedirectResponse(url=github_url)

class DevLoginRequest(BaseModel):
    github_token: str

@router.post("/dev-login")
async def dev_login(
    credentials: DevLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Local development login using a GitHub Personal Access Token (PAT).
    No OAuth App required — just paste your PAT with 'repo' scope."""
    github_token = credentials.github_token.strip()
    if not github_token:
        raise HTTPException(status_code=400, detail="github_token is required")

    # Validate token against GitHub API and fetch user profile
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/json"
            },
            timeout=10.0
        )
        if user_response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token. Make sure your PAT has 'repo' scope.")
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to verify token with GitHub API.")

        github_user = user_response.json()
        github_id = str(github_user.get("id"))
        github_username = github_user.get("login", "unknown")
        avatar_url = github_user.get("avatar_url", "")
        email = github_user.get("email") or f"{github_username}@users.noreply.github.com"

    # Upsert user record
    query = select(User).where(User.github_id == github_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    encrypted_token = encrypt_token(github_token)

    if user:
        user.github_username = github_username
        user.avatar_url = avatar_url
        user.email = email
        user.encrypted_access_token = encrypted_token
        user.deleted_at = None
    else:
        user = User(
            email=email,
            github_id=github_id,
            github_username=github_username,
            avatar_url=avatar_url,
            encrypted_access_token=encrypted_token,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    jwt_token = create_access_token(subject=user.id)
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "github_username": user.github_username,
            "avatar_url": user.avatar_url
        }
    }


@router.get("/callback")
async def oauth_callback(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """Callback endpoint handling GitHub code exchange, user creation, and JWT generation."""
    # 1. Exchange OAuth code for an access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            timeout=10.0
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve access token from GitHub")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {token_data.get('error_description', 'No access token returned')}")

        # 2. Fetch User Profile Details from GitHub API
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/json"
            },
            timeout=10.0
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user profile from GitHub")
        
        github_user = user_response.json()
        github_id = str(github_user.get("id"))
        github_username = github_user.get("login")
        avatar_url = github_user.get("avatar_url")
        email = github_user.get("email")

        # 3. If email is private/null, retrieve emails list
        if not email:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/json"
                },
                timeout=10.0
            )
            if emails_response.status_code == 200:
                emails_list = emails_response.json()
                # Find primary email
                primary_emails = [e for e in emails_list if e.get("primary")]
                if primary_emails:
                    email = primary_emails[0].get("email")
                elif emails_list:
                    email = emails_list[0].get("email")
        
        if not email:
            # Fallback dummy email if github returns absolutely nothing (unlikely)
            email = f"{github_username}@users.noreply.github.com"

        # 4. Check if user exists or create them
        query = select(User).where(User.github_id == github_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        encrypted_token = encrypt_token(access_token)

        if user:
            user.github_username = github_username
            user.avatar_url = avatar_url
            user.email = email
            user.encrypted_access_token = encrypted_token
            user.deleted_at = None
        else:
            user = User(
                email=email,
                github_id=github_id,
                github_username=github_username,
                avatar_url=avatar_url,
                encrypted_access_token=encrypted_token,
            )
            db.add(user)
        
        await db.commit()
        await db.refresh(user)

    # 5. Generate JWT token for dashboard session
    jwt_token = create_access_token(subject=user.id)
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "github_username": user.github_username,
            "avatar_url": user.avatar_url
        }
    }

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Fetch the currently logged in user's profile info."""
    return current_user
