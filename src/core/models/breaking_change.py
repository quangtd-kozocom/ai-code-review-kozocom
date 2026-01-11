# src/core/models/breaking_change.py
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel


class BreakingChange(SQLModel, table=True):
    __tablename__ = "breaking_changes"

    id: int | None = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="pr_reviews.id", ondelete="CASCADE")
    file_path: str = Field(max_length=1000)
    line_number: int | None = None
    entity_type: str | None = Field(default=None, max_length=50)
    entity_name: str | None = Field(default=None, max_length=255)
    class_name: str | None = Field(default=None, max_length=255)
    change_type: str | None = Field(default=None, max_length=50)
    change_detail: str | None = None
    old_definition: str | None = None
    new_definition: str | None = None
    severity: str = Field(default="warning", max_length=20)
    affected_count: int = 0
    recommendation: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    review: "PRReview" = Relationship(back_populates="breaking_changes")
    affected_callers: list["AffectedCaller"] = Relationship(back_populates="breaking_change", cascade_delete=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "class_name": self.class_name,
            "change_type": self.change_type,
            "change_detail": self.change_detail,
            "old_definition": self.old_definition,
            "new_definition": self.new_definition,
            "severity": self.severity,
            "affected_count": self.affected_count,
            "recommendation": self.recommendation,
        }
