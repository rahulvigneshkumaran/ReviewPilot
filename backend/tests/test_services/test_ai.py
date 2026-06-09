import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.db.models import User, Repository, PullRequest, Review, ReviewIssue, ReviewComment, ReviewStatus, SeverityLevel, IssueCategory
from app.services.ai import should_analyze_file, parse_diff_to_changed_lines, run_ai_review

def test_should_analyze_file():
    """Verify file filters skip binaries, lock files, and minified scripts."""
    assert should_analyze_file("app/main.py") is True
    assert should_analyze_file("src/index.tsx") is True
    assert should_analyze_file("package-lock.json") is False
    assert should_analyze_file("assets/logo.png") is False
    assert should_analyze_file("build/main.js") is False
    assert should_analyze_file("static/bundle.min.js") is False

def test_parse_diff_to_changed_lines():
    """Verify parser extracts correct files and line numbers from unified diff format."""
    mock_diff = (
        "diff --git a/app/main.py b/app/main.py\n"
        "index 123456..789012 100644\n"
        "--- a/app/main.py\n"
        "+++ b/app/main.py\n"
        "@@ -5,4 +5,6 @@\n"
        " import os\n"
        " \n"
        " def execute():\n"
        "-    print('old line')\n"
        "+    print('new line 1')\n"
        "+    print('new line 2')\n"
        "     return True\n"
    )
    
    changed = parse_diff_to_changed_lines(mock_diff)
    assert "app/main.py" in changed
    # Added lines should correspond to lines 8 and 9 in the destination file
    assert changed["app/main.py"] == [8, 9]

@pytest.mark.asyncio
async def test_run_ai_review_mock_flow(db_session, test_user):
    """Verify run_ai_review runs the mock review flow and inserts findings and comments into DB."""
    # 1. Setup repository, PR, and Review in test database
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="777777",
        full_name="coder/myrepo",
        is_active=True
    )
    db_session.add(repo)
    await db_session.commit()

    pr = PullRequest(
        repository_id=repo.id,
        pr_number=101,
        title="Add secret credentials logic",
        source_branch="feat/auth",
        target_branch="main",
        creator_github_username="prcreator"
    )
    db_session.add(pr)
    await db_session.commit()

    review = Review(
        pull_request_id=pr.id,
        status=ReviewStatus.PENDING
    )
    db_session.add(review)
    await db_session.commit()

    # 2. Mock GitHub Diff Client Call
    mock_diff = (
        "diff --git a/app/security.py b/app/security.py\n"
        "--- a/app/security.py\n"
        "+++ b/app/security.py\n"
        "@@ -1,3 +1,5 @@\n"
        " def authenticate():\n"
        "+    api_key = 'super_secret_key_1234'\n"
        "+    try:\n"
        "+        do_something()\n"
        "+    except Exception:\n"
        "+        pass\n"
    )

    with patch("app.services.github.github_service.fetch_pr_diff", new_callable=AsyncMock) as mock_diff_fetch:
        mock_diff_fetch.return_value = mock_diff
        
        # Run AI review scan (utilizes mock fallback since GROQ_API_KEY starts with 'mock_')
        await run_ai_review(review.id, db_session)

    # 3. Assert database results
    # Query updated review
    await db_session.refresh(review)
    assert review.status == ReviewStatus.COMPLETED
    assert review.risk_score == 80  # Recalculated by our scoring service (Low + Security + Bug + Test + Sensitive penalty = 5+35+20+10+10 = 80)
    assert review.severity == SeverityLevel.CRITICAL
    assert "Developer Mock Mode" in review.summary

    # Query issues
    issues_query = select(ReviewIssue).where(ReviewIssue.review_id == review.id)
    issues_result = await db_session.execute(issues_query)
    issues = issues_result.scalars().all()
    
    # Check that we created findings for SECURITY, BUG, and TEST (missing tests for new function definition)
    issue_types = {issue.issue_type for issue in issues}
    assert IssueCategory.SECURITY in issue_types
    assert IssueCategory.BUG in issue_types
    assert IssueCategory.TEST in issue_types
    assert IssueCategory.CODE_QUALITY in issue_types

    # Find the TEST issue and assert on message and suggestion
    test_issue = next(issue for issue in issues if issue.issue_type == IssueCategory.TEST)
    assert "Missing test coverage" in test_issue.message
    assert "import pytest" in test_issue.suggestion

    # Query comments
    comments_query = select(ReviewComment).where(ReviewComment.review_id == review.id)
    comments_result = await db_session.execute(comments_query)
    comments = comments_result.scalars().all()
    assert len(comments) == len(issues)
    assert any("ReviewPilot Finding (TEST)" in comment.comment_body for comment in comments)


@pytest.mark.asyncio
async def test_run_ai_review_mock_flow_with_tests(db_session, test_user):
    """Verify missing tests issue is NOT triggered when a test file is modified in the PR."""
    repo = Repository(
        owner_id=test_user.id,
        github_repo_id="777778",
        full_name="coder/myrepo2",
        is_active=True
    )
    db_session.add(repo)
    await db_session.commit()

    pr = PullRequest(
        repository_id=repo.id,
        pr_number=102,
        title="Add auth logic and tests",
        source_branch="feat/auth2",
        target_branch="main",
        creator_github_username="prcreator"
    )
    db_session.add(pr)
    await db_session.commit()

    review = Review(
        pull_request_id=pr.id,
        status=ReviewStatus.PENDING
    )
    db_session.add(review)
    await db_session.commit()

    # The mock diff modifies app/auth.py and tests/test_auth.py
    mock_diff = (
        "diff --git a/app/auth.py b/app/auth.py\n"
        "--- a/app/auth.py\n"
        "+++ b/app/auth.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def authenticate():\n"
        "+    return True\n"
        "diff --git a/tests/test_auth.py b/tests/test_auth.py\n"
        "--- a/tests/test_auth.py\n"
        "+++ b/tests/test_auth.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def test_authenticate():\n"
        "+    assert authenticate() is True\n"
    )

    with patch("app.services.github.github_service.fetch_pr_diff", new_callable=AsyncMock) as mock_diff_fetch:
        mock_diff_fetch.return_value = mock_diff
        await run_ai_review(review.id, db_session)

    await db_session.refresh(review)
    assert review.status == ReviewStatus.COMPLETED

    # Query issues
    issues_query = select(ReviewIssue).where(ReviewIssue.review_id == review.id)
    issues_result = await db_session.execute(issues_query)
    issues = issues_result.scalars().all()
    
    # Assert that TEST category is NOT generated
    issue_types = {issue.issue_type for issue in issues}
    assert IssueCategory.TEST not in issue_types

