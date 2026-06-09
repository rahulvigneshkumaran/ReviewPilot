import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select
from app.db.models import Repository

@pytest.mark.asyncio
async def test_list_repositories_empty(client: AsyncClient, auth_headers: dict):
    """Test listing connected repos returns empty list when none are active."""
    response = await client.get("/api/v1/repositories/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_connect_repository(client: AsyncClient, auth_headers: dict, db_session):
    """Test connecting a new repository persists it to the database."""
    payload = {
        "full_name": "testdeveloper/new-project",
        "description": "Connecting this repo",
        "default_branch": "develop",
        "is_active": True,
        "github_repo_id": "123890",
        "webhook_secret": "mysecrettoken"
    }
    
    response = await client.post("/api/v1/repositories/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    
    data = response.json()
    assert data["full_name"] == "testdeveloper/new-project"
    assert data["github_repo_id"] == "123890"
    assert data["id"] is not None

    # Check database record
    query = select(Repository).where(Repository.github_repo_id == "123890")
    result = await db_session.execute(query)
    repo = result.scalar_one_or_none()
    assert repo is not None
    assert repo.default_branch == "develop"

@pytest.mark.asyncio
async def test_disconnect_repository(client: AsyncClient, auth_headers: dict, test_user, db_session):
    """Test deleting a repository marks it soft-deleted (deleted_at)."""
    # First, insert a repository record directly
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="999888",
        full_name="testdeveloper/delete-me",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    # Call delete endpoint
    response = await client.delete(f"/api/v1/repositories/{repo.id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify repository is soft-deleted (deleted_at timestamp is set and is_active is False)
    query = select(Repository).where(Repository.id == repo.id)
    result = await db_session.execute(query)
    db_repo = result.scalar_one_or_none()
    assert db_repo is not None
    assert db_repo.deleted_at is not None
    assert db_repo.is_active is False
