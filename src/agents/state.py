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
        """Format file change for LLM prompt with enhanced context.

        Includes:
        - Diff content
        - Enhanced code structure (functions with signatures, types, decorators)
        - Class inheritance info
        - Related code from RAG
        """
        lines = [f"## File: {self.filename}", "", "### Diff:", "```", self.patch, "```"]

        # Add enhanced AST info if available
        if self.ast_info and (self.ast_info.functions or self.ast_info.classes):
            lines.extend(["", "### Code Structure:"])

            # Enhanced function info with types and decorators
            for func in self.ast_info.functions:
                func_desc = self._format_function_info(func)
                lines.append(func_desc)

            # Enhanced class info with inheritance
            for cls in self.ast_info.classes:
                cls_desc = self._format_class_info(cls)
                lines.append(cls_desc)

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

    def _format_function_info(self, func) -> str:
        """Format FunctionInfo with enhanced details."""
        parts: list[str] = []

        # Decorators
        if hasattr(func, "decorators") and func.decorators:
            parts.append(f"  @{', @'.join(func.decorators)}")

        # Async indicator
        prefix = "async " if getattr(func, "is_async", False) else ""

        # Function signature with types
        if hasattr(func, "parameters") and func.parameters:
            params = ", ".join(
                f"{p.name}: {p.type_hint}" if p.type_hint else p.name for p in func.parameters
            )
            sig = f"{prefix}def {func.name}({params})"
        else:
            sig = f"{prefix}def {func.name}()"

        # Return type
        if hasattr(func, "return_type") and func.return_type:
            sig += f" -> {func.return_type}"

        parts.append(f"- **Function**: `{sig}`")

        # Docstring summary
        if hasattr(func, "docstring") and func.docstring:
            # First line of docstring
            doc_summary = func.docstring.split("\n")[0][:100]
            parts.append(f"  - Doc: {doc_summary}")

        return "\n".join(parts)

    def _format_class_info(self, cls) -> str:
        """Format ClassInfo with enhanced details."""
        parts: list[str] = []

        # Decorators
        if hasattr(cls, "decorators") and cls.decorators:
            parts.append(f"  @{', @'.join(cls.decorators)}")

        # Class with inheritance
        if hasattr(cls, "base_classes") and cls.base_classes:
            inheritance = f"({', '.join(cls.base_classes)})"
        else:
            inheritance = ""

        parts.append(f"- **Class**: `{cls.name}{inheritance}`")

        # Methods
        if cls.methods:
            methods_str = ", ".join(cls.methods[:5])
            if len(cls.methods) > 5:
                methods_str += f" ... (+{len(cls.methods) - 5} more)"
            parts.append(f"  - Methods: {methods_str}")

        # Docstring summary
        if hasattr(cls, "docstring") and cls.docstring:
            doc_summary = cls.docstring.split("\n")[0][:100]
            parts.append(f"  - Doc: {doc_summary}")

        return "\n".join(parts)


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

    # RAG context - which files were used to inform this comment
    related_files: list[str] = Field(default_factory=list)

    # Code suggestion - actual code fix example
    code_suggestion: str | None = None


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

    # Router decisions: {filename: [agents to run]}
    routing_decisions: dict[str, list[str]]

    # Agent outputs (merged via operator.add)
    comments: Annotated[list[ReviewComment], operator.add]

    # Aggregated
    final_comments: list[ReviewComment]
    summary: str

    # Output
    acknowledge_comment_id: int | None  # Initial notification comment
    review_id: int | None
    errors: list[str]
