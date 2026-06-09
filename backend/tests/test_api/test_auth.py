import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_redirect(client: AsyncClient):
    """Test OAuth login endpoint returns 307 temporary redirect to GitHub."""
    response = await client.get("/api/v1/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert "github.com/login/oauth/authorize" in response.headers["location"]

@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """Test accessing current user details fails without JWT token."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_get_me_authorized(client: AsyncClient, auth_headers: dict, test_user):
    """Test fetching user profile succeeds with valid auth header."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["github_username"] == test_user.github_username
    assert data["id"] == str(test_user.id)
