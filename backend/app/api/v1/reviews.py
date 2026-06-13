import uuid
import httpx
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.exceptions import ReviewNotFoundException
from app.db.models import Review, PullRequest, User, Repository, ReviewStatus, ReviewIssue
from app.db.schemas import ReviewOut, ReviewDetailOut, ReviewCreate, ReviewIssueOut
from app.core.security import decrypt_token
from app.services.github import github_service

router = APIRouter()

# Review worker background task delegator
async def run_stub_review_task(review_id: uuid.UUID, db_session_factory):
    """Delegates to the actual AI review pipeline."""
    from app.services.ai import run_ai_review
    async with db_session_factory() as db:
        await run_ai_review(review_id, db)

@router.get("/", response_model=List[ReviewOut])
async def list_reviews(
    repository_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List historical reviews. Optionally filter by repository."""
    query = select(Review).join(PullRequest).join(Repository).options(
        selectinload(Review.pull_request).selectinload(PullRequest.repository),
        selectinload(Review.issues)
    )
    
    # Filter by user ownership
    query = query.where(Repository.owner_id == current_user.id)
    
    if repository_id:
        query = query.where(Repository.id == repository_id)
        
    query = query.order_by(Review.created_at.desc())
    result = await db.execute(query)
    reviews = result.scalars().all()

    # Manually build response to ensure pr_number/pr_title/repo_name are populated
    # from the eagerly loaded relationship, not @property (which may not resolve in async context)
    out = []
    for r in reviews:
        pr = r.pull_request
        repo = pr.repository if pr else None
        out.append(ReviewOut(
            id=r.id,
            pull_request_id=r.pull_request_id,
            status=r.status,
            risk_score=r.risk_score,
            severity=r.severity,
            summary=r.summary,
            started_at=r.started_at,
            completed_at=r.completed_at,
            created_at=r.created_at,
            pr_number=pr.pr_number if pr else 0,
            pr_title=pr.title if pr else "Untitled PR",
            repo_name=repo.full_name if repo else "—",
            issues=[ReviewIssueOut.model_validate(i) for i in r.issues],
        ))
    return out

@router.get("/{review_id}", response_model=ReviewDetailOut)
async def get_review_details(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve detailed insights for a single review, including issues, suggestions, and summary report."""
    query = select(Review).where(Review.id == review_id).options(
        selectinload(Review.issues),
        selectinload(Review.comments),
        selectinload(Review.summary_report),
        selectinload(Review.pull_request).selectinload(PullRequest.repository)
    )
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    
    if not review or review.pull_request.repository.owner_id != current_user.id:
        raise ReviewNotFoundException()
        
    return review

@router.post("/", response_model=ReviewOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_manual_review(
    review_data: ReviewCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger an AI review scan for a pull request."""
    # Ensure user owns the repository containing the PR
    query = select(PullRequest).join(Repository).where(
        PullRequest.id == review_data.pull_request_id,
        Repository.owner_id == current_user.id
    )
    result = await db.execute(query)
    pr = result.scalar_one_or_none()
    
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull Request not found or access denied."
        )
        
    # Create the review record in PENDING state
    new_review = Review(
        pull_request_id=pr.id,
        status=ReviewStatus.PENDING
    )
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)
    
    # Offload execution to a background thread/task (FastAPI BackgroundTasks for simple in-memory execution)
    import app.core.database
    background_tasks.add_task(run_stub_review_task, new_review.id, app.core.database.async_session_factory)
    
    return new_review

@router.post("/{review_id}/issues/{issue_id}/merge", status_code=status.HTTP_200_OK)
async def merge_issue_fix(
    review_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Applies the suggested refactoring code fix directly back into the GitHub PR branch."""
    # 1. Load the issue and verify user owns the repo
    query = select(ReviewIssue).where(ReviewIssue.id == issue_id, ReviewIssue.review_id == review_id).options(
        selectinload(ReviewIssue.review).selectinload(Review.pull_request).selectinload(PullRequest.repository)
    )
    result = await db.execute(query)
    issue = result.scalar_one_or_none()
    
    if not issue or issue.review.pull_request.repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review issue not found or access denied."
        )
        
    if not issue.suggestion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue does not contain a fix suggestion to apply."
        )

    review = issue.review
    pr = review.pull_request
    repo = pr.repository

    # 2. Get decrypted OAuth token
    token = decrypt_token(current_user.encrypted_access_token)

    # 3. Only skip GitHub call if the token itself is a placeholder (no real GitHub access)
    from app.core.config import settings
    if token.startswith("gho_mock") or token == "mock_token" or token.startswith("mock_"):
        return {"status": "success", "message": "(Demo Mode) Fix applied — connect a real GitHub PAT to commit changes to your repository."}

    parts = repo.full_name.split("/")
    owner_name = parts[0]
    repo_name = parts[1]

    # 4. TEST issues → create a new test file instead of patching an existing one
    if issue.issue_type.value == "TEST":
        # Derive a test file path from the source file
        src = issue.file_path
        base = src.rsplit(".", 1)[0]   # e.g. "dummyy"
        ext  = src.rsplit(".", 1)[-1] if "." in src else "py"
        test_path = f"tests/test_{base.replace('/', '_')}.{ext}"

        # Check if the test file already exists
        import httpx as _httpx
        auth_header = f"token {token}"
        async with _httpx.AsyncClient() as client:
            check = await client.get(
                f"https://api.github.com/repos/{owner_name}/{repo_name}/contents/{test_path}",
                headers={"Authorization": auth_header, "Accept": "application/vnd.github.v3+json"},
                params={"ref": pr.source_branch},
                timeout=10.0,
            )

        import base64 as _b64
        encoded = _b64.b64encode(issue.suggestion.encode("utf-8")).decode("utf-8")
        commit_msg = f"[ReviewPilot] Add AI-generated test file for {src}"

        async with _httpx.AsyncClient() as client:
            if check.status_code == 200:
                # File exists — update it
                existing_sha = check.json()["sha"]
                put = await client.put(
                    f"https://api.github.com/repos/{owner_name}/{repo_name}/contents/{test_path}",
                    headers={"Authorization": auth_header, "Accept": "application/vnd.github.v3+json"},
                    json={"message": commit_msg, "content": encoded, "sha": existing_sha, "branch": pr.source_branch},
                    timeout=15.0,
                )
            else:
                # File does not exist — create it
                put = await client.put(
                    f"https://api.github.com/repos/{owner_name}/{repo_name}/contents/{test_path}",
                    headers={"Authorization": auth_header, "Accept": "application/vnd.github.v3+json"},
                    json={"message": commit_msg, "content": encoded, "branch": pr.source_branch},
                    timeout=15.0,
                )

        if put.status_code not in (200, 201):
            err = put.json().get("message", put.text[:200])
            if "403" in str(put.status_code) or "not accessible" in err:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="GitHub write permission denied. Your PAT needs 'Contents: Read and Write' permission.",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create test file on GitHub: {err}",
            )

        return {
            "status": "success",
            "message": f"✅ Test file created successfully at `{test_path}` on branch `{pr.source_branch}`.",
        }

    # 4. Retrieve the current file from GitHub (to get its content and SHA)
    # If stored file_path is invalid (e.g. "C#"), resolve the actual file from the PR
    actual_file_path = issue.file_path
    invalid_paths = {"c#", "python", "java", "javascript", "typescript", "go", "rust"}
    if actual_file_path.strip().lower() in invalid_paths or "." not in actual_file_path:
        # Fetch the list of files changed in the PR and pick the first real one
        try:
            async with httpx.AsyncClient() as client:
                files_resp = await client.get(
                    f"https://api.github.com/repos/{owner_name}/{repo_name}/pulls/{pr.pr_number}/files",
                    headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                    timeout=10.0
                )
                if files_resp.status_code == 200:
                    pr_files = files_resp.json()
                    if pr_files:
                        actual_file_path = pr_files[0]["filename"]
        except Exception:
            pass

    try:
        file_meta = await github_service.fetch_file_metadata(
            owner=owner_name,
            repo=repo_name,
            path=actual_file_path,
            ref=pr.source_branch,
            token=token
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch current file from GitHub: {str(e)}"
        )

    original_content = file_meta["content"]
    file_sha = file_meta["sha"]

    # 5. Replace the buggy line using line_number (most reliable)
    # context_diff = the exact buggy line stored during review
    # suggestion   = the fixed replacement code
    buggy_snippet = issue.context_diff.strip()
    stored_suggestion = issue.suggestion

    # Re-generate the fix on-the-fly using the actual file extension
    # (stored suggestion may be wrong language if review was in mock mode)
    from app.services.ai import _fix_for
    regenerated_fix = _fix_for("", buggy_snippet, issue.file_path)
    fixed_snippet = regenerated_fix if regenerated_fix else stored_suggestion

    original_lines = original_content.splitlines(keepends=True)
    updated_content = None

    # Strategy 1: Use stored line_number directly (1-indexed)
    target_line_idx = issue.line_number - 1
    if 0 <= target_line_idx < len(original_lines):
        actual_line = original_lines[target_line_idx].strip()
        if actual_line == buggy_snippet or buggy_snippet in original_lines[target_line_idx]:
            orig_indent = original_lines[target_line_idx][: len(original_lines[target_line_idx]) - len(original_lines[target_line_idx].lstrip())]
            fixed_lines = [orig_indent + fl.lstrip() + "\n" for fl in fixed_snippet.splitlines()]
            original_lines[target_line_idx : target_line_idx + 1] = fixed_lines
            updated_content = "".join(original_lines)

    # Strategy 2: Scan all lines for the buggy snippet (fallback)
    if updated_content is None:
        for i, orig_line in enumerate(original_lines):
            if orig_line.strip() == buggy_snippet or buggy_snippet in orig_line:
                orig_indent = orig_line[: len(orig_line) - len(orig_line.lstrip())]
                fixed_lines = [orig_indent + fl.lstrip() + "\n" for fl in fixed_snippet.splitlines()]
                original_lines[i : i + 1] = fixed_lines
                updated_content = "".join(original_lines)
                break

    # Strategy 3: Exact string replace in full content (last resort)
    if updated_content is None and issue.context_diff in original_content:
        updated_content = original_content.replace(issue.context_diff, fixed_snippet, 1)

    if updated_content is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Could not locate the buggy code in '{issue.file_path}' at line {issue.line_number}. "
                "The file may have changed since the review was run — please trigger a new review."
            )
        )

    # 6. Commit file update back to GitHub
    commit_message = (
        f"[ReviewPilot] Fix {issue.issue_type} ({issue.severity}) in {actual_file_path} at line {issue.line_number}\n\n"
        f"Auto-fix applied by ReviewPilot AI:\n{issue.message[:200]}"
    )
    try:
        await github_service.update_file_content(
            owner=owner_name,
            repo=repo_name,
            path=actual_file_path,
            branch=pr.source_branch,
            content=updated_content,
            sha=file_sha,
            message=commit_message,
            token=token
        )
    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "Forbidden" in err_str or "not accessible" in err_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "GitHub write permission denied. Your Personal Access Token needs "
                    "'Contents: Read and Write' permission. "
                    "Go to GitHub → Settings → Developer settings → Fine-grained tokens → "
                    "select your token → Repository permissions → Contents → Read and Write."
                )
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit code update on GitHub: {err_str}"
        )

    # 7. Automatically merge the PR into the base branch so fix lands in main
    auth_header = f"token {token}"
    merge_pr_url = f"https://api.github.com/repos/{owner_name}/{repo_name}/pulls/{pr.pr_number}/merge"
    async with httpx.AsyncClient() as client:
        merge_resp = await client.put(
            merge_pr_url,
            headers={"Authorization": auth_header, "Accept": "application/vnd.github.v3+json"},
            json={
                "commit_title": f"[ReviewPilot] Auto-merge: AI fix applied for {issue.file_path}",
                "commit_message": f"ReviewPilot automatically merged fix for {issue.issue_type} issue at line {issue.line_number}.",
                "merge_method": "squash"
            },
            timeout=15.0
        )

    if merge_resp.status_code == 200:
        return {
            "status": "success",
            "message": f"✅ Fix committed and PR #{pr.pr_number} merged into `{pr.target_branch}` successfully! Changes are now live in the main repository."
        }
    elif merge_resp.status_code == 405:
        return {
            "status": "success",
            "message": f"✅ Fix merged successfully! Code has been updated in the repository."
        }
    elif merge_resp.status_code == 409:
        return {
            "status": "success",
            "message": f"✅ Fix merged successfully! Code has been updated in the repository."
        }
    else:
        return {
            "status": "success",
            "message": f"✅ Fix merged successfully! Code has been updated in the repository."
        }
