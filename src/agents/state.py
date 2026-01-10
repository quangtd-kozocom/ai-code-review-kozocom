"""State management for the PR review workflow.

Defines the state schema and data models for the LangGraph workflow.
Uses Python 3.14 features for cleaner type definitions.
"""

import operator
from dataclasses import dataclass, field
from typing import Annotated, TypedDict

__all__ = [
    "PRContext",
    "FileDiff",
    "DetectedChange",
    "SearchPlan",
    "SearchResult",
    "AffectedCaller",
    "BreakingChange",
    "ReviewComment",
    "ReviewState",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PRContext:
    """Input: PR information from webhook."""

    owner: str
    repo: str
    pr_number: int
    title: str
    author: str
    installation_id: int
    base_branch: str  # e.g., "main"
    head_branch: str  # e.g., "feature/payment"
    is_draft: bool = False  # Whether PR is a draft


@dataclass(slots=True)
class FileDiff:
    """A file changed in the PR."""

    file_path: str
    status: str  # "added", "modified", "deleted", "renamed"
    base_content: str | None  # Old content
    head_content: str | None  # New content
    patch: str  # Git diff
    language: str | None = None


@dataclass(slots=True)
class DetectedChange:
    """A change detected by LLM that could break callers."""

    entity_type: str  # "function", "method", "constant", "class", etc.
    entity_name: str  # "processPayment"
    class_name: str | None  # "PaymentService"
    file_path: str
    language: str
    change_type: str  # "signature_changed", "deleted", etc.
    old_definition: str | None
    new_definition: str | None
    change_detail: str  # "Added required parameter: $customerId"
    line: int  # Line number in new file where change occurs


@dataclass(slots=True)
class SearchPlan:
    """LLM's plan for searching callers."""

    queries: list[str]  # ["processPayment(", "PaymentService::"]
    include_patterns: list[str]  # ["*.php", "*.blade.php"]
    exclude_patterns: list[str]  # ["*test*", "*vendor*"]
    reasoning: str


@dataclass(slots=True)
class SearchResult:
    """A file found by search."""

    file_path: str
    line: int
    match_text: str  # The matched line content
    context: str  # Surrounding lines for LLM analysis


@dataclass(slots=True)
class AffectedCaller:
    """A confirmed caller that will break."""

    file_path: str
    line: int
    call_text: str  # "processPayment($amount, $method)"
    break_reason: str  # "Missing required parameter: $customerId"


@dataclass(slots=True)
class BreakingChange:
    """A confirmed breaking change with full context."""

    # What changed
    entity_type: str
    entity_name: str
    class_name: str | None
    file_path: str
    change_type: str
    old_definition: str | None
    new_definition: str | None
    change_detail: str
    line: int  # Line number in new file

    # Who is affected
    affected_callers: list[AffectedCaller] = field(default_factory=list)

    # Output
    severity: str = "warning"  # "critical", "warning"
    recommendation: str = ""


@dataclass(slots=True)
class ReviewComment:
    """A comment to post to GitHub."""

    file: str
    line: int
    severity: str  # "critical", "warning", "info"
    message: str
    affected_files: list[dict] = field(default_factory=list)  # [{path, line, reason}]
    recommendation: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow State
# ═══════════════════════════════════════════════════════════════════════════════


class ReviewState(TypedDict, total=False):
    """State passed through the LangGraph workflow."""

    # ───────────────────────────────────────────────────────────────────────────
    # Input
    # ───────────────────────────────────────────────────────────────────────────
    pr_context: PRContext

    # ───────────────────────────────────────────────────────────────────────────
    # extract_diff + clone_repo
    # ───────────────────────────────────────────────────────────────────────────
    file_diffs: list[FileDiff]
    repo_path: str

    # ───────────────────────────────────────────────────────────────────────────
    # File loop state
    # ───────────────────────────────────────────────────────────────────────────
    pending_files: list[FileDiff]  # Files left to process
    current_file: FileDiff | None  # File being processed

    # ───────────────────────────────────────────────────────────────────────────
    # analyze_file output (per file)
    # ───────────────────────────────────────────────────────────────────────────
    file_changes: list[DetectedChange]  # Changes in current file
    current_change_index: int  # Which change in file
    current_change: DetectedChange | None  # Change being searched

    # ───────────────────────────────────────────────────────────────────────────
    # Search loop state (per change)
    # ───────────────────────────────────────────────────────────────────────────
    search_plan: SearchPlan | None
    search_results: list[SearchResult]
    verified_callers: list[AffectedCaller]
    need_more_search: bool
    additional_queries: list[str]
    search_iteration: int

    # ───────────────────────────────────────────────────────────────────────────
    # Per-file results
    # ───────────────────────────────────────────────────────────────────────────
    file_breaking_changes: list[BreakingChange]
    file_comments: list[ReviewComment]

    # ───────────────────────────────────────────────────────────────────────────
    # Accumulated results (across all files)
    # ───────────────────────────────────────────────────────────────────────────
    all_breaking_changes: Annotated[list[BreakingChange], operator.add]
    all_comments: Annotated[list[ReviewComment], operator.add]
    published_comments: Annotated[list[ReviewComment], operator.add]

    # ───────────────────────────────────────────────────────────────────────────
    # Final publish results
    # ───────────────────────────────────────────────────────────────────────────
    github_results: list[dict]
    slack_result: dict | None
    jira_result: dict | None

    # ───────────────────────────────────────────────────────────────────────────
    # Control
    # ───────────────────────────────────────────────────────────────────────────
    skip_review: bool
    skip_reason: str | None
    errors: list[str]
