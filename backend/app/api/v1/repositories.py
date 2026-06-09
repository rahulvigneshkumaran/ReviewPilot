from typing import List
from datetime import datetime
import uuid
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.exceptions import RepositoryNotFoundException
from app.core.security import decrypt_token
from app.db.models import Repository, User
from app.db.schemas import RepositoryCreate, RepositoryOut, RepositoryUpdate

router = APIRouter()

class ConnectByNameRequest(BaseModel):
    full_name: str


@router.get("/", response_model=List[RepositoryOut])
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all active repositories connected by the authenticated user."""
    query = select(Repository).where(
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None)
    ).order_by(Repository.full_name)
    
    result = await db.execute(query)
    repos = result.scalars().all()
    return repos

@router.post("/connect-by-name", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
async def connect_repository_by_name(
    payload: ConnectByNameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Connect a GitHub repository by typing owner/repo. Fetches real metadata from GitHub API."""
    full_name = payload.full_name.strip()

    # Auto-parse full GitHub URLs like https://github.com/owner/repo
    if full_name.startswith("http://") or full_name.startswith("https://"):
        from urllib.parse import urlparse
        parsed = urlparse(full_name)
        # path is like /owner/repo or /owner/repo/ — strip leading slash and trailing slashes
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2:
            full_name = f"{path_parts[0]}/{path_parts[1]}"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract owner/repo from the URL. Use format: owner/repo or https://github.com/owner/repo"
            )

    if not full_name or "/" not in full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository must be in 'owner/repo' format (e.g. Kalpanagobal/ai-code-reviewer)"
        )

    # Fetch real repo metadata from GitHub using the user's encrypted token
    token = decrypt_token(current_user.encrypted_access_token)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{full_name}",
            headers={"Authorization": f"token {token}", "Accept": "application/json"},
            timeout=10.0
        )
        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository '{full_name}' not found on GitHub or you don't have access."
            )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch repository info from GitHub API."
            )
        repo_data = resp.json()

    github_repo_id = str(repo_data["id"])

    # Check if already connected (restore if soft-deleted)
    existing_result = await db.execute(select(Repository).where(Repository.github_repo_id == github_repo_id))
    existing = existing_result.scalar_one_or_none()

    if existing and existing.deleted_at is None:
        # Already connected — return it (idempotent)
        return existing
    elif existing:
        # Restore soft-deleted entry
        existing.deleted_at = None
        existing.owner_id = current_user.id
        existing.full_name = repo_data["full_name"]
        existing.description = repo_data.get("description") or ""
        existing.default_branch = repo_data.get("default_branch", "main")
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    # Create new repository record with real GitHub data
    new_repo = Repository(
        owner_id=current_user.id,
        github_repo_id=github_repo_id,
        full_name=repo_data["full_name"],
        description=repo_data.get("description") or "",
        default_branch=repo_data.get("default_branch", "main"),
        is_active=True,
    )
    db.add(new_repo)
    await db.commit()
    await db.refresh(new_repo)
    return new_repo

