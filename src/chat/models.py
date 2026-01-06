"""Pydantic models for type-safe GitHub API responses.

Note: FixResult and FileChange are imported from canonical locations
to avoid duplication. Use these imports for consistency across the codebase.
"""

from pydantic import BaseModel

# Re-export canonical models for backward compatibility
from ..agents.models import FixResult
from ..agents.state import FileChange

__all__ = [
    "FileChange",
    "FixResult",
    "GitHubReviewComment",
]


class GitHubReviewComment(BaseModel):
    """GitHub review comment from the API.

    This is distinct from agents.state.ReviewComment which represents
    an agent-generated review comment. This model represents the raw
    GitHub API response structure.
    """

    id: int
    path: str
    line: int | None = None
    original_line: int | None = None
    body: str = ""

    @property
    def effective_line(self) -> int:
        """Get the effective line number."""
        return self.line or self.original_line or 0
