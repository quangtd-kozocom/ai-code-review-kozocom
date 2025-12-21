import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """A file changed in the PR."""

    filename: str
    status: Literal["added", "modified", "removed", "renamed"]
    additions: int
    deletions: int
    patch: str  # Git diff
    language: str | None = None


class ReviewComment(BaseModel):
    """A review comment from an agent."""

    file: str
    line: int
    severity: Literal["critical", "warning", "info", "suggestion"]
    category: str  # security, style, logic
    message: str
    suggestion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    agent: str  # Which agent created this


class PRContext(BaseModel):
    """Context about the PR being reviewed."""

    owner: str
    repo: str
    pr_number: int
    title: str
    author: str
    installation_id: int


class GraphState(TypedDict):
    """State passed through the LangGraph workflow."""

    # Input
    context: PRContext

    # Extracted
    files: list[FileChange]

    # Agent outputs (merged via operator.add)
    comments: Annotated[list[ReviewComment], operator.add]

    # Aggregated
    final_comments: list[ReviewComment]
    summary: str

    # Output
    review_id: int | None
    errors: list[str]
