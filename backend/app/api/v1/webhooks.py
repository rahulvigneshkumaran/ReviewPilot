import hmac
import hashlib
import json
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.db.models import Repository, PullRequest, Review, ReviewStatus, PRState
from app.api.v1.reviews import run_stub_review_task

router = APIRouter()

async def verify_signature(
    request: Request,
    x_hub_signature_256: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> bytes:
    """Validate incoming webhook signature. Skips verification if no real secret is configured."""
    body = await request.body()

    try:
        payload = json.loads(body.decode("utf-8"))
        repo_id = str(payload.get("repository", {}).get("id"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Fetch repo-specific secret from DB
    query = select(Repository).where(
        Repository.github_repo_id == repo_id,
        Repository.deleted_at.is_(None)
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()

    secret = repo.webhook_secret if (repo and repo.webhook_secret) else settings.GITHUB_WEBHOOK_SECRET

    # If no real secret is configured (still using placeholder), skip HMAC — allow for easy local testing
    PLACEHOLDER_SECRETS = {"mock_webhook_secret", "", None}
    if secret in PLACEHOLDER_SECRETS:
        return body  # Skip signature check gracefully

    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header missing")

    # Compute and compare signature hash
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected_signature = f"sha256={mac.hexdigest()}"

    if not hmac.compare_digest(x_hub_signature_256, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook_receiver(
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    payload_bytes: bytes = Depends(verify_signature),
    db: AsyncSession = Depends(get_db)
):
    """Exposes POST endpoint to receive webhook payloads from GitHub."""
    if not x_github_event:
        raise HTTPException(status_code=400, detail="X-GitHub-Event header missing")

    payload = json.loads(payload_bytes.decode("utf-8"))

    # We only process 'pull_request' events
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"Unsupported event category: {x_github_event}"}

    action = payload.get("action")
    # Only analyze pull request events on creation/update/assignment
    if action not in ["opened", "synchronize", "reopened", "assigned"]:
        return {"status": "ignored", "reason": f"Unsupported pull request action: {action}"}

    repo_data = payload.get("repository", {})
    github_repo_id = str(repo_data.get("id"))
    
    # 1. Fetch Repository from Database
    repo_query = select(Repository).where(
        Repository.github_repo_id == github_repo_id,
        Repository.deleted_at.is_(None)
    )
    repo_result = await db.execute(repo_query)
    repo = repo_result.scalar_one_or_none()
    
    if not repo or not repo.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not registered or inactive."
        )

    # 2. Extract Pull Request metadata
    pr_data = payload.get("pull_request", {})
    pr_number = pr_data.get("number")
    title = pr_data.get("title", f"Pull Request #{pr_number}")
    source_branch = pr_data.get("head", {}).get("ref", "unknown")
    target_branch = pr_data.get("base", {}).get("ref", "main")
    creator = pr_data.get("user", {}).get("login", "unknown")
    state_str = pr_data.get("state", "open").upper()
    
    pr_state_val = PRState.OPEN
    if state_str == "CLOSED":
        pr_state_val = PRState.CLOSED
    elif state_str == "MERGED":
        # Github state is 'closed' for merged PRs, but payload merged=True
        if pr_data.get("merged"):
            pr_state_val = PRState.MERGED
        else:
            pr_state_val = PRState.CLOSED

    # 3. Create or Update PullRequest Record
    pr_query = select(PullRequest).where(
        PullRequest.repository_id == repo.id,
        PullRequest.pr_number == pr_number
    )
    pr_result = await db.execute(pr_query)
    pr = pr_result.scalar_one_or_none()

    if pr:
        pr.title = title
        pr.state = pr_state_val
        pr.source_branch = source_branch
        pr.target_branch = target_branch
        pr.deleted_at = None
    else:
        pr = PullRequest(
            repository_id=repo.id,
            pr_number=pr_number,
            state=pr_state_val,
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            creator_github_username=creator,
        )
        db.add(pr)
    
    await db.commit()
    await db.refresh(pr)

    # 4. Trigger review scan if PR is open
    if pr.state == PRState.OPEN:
        new_review = Review(
            pull_request_id=pr.id,
            status=ReviewStatus.PENDING
        )
        db.add(new_review)
        await db.commit()
        await db.refresh(new_review)

        # Offload AI review process to background
        import app.core.database
        background_tasks.add_task(run_stub_review_task, new_review.id, app.core.database.async_session_factory)
        return {
            "status": "accepted",
            "message": f"Review scan triggered for PR #{pr_number}",
            "review_id": new_review.id
        }

    return {"status": "accepted", "message": f"Pull Request metadata updated for PR #{pr_number}"}
