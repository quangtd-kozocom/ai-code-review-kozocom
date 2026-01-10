"""State management for the PR review workflow.

Defines the state schema and data models for the LangGraph workflow.
Uses Python 3.14 features for cleaner type definitions.
"""

import operator
from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from ..analysis.call_graph import CallGraph
from ..analysis.context_builder import FunctionContext, ReviewContext
from ..analysis.diff_extractor import ChangeType, FileDiff
from ..analysis.external_discovery import ExternalFile
from ..analysis.impact_analyzer import FunctionImpact, ImpactLevel, ImpactReport
from ..core.config import ReviewerConfig

__all__ = [
    "PRContext",
    "DependencyAnalysis",
    "CodeRef",
    "AffectedFile",
    "ReviewComment",
    "ReviewState",
    "FunctionReviewInput",
    "ExternalFile",
]

type Severity = Literal["critical", "warning", "info", "suggestion"]
type ReviewDepth = Literal["deep", "standard", "quick"]


@dataclass(frozen=True, slots=True)
class PRContext:
    """Context about the PR being reviewed."""
    
    owner: str
    repo: str
    pr_number: int
    title: str
    author: str
    installation_id: int
    base_branch: str
    head_branch: str
    is_draft: bool = False


class DependencyAnalysis(BaseModel):
    """Information about a dependency that was analyzed for a comment."""

    name: str
    file: str | None = None
    behavior_verified: bool = False
    validation_provided: bool = False
    summary: str | None = None

    model_config = {"frozen": True}


class CodeRef(BaseModel):
    """Reference to code location with context."""
    
    file: str
    line: int
    name: str  # Function/class name
    break_reason: str | None = None  # WHY it will break
    
    model_config = {"frozen": True}


class AffectedFile(BaseModel):
    """External file affected by this change."""
    
    path: str
    line: int | None = None
    break_reason: str
    
    model_config = {"frozen": True}


class ReviewComment(BaseModel):
    """A review comment to post to GitHub."""

    file: str
    line: int
    severity: Severity
    category: str
    message: str
    suggestion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    agent: str = "function_reviewer"

    # Code suggestion with language hint
    code_suggestion: str | None = None

    # Context used for this comment
    related_context: list[str] = Field(default_factory=list)

    # Dependencies analyzed for this comment
    dependencies_analyzed: list[DependencyAnalysis] = Field(default_factory=list)

    # Issue grouping support
    issue_group: str | None = None
    related_issues: list[str] = Field(default_factory=list)

    # Impact context (NEW - for breaking changes focus)
    affected_files: list[AffectedFile] = Field(default_factory=list)
    caller_refs: list[CodeRef] = Field(default_factory=list)
    dependency_refs: list[CodeRef] = Field(default_factory=list)

    model_config = {"frozen": True}


@dataclass(slots=True)
class FunctionReviewInput:
    """Input for reviewing a single function."""
    
    function_context: FunctionContext
    review_depth: ReviewDepth = "standard"
    focus_areas: list[str] = field(default_factory=list)


class ReviewState(TypedDict, total=False):
    """State passed through the LangGraph workflow.
    
    Uses TypedDict with total=False for optional fields.
    Fields are added progressively as the workflow executes.
    """
    
    # =========================================================================
    # Input (from webhook)
    # =========================================================================
    pr_context: PRContext
    repo_config: ReviewerConfig
    
    # =========================================================================
    # Phase 1: Diff Analysis (deterministic)
    # =========================================================================
    file_diffs: list[FileDiff]
    function_changes: dict[str, dict]  # {func_name: {type, old, new}}
    file_contents: dict[str, str]  # Map file paths to content
    new_files: list[str]
    deleted_files: list[str]
    
    # =========================================================================
    # Phase 2: Impact Analysis (AST-based)
    # =========================================================================
    call_graph: CallGraph
    impact_report: ImpactReport
    
    # =========================================================================
    # Phase 2.5: External Discovery (evaluator loop state)
    # =========================================================================
    external_files: list[ExternalFile]
    pending_searches: list[str]  # Targets for next discovery iteration
    context_sufficient: bool  # LLM evaluator result
    evaluation_iteration: int  # Current iteration count
    breaking_changes: list[str]
    
    # =========================================================================
    # Phase 3: Review (LLM-based)
    # =========================================================================
    review_context: ReviewContext
    functions_to_review: list[FunctionReviewInput]
    
    # Review outputs (merged via operator.add)
    comments: Annotated[list[ReviewComment], operator.add]
    
    # =========================================================================
    # Aggregation & Output
    # =========================================================================
    final_comments: list[ReviewComment]
    summary: str
    review_id: int | None
    errors: list[str] | None
    
    # =========================================================================
    # Workflow Control
    # =========================================================================
    skip_review: bool
    skip_reason: str | None


def create_initial_state(
    pr_context: PRContext,
    repo_config: ReviewerConfig | None = None,
) -> ReviewState:
    """Create initial state for workflow.
    
    Args:
        pr_context: PR context from webhook.
        repo_config: Repository configuration.
        
    Returns:
        Initial ReviewState with required fields.
    """
    return ReviewState(
        pr_context=pr_context,
        repo_config=repo_config or ReviewerConfig(),
        comments=[],
        skip_review=False,
    )
