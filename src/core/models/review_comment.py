# src/core/models/review_comment.py
from datetime import datetime
from typing import Any
from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, SQLModel


class ReviewComment(SQLModel, table=True):
    __tablename__ = "review_comments"

    id: int | None = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="pr_reviews.id", ondelete="CASCADE")
    file_path: str = Field(max_length=1000)
    line_number: int | None = None
    severity: str | None = Field(default=None, max_length=20)
    message: str | None = None
    recommendation: str | None = None
    affected_files: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    github_comment_id: int | None = None
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    review: "PRReview" = Relationship(back_populates="comments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity,
            "message": self.message,
            "recommendation": self.recommendation,
            "affected_files": self.affected_files,
            "github_comment_id": self.github_comment_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }
