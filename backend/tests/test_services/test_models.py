import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Repository, PullRequest, PRState

@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test creating a user and checking schema fields."""
    user = User(
        email="user@example.com",
        github_id="12345",
        github_username="example_user",
        encrypted_access_token="encrypted_bytes",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.github_username == "example_user"
    assert user.created_at is not None
    assert user.deleted_at is None

@pytest.mark.asyncio
async def test_user_repository_relationship(db_session: AsyncSession):
    """Test user-repository model relationships and constraints."""
    user = User(
        email="owner@example.com",
        github_id="67890",
        github_username="repo_owner",
        encrypted_access_token="encrypted_bytes",
    )
    db_session.add(user)
    await db_session.commit()

    repo = Repository(
        owner_id=user.id,
        github_repo_id="112233",
        full_name="repo_owner/test-repo",
        description="A test repository connection",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    assert repo.id is not None
    assert repo.owner.github_username == "repo_owner"
    
    # Check back-population relationship
    from sqlalchemy.orm import selectinload
    stmt = select(User).where(User.id == user.id).options(selectinload(User.repositories))
    db_user = (await db_session.execute(stmt)).scalar_one()
    assert len(db_user.repositories) == 1
    assert db_user.repositories[0].full_name == "repo_owner/test-repo"

@pytest.mark.asyncio
async def test_pull_request_cascade(db_session: AsyncSession):
    """Test that deleting a repository cascade-deletes related pull requests."""
    user = User(
        email="dev@example.com",
        github_id="55555",
        github_username="devuser",
        encrypted_access_token="encrypted_bytes",
    )
    db_session.add(user)
    await db_session.commit()

    repo = Repository(
        owner_id=user.id,
        github_repo_id="55555_repo",
        full_name="devuser/project",
    )
    db_session.add(repo)
    await db_session.commit()

    pr = PullRequest(
        repository_id=repo.id,
        pr_number=1,
        state=PRState.OPEN,
        title="Fix core bugs",
        source_branch="fix/bugs",
        target_branch="main",
        creator_github_username="anotherdev",
    )
    db_session.add(pr)
    await db_session.commit()

    # Verify PR is present
    query = select(PullRequest).where(PullRequest.repository_id == repo.id)
    result = await db_session.execute(query)
    assert len(result.scalars().all()) == 1

    # Delete the repository
    await db_session.delete(repo)
    await db_session.commit()

    # Verify PR has been deleted due to CASCADE mapping
    result = await db_session.execute(query)
    assert len(result.scalars().all()) == 0
