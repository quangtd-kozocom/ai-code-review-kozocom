"""Pydantic models for type-safe GitHub API responses."""

from pydantic import BaseModel


class ReviewComment(BaseModel):
    """GitHub review comment structure."""

    id: int
    path: str
    line: int | None = None
    original_line: int | None = None
    body: str = ""

    @property
    def effective_line(self) -> int:
        """Get the effective line number."""
        return self.line or self.original_line or 0


class FixResult(BaseModel):
    """LLM fix generation result."""

    fixed_code: str
    explanation: str = ""


class FileChange(BaseModel):
    """PR file change."""

    filename: str
    patch: str = ""
    status: str = ""
