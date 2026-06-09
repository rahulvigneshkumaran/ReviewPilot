from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.db.models import Review, ReviewIssue, Repository, PullRequest, User, IssueCategory
from app.db.schemas import DashboardMetrics

router = APIRouter()

@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve summarized statistics for user's dashboard view."""
    
    # 1. Total connected active repositories
    repos_query = select(func.count(Repository.id)).where(
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None)
    )
    repos_count = (await db.execute(repos_query)).scalar() or 0

    # 2. Total reviews performed on owned repositories
    reviews_query = select(func.count(Review.id)).join(PullRequest).join(Repository).where(
        Repository.owner_id == current_user.id
    )
    reviews_count = (await db.execute(reviews_query)).scalar() or 0

    # 3. Total issues detected
    issues_query = select(func.count(ReviewIssue.id)).join(Review).join(PullRequest).join(Repository).where(
        Repository.owner_id == current_user.id
    )
    issues_count = (await db.execute(issues_query)).scalar() or 0

    # 4. Total security findings
    security_query = select(func.count(ReviewIssue.id)).join(Review).join(PullRequest).join(Repository).where(
        Repository.owner_id == current_user.id,
        ReviewIssue.issue_type == IssueCategory.SECURITY
    )
    security_count = (await db.execute(security_query)).scalar() or 0

    # 5. Average risk score
    avg_risk_query = select(func.avg(Review.risk_score)).join(PullRequest).join(Repository).where(
        Repository.owner_id == current_user.id
    )
    avg_risk = (await db.execute(avg_risk_query)).scalar() or 0.0

    # 6. Test cases generated (simulated counts from issue type: TEST)
    test_query = select(func.count(ReviewIssue.id)).join(Review).join(PullRequest).join(Repository).where(
        Repository.owner_id == current_user.id,
        ReviewIssue.issue_type == IssueCategory.TEST
    )
    test_cases_count = (await db.execute(test_query)).scalar() or 0

    # 7. Mock acceptance rate for Phase 2 demo dashboard
    fix_acceptance_rate = 82.5  # Fixed mock rate for styling representation

    return DashboardMetrics(
        prs_reviewed=reviews_count,
        issues_detected=issues_count,
        security_findings=security_count,
        average_risk_score=float(avg_risk),
        generated_test_cases=test_cases_count,
        fix_acceptance_rate=fix_acceptance_rate,
        repositories_connected=repos_count
    )
