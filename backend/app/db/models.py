import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# --- Enum definitions mapped to PostgreSQL ENUMs ---

class SeverityLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IssueCategory(str, enum.Enum):
    BUG = "BUG"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    CODE_QUALITY = "CODE_QUALITY"
    TEST = "TEST"

class PRState(str, enum.Enum):
    OPEN = "OPEN"
    MERGED = "MERGED"
    CLOSED = "CLOSED"

class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CommentStatus(str, enum.Enum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    FAILED = "FAILED"

# --- Models ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    github_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    github_username: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repositories: Mapped[List["Repository"]] = relationship("Repository", back_populates="owner", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("idx_users_github_username", "github_username", postgresql_where=deleted_at.is_(None)),
    )

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    github_repo_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="repositories")
    pull_requests: Mapped[List["PullRequest"]] = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_repositories_owner", "owner_id", postgresql_where=deleted_at.is_(None)),
        Index("idx_repositories_github_id", "github_repo_id", postgresql_where=deleted_at.is_(None)),
    )

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[PRState] = mapped_column(default=PRState.OPEN, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_branch: Mapped[str] = mapped_column(String(100), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(100), nullable=False)
    creator_github_username: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="pull_request", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("repository_id", "pr_number", name="unique_repo_pr"),
        Index("idx_pull_requests_repo_id", "repository_id"),
        Index("idx_pull_requests_state", "state"),
    )

class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(default=ReviewStatus.PENDING, nullable=False)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[Optional[SeverityLevel]] = mapped_column(nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="reviews")
    issues: Mapped[List["ReviewIssue"]] = relationship("ReviewIssue", back_populates="review", cascade="all, delete-orphan")
    comments: Mapped[List["ReviewComment"]] = relationship("ReviewComment", back_populates="review", cascade="all, delete-orphan")
    summary_report: Mapped[Optional["ReviewSummary"]] = relationship("ReviewSummary", uselist=False, back_populates="review", cascade="all, delete-orphan")

    @property
    def pr_number(self) -> int:
        return self.pull_request.pr_number if self.pull_request else 0

    @property
    def pr_title(self) -> str:
        return self.pull_request.title if self.pull_request else ""

    @property
    def repo_name(self) -> str:
        return self.pull_request.repository.full_name if self.pull_request and self.pull_request.repository else ""

    __table_args__ = (
        Index("idx_reviews_pr_id", "pull_request_id"),
        Index("idx_reviews_status", "status"),
        Index("idx_reviews_created_at", "created_at"),
    )

class ReviewIssue(Base):
    __tablename__ = "review_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_type: Mapped[IssueCategory] = mapped_column(nullable=False)
    severity: Mapped[SeverityLevel] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="issues")
    comments: Mapped[List["ReviewComment"]] = relationship("ReviewComment", back_populates="issue")

    __table_args__ = (
        Index("idx_review_issues_review_id", "review_id"),
        Index("idx_review_issues_type", "issue_type"),
    )

class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    issue_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("review_issues.id", ondelete="SET NULL"), nullable=True)
    github_comment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    comment_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CommentStatus] = mapped_column(default=CommentStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="comments")
    issue: Mapped[Optional["ReviewIssue"]] = relationship("ReviewIssue", back_populates="comments")

    __table_args__ = (
        Index("idx_review_comments_review", "review_id"),
        Index("idx_review_comments_status", "status"),
    )

class ReviewSummary(Base):
    __tablename__ = "review_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), unique=True, nullable=False)
    markdown_summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_bugs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_security_flaws: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_perf_issues: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="summary_report")

class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_category: Mapped[str] = mapped_column(String(100), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_rag_documents_category", "rule_category"),
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # Using String instead of INET for cross-compatibility in SQLite tests
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
