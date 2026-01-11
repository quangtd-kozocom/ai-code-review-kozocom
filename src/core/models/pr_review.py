# src/core/models/pr_review.py
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel


class PRReview(SQLModel, table=True):
    __tablename__ = "pr_reviews"

    id: int | None = Field(default=None, primary_key=True)
    repository_id: int = Field(foreign_key="repositories.id", ondelete="CASCADE")
    pr_number: int
    pr_title: str | None = Field(default=None, max_length=500)
    pr_author: str | None = Field(default=None, max_length=255)
    base_branch: str | None = Field(default=None, max_length=255)
    head_branch: str | None = Field(default=None, max_length=255)
    status: str = Field(default="pending", max_length=20)
    skip_reason: str | None = None
    total_files: int = 0
    total_changes: int = 0
    total_comments: int = 0
    count_critical: int = 0
    count_warning: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    repository: "Repository" = Relationship(back_populates="reviews")
    breaking_changes: list["BreakingChange"] = Relationship(back_populates="review", cascade_delete=True)
    comments: list["ReviewComment"] = Relationship(back_populates="review", cascade_delete=True)

    @property
    def pr_link(self) -> str:
        return f"https://github.com/{self.repository.full_name}/pull/{self.pr_number}" if self.repository else ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "pr_number": self.pr_number,
            "pr_title": self.pr_title,
            "pr_author": self.pr_author,
            "pr_link": self.pr_link,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
            "status": self.status,
            "skip_reason": self.skip_reason,
            "total_files": self.total_files,
            "total_changes": self.total_changes,
            "total_comments": self.total_comments,
            "count_critical": self.count_critical,
            "count_warning": self.count_warning,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
