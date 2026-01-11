# src/core/models/affected_caller.py
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel


class AffectedCaller(SQLModel, table=True):
    __tablename__ = "affected_callers"

    id: int | None = Field(default=None, primary_key=True)
    breaking_change_id: int = Field(foreign_key="breaking_changes.id", ondelete="CASCADE")
    file_path: str = Field(max_length=1000)
    line_number: int | None = None
    call_text: str | None = None
    break_reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    breaking_change: "BreakingChange" = Relationship(back_populates="affected_callers")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "call_text": self.call_text,
            "break_reason": self.break_reason,
        }
