import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import SeverityLevel, IssueCategory, PRState, ReviewStatus, CommentStatus

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    github_username: str
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    github_id: str
    encrypted_access_token: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    encrypted_access_token: Optional[str] = None

class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    github_id: str
    created_at: datetime
    updated_at: datetime

# --- Repository Schemas ---
class RepositoryBase(BaseModel):
    full_name: str
    description: Optional[str] = None
    default_branch: str = "main"
    is_active: bool = True

class RepositoryCreate(RepositoryBase):
    github_repo_id: str
    webhook_secret: Optional[str] = None

class RepositoryUpdate(BaseModel):
    description: Optional[str] = None
    default_branch: Optional[str] = None
    is_active: Optional[bool] = None
    webhook_secret: Optional[str] = None

class RepositoryOut(RepositoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    github_repo_id: str
    created_at: datetime
    updated_at: datetime

# --- Pull Request Schemas ---
class PullRequestBase(BaseModel):
    pr_number: int
    state: PRState
    title: str
    source_branch: str
    target_branch: str
    creator_github_username: str

class PullRequestCreate(PullRequestBase):
    repository_id: uuid.UUID

class PullRequestOut(PullRequestBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    repository_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

# --- Review Issue Schemas ---
class ReviewIssueBase(BaseModel):
    file_path: str
    line_number: int
    issue_type: IssueCategory
    severity: SeverityLevel
    message: str
    context_diff: Optional[str] = None
    suggestion: Optional[str] = None

class ReviewIssueOut(ReviewIssueBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    review_id: uuid.UUID
    created_at: datetime

# --- Review Comment Schemas ---
class ReviewCommentBase(BaseModel):
    file_path: str
    line_number: int
    comment_body: str

class ReviewCommentCreate(ReviewCommentBase):
    review_id: uuid.UUID
    issue_id: Optional[uuid.UUID] = None

class ReviewCommentOut(ReviewCommentBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    review_id: uuid.UUID
    issue_id: Optional[uuid.UUID] = None
    github_comment_id: Optional[str] = None
    status: CommentStatus
    created_at: datetime

# --- Review Summary Schemas ---
class ReviewSummaryBase(BaseModel):
    markdown_summary: str
    total_bugs: int
    total_security_flaws: int
    total_perf_issues: int

class ReviewSummaryOut(ReviewSummaryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    review_id: uuid.UUID
    created_at: datetime

# --- Review Schemas ---
class ReviewBase(BaseModel):
    status: ReviewStatus
    risk_score: Optional[int] = None
    severity: Optional[SeverityLevel] = None
    summary: Optional[str] = None

class ReviewCreate(BaseModel):
    pull_request_id: uuid.UUID

class ReviewOut(ReviewBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pull_request_id: uuid.UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    pr_number: int = 0
    pr_title: str = ""
    repo_name: str = ""
    issues: List[ReviewIssueOut] = []

# --- Aggregated Review Details ---
class ReviewDetailOut(ReviewOut):
    model_config = ConfigDict(from_attributes=True)
    issues: List[ReviewIssueOut] = []
    comments: List[ReviewCommentOut] = []
    summary_report: Optional[ReviewSummaryOut] = None

# --- Dashboard & Analytics Schemas ---
class DashboardMetrics(BaseModel):
    prs_reviewed: int
    issues_detected: int
    security_findings: int
    average_risk_score: float
    generated_test_cases: int
    fix_acceptance_rate: float
    repositories_connected: int
