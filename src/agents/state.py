import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from ..ast.models import ASTInfo, RelatedCode
from ..core.config import ReviewerConfig

__all__ = [
    "FileChange",
    "EnhancedFileChange",
    "ReviewComment",
    "PRContext",
    "GraphState",
]


class FileChange(BaseModel):
    """A file changed in the PR."""

    filename: str
    status: Literal["added", "modified", "removed", "renamed"]
    additions: int
    deletions: int
    patch: str  # Git diff
    language: str | None = None


class EnhancedFileChange(BaseModel):
    """A file changed in the PR with enriched context."""

    filename: str
    status: Literal["added", "modified", "removed", "renamed"]
    additions: int
    deletions: int
    patch: str  # Git diff
    language: str | None = None

    full_content: str | None = None
    ast_info: ASTInfo | None = None
    related_context: list[RelatedCode] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def format_for_prompt(self) -> str:
        """Format file change for LLM prompt."""
        lines = [f"## File: {self.filename}", "", "### Diff:", "```", self.patch, "```"]

        # Add AST info if available
        if self.ast_info and (self.ast_info.functions or self.ast_info.classes):
            lines.extend(["", "### Code Structure:"])
            if funcs := [f.name for f in self.ast_info.functions]:
                lines.append(f"- Functions: {', '.join(funcs)}")
            if classes := [c.name for c in self.ast_info.classes]:
                lines.append(f"- Classes: {', '.join(classes)}")

        # Add related context (top 3)
        if self.related_context:
            lines.extend(["", "### Related Code from Codebase:"])
            for ctx in self.related_context[:3]:
                lines.extend(
                    [
                        "",
                        f"**{ctx.relationship.upper()}**: `{ctx.file_path}` - `{ctx.name}`",
                        "```",
                        ctx.content[:500],
                        "```",
                    ]
                )

        return "\n".join(lines)


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
    base_branch: str = "main"
    is_draft: bool = False


class GraphState(TypedDict):
    """State passed through the LangGraph workflow."""

    # Input
    context: PRContext

    # Configuration - per-repository settings
    repo_config: ReviewerConfig

    # Extracted
    files: list[FileChange]

    # Agent outputs (merged via operator.add)
    comments: Annotated[list[ReviewComment], operator.add]

    # Aggregated
    final_comments: list[ReviewComment]
    summary: str

    # Output
    acknowledge_comment_id: int | None  # Initial notification comment
    review_id: int | None
    errors: list[str]
