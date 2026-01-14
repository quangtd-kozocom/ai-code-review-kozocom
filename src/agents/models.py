"""Pydantic models for LLM structured outputs."""

from pydantic import BaseModel, ConfigDict, Field

# ═══════════════════════════════════════════════════════════════════════════════
# Breaking Change Detection Models
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
    could_break_callers: bool = Field(description="Could break existing callers")
    line: int = Field(description="Line number in the NEW file where this change occurs")


class FileAnalysisResult(BaseModel):
    """Result of analyzing a file for breaking changes."""

    model_config = ConfigDict(populate_by_name=True)

    changes: list[AnalyzedChange] = Field(
        default_factory=list,
        alias="breaking_changes",
        description="List of changes detected",
    )
    summary: str = Field(default="", description="Brief summary of changes in this file")


class SearchPlanResult(BaseModel):
    """LLM's plan for searching callers."""

    queries: list[str] = Field(default_factory=list, description="Search queries to find callers")
    include_patterns: list[str] = Field(default_factory=list, description="Include patterns")
    exclude_patterns: list[str] = Field(default_factory=list, description="Exclude patterns")
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
    need_more_search: bool = Field(default=False)
    additional_queries: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8)
    reasoning: str = Field(default="")


class GeneratedComment(BaseModel):
    """A generated review comment."""

    line: int = Field(default=1)
    severity: str = Field(default="warning")
    message: str = Field(default="")
    recommendation: str = Field(default="")


class FileReviewResult(BaseModel):
    """Result of generating review for a file."""

    comments: list[GeneratedComment] = Field(default_factory=list)
    summary: str = Field(default="")


# ═══════════════════════════════════════════════════════════════════════════════
# Fix Command Models
# ═══════════════════════════════════════════════════════════════════════════════


class FixResult(BaseModel):
    """Result of generating a single code fix."""

    fixed_code: str = Field(description="The corrected code snippet")
    explanation: str = Field(description="Brief explanation of what was fixed")


class BatchFixItem(BaseModel):
    """A single fix in a batch fix response."""

    file: str = Field(description="File path")
    fixed_code: str = Field(description="The corrected code snippet")
    explanation: str = Field(description="Brief explanation")


class BatchFixResult(BaseModel):
    """Result of batch fixing multiple files."""

    fixes: list[BatchFixItem] = Field(default_factory=list)