@router.post("/", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
async def connect_repository(
    repo_data: RepositoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Connect a new GitHub repository, checking if it is already registered."""
    # Check if repo was previously registered (soft-deleted) or exists active
    query = select(Repository).where(Repository.github_repo_id == repo_data.github_repo_id)
    result = await db.execute(query)
    existing_repo = result.scalar_one_or_none()
    
    if existing_repo:
        if existing_repo.deleted_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository already connected."
            )
        # Restore soft-deleted repo
        existing_repo.deleted_at = None
        existing_repo.owner_id = current_user.id
        existing_repo.full_name = repo_data.full_name
        existing_repo.description = repo_data.description
        existing_repo.default_branch = repo_data.default_branch
        existing_repo.is_active = repo_data.is_active
        existing_repo.webhook_secret = repo_data.webhook_secret
        await db.commit()
        await db.refresh(existing_repo)
        return existing_repo

    # Create new repository record
    new_repo = Repository(
        owner_id=current_user.id,
        github_repo_id=repo_data.github_repo_id,
        full_name=repo_data.full_name,
        description=repo_data.description,
        default_branch=repo_data.default_branch,
        is_active=repo_data.is_active,
        webhook_secret=repo_data.webhook_secret,
    )
    db.add(new_repo)
    await db.commit()
    await db.refresh(new_repo)
    return new_repo

@router.get("/{repo_id}", response_model=RepositoryOut)
async def get_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetch details of a single connected repository."""
    query = select(Repository).where(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None)
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if not repo:
        raise RepositoryNotFoundException()
    return repo

@router.patch("/{repo_id}", response_model=RepositoryOut)
async def update_repository(
    repo_id: uuid.UUID,
    repo_update: RepositoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update configurations of a connected repository (e.g. branch, active flag)."""
    query = select(Repository).where(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None)
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if not repo:
        raise RepositoryNotFoundException()
        
    update_data = repo_update.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(repo, key, val)
        
    await db.commit()
    await db.refresh(repo)
    return repo

@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a repository connection (marks deleted_at)."""
    query = select(Repository).where(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None)
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if not repo:
        raise RepositoryNotFoundException()
        
    repo.deleted_at = datetime.utcnow()
    repo.is_active = False
    await db.commit()
    return None


@router.get("/{repo_id}/branches")
async def list_repo_branches(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch all branches for a connected repository directly from GitHub API."""
    query = select(Repository).where(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None),
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if not repo:
        raise RepositoryNotFoundException()

    token = decrypt_token(current_user.encrypted_access_token)

    # Mock mode — return empty list so UI shows the empty-state gracefully
    if token.startswith("gho_mock") or token == "mock_token":
        return []

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo.full_name}/branches",
            headers={"Authorization": f"token {token}", "Accept": "application/json"},
            params={"per_page": 100},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"GitHub API error fetching branches: {resp.text}",
            )
        branches = resp.json()

    return [
        {
            "name": b["name"],
            "sha": b["commit"]["sha"],
            "protected": b.get("protected", False),
            "is_default": b["name"] == repo.default_branch,
        }
        for b in branches
    ]


@router.post("/{repo_id}/pull-requests/{pr_number}/trigger-review", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pr_review(
    repo_id: uuid.UUID,
    pr_number: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert a PullRequest record from GitHub data and trigger an AI review scan."""
    from app.db.models import PullRequest, Review, ReviewStatus, PRState
    from app.api.v1.reviews import run_stub_review_task

    # 1. Verify repo ownership
    query = select(Repository).where(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None),
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if not repo:
        raise RepositoryNotFoundException()

    token = decrypt_token(current_user.encrypted_access_token)

    # 2. Fetch PR metadata from GitHub
    if token.startswith("gho_mock") or token == "mock_token":
        # Mock mode — create a stub PR record
        pr_title = f"Pull Request #{pr_number}"
        source_branch = "feature-branch"
        target_branch = repo.default_branch
        creator = current_user.github_username
    else:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo.full_name}/pulls/{pr_number}",
                headers={"Authorization": f"token {token}", "Accept": "application/json"},
                timeout=10.0,
            )
            if resp.status_code == 404:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"PR #{pr_number} not found on GitHub.")
            if resp.status_code != 200:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API error fetching PR details.")
            pr_data = resp.json()
            pr_title = pr_data.get("title", f"Pull Request #{pr_number}")
            source_branch = pr_data["head"]["ref"]
            target_branch = pr_data["base"]["ref"]
            creator = pr_data["user"]["login"]

    # 3. Upsert PullRequest record in DB
    pr_query = select(PullRequest).where(
        PullRequest.repository_id == repo.id,
        PullRequest.pr_number == pr_number,
    )
    pr_result = await db.execute(pr_query)
    pr = pr_result.scalar_one_or_none()

    if pr:
        pr.title = pr_title
        pr.source_branch = source_branch
        pr.target_branch = target_branch
        pr.state = PRState.OPEN
        pr.deleted_at = None
    else:
        pr = PullRequest(
            repository_id=repo.id,
            pr_number=pr_number,
            state=PRState.OPEN,
            title=pr_title,
            source_branch=source_branch,
            target_branch=target_branch,
            creator_github_username=creator,
        )
        db.add(pr)

    await db.commit()
    await db.refresh(pr)

    # 4. Create Review record and fire background AI task
    new_review = Review(pull_request_id=pr.id, status=ReviewStatus.PENDING)
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)

    import app.core.database
    background_tasks.add_task(run_stub_review_task, new_review.id, app.core.database.async_session_factory)

    return {
        "status": "accepted",
        "review_id": str(new_review.id),
        "message": f"AI review triggered for PR #{pr_number}. Check the Reviews tab for results.",
    }


@router.get("/{repo_id}/pull-requests")
async def list_repo_pull_requests(
    repo_id: uuid.UUID,
    state: str = "open",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch pull requests for a connected repository directly from GitHub API."""
    query = select(Repository).where(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None),
    )
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if not repo:
        raise RepositoryNotFoundException()

    token = decrypt_token(current_user.encrypted_access_token)

    # Mock mode — return empty list so UI shows the empty-state gracefully
    if token.startswith("gho_mock") or token == "mock_token":
        return []

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo.full_name}/pulls",
            headers={"Authorization": f"token {token}", "Accept": "application/json"},
            params={"state": state, "per_page": 50, "sort": "updated", "direction": "desc"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"GitHub API error fetching pull requests: {resp.text}",
            )
        prs = resp.json()

    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "head_branch": pr["head"]["ref"],
            "base_branch": pr["base"]["ref"],
            "author": pr["user"]["login"],
            "author_avatar": pr["user"]["avatar_url"],
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "url": pr["html_url"],
            "draft": pr.get("draft", False),
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "changed_files": pr.get("changed_files"),
        }
        for pr in prs
    ]
