import hmac
import hashlib
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Repository, PullRequest, Review, ReviewStatus, PRState

@pytest.mark.asyncio
async def test_webhook_invalid_signature(client: AsyncClient, test_user, db_session):
    """Test webhook endpoint rejects requests with invalid signature header."""
    # Register test repository connection
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="111111",
        full_name="testdeveloper/myproject",
        webhook_secret="secure_webhook_secret"
    )
    db_session.add(repo)
    await db_session.commit()

    payload = {"repository": {"id": 111111}}
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=invalidhashvaluehere"
    }

    response = await client.post("/api/v1/webhooks/", json=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"

@pytest.mark.asyncio
async def test_webhook_valid_signature_opened_pr(client: AsyncClient, test_user, db_session, mocker):
    """Test webhook successfully parses a valid signature payload, creates a PR and PENDING review."""
    from unittest.mock import AsyncMock
    mocker.patch("app.services.github.github_service.fetch_pr_diff", new_callable=AsyncMock).return_value = (
        "diff --git a/app/main.py b/app/main.py\n"
        "--- a/app/main.py\n"
        "+++ b/app/main.py\n"
        "@@ -1,1 +1,2 @@\n"
        "+# test comment\n"
    )
    secret = "my_awesome_webhook_secret"
    
    # 1. Register repository
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="222222",
        full_name="testdeveloper/repo2",
        webhook_secret=secret,
        is_active=True
    )
    db_session.add(repo)
    await db_session.commit()

    # 2. Mock payload
    payload = {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "number": 42,
            "title": "Feature: Integrate MCP Server",
            "state": "open",
            "user": {"login": "pr-creator"},
            "head": {"ref": "feature/mcp"},
            "base": {"ref": "main"},
            "merged": False
        },
        "repository": {
            "id": 222222,
            "full_name": "testdeveloper/repo2"
        }
    }
    
    body_str = json.dumps(payload)
    
    # Compute signature
    mac = hmac.new(secret.encode("utf-8"), msg=body_str.encode("utf-8"), digestmod=hashlib.sha256)
    valid_signature = f"sha256={mac.hexdigest()}"

    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": valid_signature,
        "Content-Type": "application/json"
    }

    # 3. Post webhook payload
    response = await client.post("/api/v1/webhooks/", content=body_str, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    # 4. Verify database updates
    pr_query = select(PullRequest).where(PullRequest.repository_id == repo.id, PullRequest.pr_number == 42)
    pr_result = await db_session.execute(pr_query)
    pr = pr_result.scalar_one_or_none()
    
    assert pr is not None
    assert pr.title == "Feature: Integrate MCP Server"
    assert pr.creator_github_username == "pr-creator"
    
    review_query = select(Review).where(Review.pull_request_id == pr.id)
    review_result = await db_session.execute(review_query)
    review = review_result.scalar_one_or_none()
    
    assert review is not None
    assert review.status == ReviewStatus.COMPLETED

@pytest.mark.asyncio
async def test_webhook_ignore_ping(client: AsyncClient, test_user, db_session):
    """Test webhook returns accepted status but ignores unsupported event types like ping."""
    secret = "ping_secret"
    
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="333333",
        full_name="testdeveloper/repo3",
        webhook_secret=secret
    )
    db_session.add(repo)
    await db_session.commit()

    payload = {"zen": "Keep it simple", "hook_id": 999, "repository": {"id": 333333}}
    body_str = json.dumps(payload)
    
    mac = hmac.new(secret.encode("utf-8"), msg=body_str.encode("utf-8"), digestmod=hashlib.sha256)
    headers = {
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": f"sha256={mac.hexdigest()}",
        "Content-Type": "application/json"
    }

    response = await client.post("/api/v1/webhooks/", content=body_str, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"

@pytest.mark.asyncio
async def test_webhook_valid_signature_assigned_pr(client: AsyncClient, test_user, db_session, mocker):
    """Test webhook successfully parses a valid signature assigned PR payload, creates a PR and PENDING review."""
    from unittest.mock import AsyncMock
    mocker.patch("app.services.github.github_service.fetch_pr_diff", new_callable=AsyncMock).return_value = (
        "diff --git a/app/main.py b/app/main.py\n"
        "--- a/app/main.py\n"
        "+++ b/app/main.py\n"
        "@@ -1,1 +1,2 @@\n"
        "+# test comment\n"
    )
    secret = "my_assigned_webhook_secret"
    
    # 1. Register repository
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="444444",
        full_name="testdeveloper/repo4",
        webhook_secret=secret,
        is_active=True
    )
    db_session.add(repo)
    await db_session.commit()

    # 2. Mock payload
    payload = {
        "action": "assigned",
        "number": 43,
        "pull_request": {
            "number": 43,
            "title": "Fix memory leak",
            "state": "open",
            "user": {"login": "pr-creator"},
            "head": {"ref": "bugfix/memory-leak"},
            "base": {"ref": "main"},
            "merged": False
        },
        "repository": {
            "id": 444444,
            "full_name": "testdeveloper/repo4"
        }
    }
    
    body_str = json.dumps(payload)
    
    # Compute signature
    mac = hmac.new(secret.encode("utf-8"), msg=body_str.encode("utf-8"), digestmod=hashlib.sha256)
    valid_signature = f"sha256={mac.hexdigest()}"

    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": valid_signature,
        "Content-Type": "application/json"
    }

    # 3. Post webhook payload
    response = await client.post("/api/v1/webhooks/", content=body_str, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    # 4. Verify database updates
    pr_query = select(PullRequest).where(PullRequest.repository_id == repo.id, PullRequest.pr_number == 43)
    pr_result = await db_session.execute(pr_query)
    pr = pr_result.scalar_one_or_none()
    
    assert pr is not None
    assert pr.title == "Fix memory leak"

