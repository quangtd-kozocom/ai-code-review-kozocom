"""Agent modules for AI Code Reviewer."""

from .constants import (
    # Change types
    CHANGE_CONTRACT,
    CHANGE_DELETED,
    CHANGE_RENAMED,
    CHANGE_SIGNATURE,
    CHANGE_VALUE,
    CHANGE_VISIBILITY,
    # Entity types
    ENTITY_CLASS,
    ENTITY_CONSTANT,
    ENTITY_ENUM,
    ENTITY_FUNCTION,
    ENTITY_INTERFACE,
    ENTITY_METHOD,
    ENTITY_PROPERTY,
    ENTITY_TYPE,
    # Severity
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from .graph import create_review_graph, run_review
from .models import (
    # Legacy models
    AgentFinding,
    AgentFindings,
    # New breaking change models
    AnalyzedChange,
    ExplainResult,
    FileAnalysisResult,
    FileReviewResult,
    FixResult,
    GeneratedComment,
    ImpactVerificationResult,
    SearchPlanResult,
    VerifiedCaller,
)
from .state import (
    AffectedCaller,
    BreakingChange,
    DetectedChange,
    FileDiff,
    PRContext,
    ReviewComment,
    ReviewState,
    SearchPlan,
    SearchResult,
)

__all__ = [
    # Graph
    "create_review_graph",
    "run_review",
    # Constants - Entity types
    "ENTITY_FUNCTION",
    "ENTITY_METHOD",
    "ENTITY_CONSTANT",
    "ENTITY_PROPERTY",
    "ENTITY_INTERFACE",
    "ENTITY_CLASS",
    "ENTITY_ENUM",
    "ENTITY_TYPE",
    # Constants - Change types
    "CHANGE_SIGNATURE",
    "CHANGE_DELETED",
    "CHANGE_VALUE",
    "CHANGE_VISIBILITY",
    "CHANGE_CONTRACT",
    "CHANGE_RENAMED",
    # Constants - Severity
    "SEVERITY_CRITICAL",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",
    # State
    "ReviewState",
    "PRContext",
    "FileDiff",
    "DetectedChange",
    "SearchPlan",
    "SearchResult",
    "AffectedCaller",
    "BreakingChange",
    "ReviewComment",
    # New Models
    "AnalyzedChange",
    "FileAnalysisResult",
    "SearchPlanResult",
    "VerifiedCaller",
    "ImpactVerificationResult",
    "GeneratedComment",
    "FileReviewResult",
    # Legacy Models
    "AgentFinding",
    "AgentFindings",
    "ExplainResult",
    "FixResult",
]
