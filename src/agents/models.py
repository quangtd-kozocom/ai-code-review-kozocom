"""Pydantic models for LLM structured outputs."""

from pydantic import BaseModel, ConfigDict, Field

# ═══════════════════════════════════════════════════════════════════════════════
# New Breaking Change Detection Models
# ═══════════════════════════════════════════════════════════════════════════════


class AnalyzedChange(BaseModel):
    """A single change detected in a file."""

    entity_type: str = Field(description="Type: function, method, constant, class, interface, etc.")
    entity_name: str = Field(description="Name of the entity")
    class_name: str | None = Field(None, description="Class name if method/property")
    change_type: str = Field(description="Type of change: signature_changed, deleted, etc.")
    old_definition: str | None = Field(None, description="Old code/signature")
    new_definition: str | None = Field(None, description="New code/signature")
    change_detail: str = Field(description="Human-readable description of what changed")
    could_break_callers: bool = Field(
        description="Whether this change could break existing callers"
    )
    line: int = Field(
        description="Line number in the NEW file where this change occurs (from diff)"
    )


class FileAnalysisResult(BaseModel):
    """Result of analyzing a file for breaking changes."""

    model_config = ConfigDict(populate_by_name=True)

    # Accept both 'changes' and 'breaking_changes' from LLM
    changes: list[AnalyzedChange] = Field(
        default_factory=list,
        alias="breaking_changes",
        description="List of changes detected",
    )
    summary: str = Field(
        default="",
        description="Brief summary of changes in this file",
    )


class SearchPlanResult(BaseModel):
    """LLM's plan for searching callers."""

    queries: list[str] = Field(default_factory=list, description="Search queries to find callers")
    include_patterns: list[str] = Field(
        default_factory=list, description="File patterns to include (e.g., *.php)"
    )
    exclude_patterns: list[str] = Field(
        default_factory=list, description="File patterns to exclude (e.g., *test*)"
    )
    reasoning: str = Field(default="", description="Why these queries will find relevant callers")


class VerifiedCaller(BaseModel):
    """A verified caller that will be affected."""

    file_path: str
    line: int = Field(default=1)
    call_text: str = Field(default="", description="The actual call code")
    will_break: bool = Field(default=True, description="Whether this call will break")
    break_reason: str = Field(default="", description="Why it will break")


class ImpactVerificationResult(BaseModel):
    """Result of verifying impact on callers."""

    affected_callers: list[VerifiedCaller] = Field(default_factory=list)
    need_more_search: bool = Field(default=False, description="Whether more searching is needed")
    additional_queries: list[str] = Field(
        default_factory=list, description="Additional queries if need_more_search"
    )
    confidence: float = Field(default=0.8, description="Confidence 0.0-1.0")  # Removed constraints
    reasoning: str = Field(default="", description="Explanation of the analysis")


class GeneratedComment(BaseModel):
    """A generated review comment."""

    line: int = Field(default=1, description="Line number in the file")
    severity: str = Field(default="warning", description="critical, warning, or info")
    message: str = Field(default="", description="The comment message with full context")
    recommendation: str = Field(default="", description="Suggested fix or action")


class FileReviewResult(BaseModel):
    """Result of generating review for a file."""

    comments: list[GeneratedComment] = Field(default_factory=list)
    summary: str = Field(default="", description="Brief summary of issues found")


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy Models (for chat commands compatibility)
# ═══════════════════════════════════════════════════════════════════════════════


class FixResult(BaseModel):
    """Result of generating a code fix."""

    fixed_code: str = Field(description="The corrected code snippet")
    explanation: str = Field(description="Explanation of what was fixed and why")


class AgentFinding(BaseModel):
    """A single finding from an agent review."""

    title: str = Field(description="Short title of the issue")
    line: int = Field(ge=1, description="Line number in the file")
    severity: str = Field(description="critical, warning, or info")
    message: str = Field(description="Detailed explanation of the issue")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class AgentFindings(BaseModel):
    """Collection of findings from an agent."""

    findings: list[AgentFinding] = Field(default_factory=list)


class ExplainResult(BaseModel):
    """Result of explaining code."""

    explanation: str = Field(description="Explanation of the code")
