import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select
from app.db.models import Repository, PullRequest, Review, ReviewIssue, PRState, ReviewStatus, SeverityLevel, IssueCategory
from app.core.security import encrypt_token

@pytest.mark.asyncio
async def test_list_reviews_empty(client: AsyncClient, auth_headers: dict):
    """Test listing reviews returns empty list when none are registered."""
    response = await client.get("/api/v1/reviews/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_merge_issue_fix_mock(client: AsyncClient, auth_headers: dict, test_user, db_session):
    """Test that merging a code fix using mock credentials successfully triggers mock mode bypass."""
    # 1. Create Repository
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="777666",
        full_name="testdeveloper/my-app",
        is_active=True
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    # 2. Create Pull Request
    pr = PullRequest(
        repository_id=repo.id,
        pr_number=42,
        state=PRState.OPEN,
        title="Fix bug in auth middleware",
        source_branch="bugfix-auth",
        target_branch="main",
        creator_github_username="testdeveloper"
    )
    db_session.add(pr)
    await db_session.commit()
    await db_session.refresh(pr)

    # 3. Create Review
    review = Review(
        pull_request_id=pr.id,
        status=ReviewStatus.COMPLETED,
        risk_score=65,
        severity=SeverityLevel.HIGH,
        summary="Found credentials key issue"
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    # 4. Create Review Issue
    issue = ReviewIssue(
        review_id=review.id,
        file_path="app/middleware.py",
        line_number=15,
        issue_type=IssueCategory.SECURITY,
        severity=SeverityLevel.HIGH,
        message="Hardcoded secret key",
        context_diff='secret = "12345"',
        suggestion='secret = os.getenv("JWT_SECRET")'
    )
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    # 5. Make the merge request call
    url = f"/api/v1/reviews/{review.id}/issues/{issue.id}/merge"
    response = await client.post(url, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Mock Mode" in data["message"]

@pytest.mark.asyncio
async def test_merge_issue_fix_not_found(client: AsyncClient, auth_headers: dict):
    """Test merging a non-existent review issue returns 404."""
    random_review_id = uuid.uuid4()
    random_issue_id = uuid.uuid4()
    url = f"/api/v1/reviews/{random_review_id}/issues/{random_issue_id}/merge"
    response = await client.post(url, headers=auth_headers)
    assert response.status_code == 404
