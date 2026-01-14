"""Agent modules for AI Code Reviewer."""

from .constants import (
    CHANGE_CONTRACT,
    CHANGE_DELETED,
    CHANGE_RENAMED,
    CHANGE_SIGNATURE,
    CHANGE_VALUE,
    CHANGE_VISIBILITY,
    ENTITY_CLASS,
    ENTITY_CONSTANT,
    ENTITY_ENUM,
    ENTITY_FUNCTION,
    ENTITY_INTERFACE,
    ENTITY_METHOD,
    ENTITY_PROPERTY,
    ENTITY_TYPE,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from .graph import create_review_graph, run_review
from .models import (
    AnalyzedChange,
    BatchFixItem,
    BatchFixResult,
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
    "create_review_graph", "run_review",
    # Constants
    "ENTITY_FUNCTION", "ENTITY_METHOD", "ENTITY_CONSTANT", "ENTITY_PROPERTY",
    "ENTITY_INTERFACE", "ENTITY_CLASS", "ENTITY_ENUM", "ENTITY_TYPE",
    "CHANGE_SIGNATURE", "CHANGE_DELETED", "CHANGE_VALUE", "CHANGE_VISIBILITY",
    "CHANGE_CONTRACT", "CHANGE_RENAMED",
    "SEVERITY_CRITICAL", "SEVERITY_WARNING", "SEVERITY_INFO",
    # State
    "ReviewState", "PRContext", "FileDiff", "DetectedChange",
    "SearchPlan", "SearchResult", "AffectedCaller", "BreakingChange", "ReviewComment",
    # Models
    "AnalyzedChange", "FileAnalysisResult", "SearchPlanResult", "VerifiedCaller",
    "ImpactVerificationResult", "GeneratedComment", "FileReviewResult",
    "FixResult", "BatchFixItem", "BatchFixResult",
]
