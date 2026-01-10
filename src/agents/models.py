"""Pydantic models for LLM structured outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    """A single finding from code review."""
    
    line: int = Field(..., description="Line number", ge=1)
    severity: Literal["critical", "warning", "info", "suggestion"]
    message: str = Field(..., description="Issue description", min_length=10)
    suggestion: str | None = Field(None, description="How to fix it")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level")
    dependencies_checked: list[dict] | None = Field(
        None,
        description="Dependencies that were verified"
    )


class AgentFindings(BaseModel):
    """Collection of findings from code review."""
    
    findings: list[AgentFinding] = Field(
        default_factory=list,
        description="List of findings"
    )


class ExplainResult(BaseModel):
    """Result from explain command."""
    
    explanation: str = Field(..., description="Detailed explanation")
    severity: Literal["critical", "warning", "info", "suggestion"]
    related_code: str | None = Field(None, description="Related code context")


class FixResult(BaseModel):
    """Result from fix command."""
    
    fixed_code: str = Field(..., description="Fixed code")
    explanation: str = Field(..., description="What was fixed")
    changes_made: list[str] = Field(
        default_factory=list,
        description="List of changes"
    )


class ContextEvaluation(BaseModel):
    """LLM evaluation of whether we have sufficient context."""
    
    context_sufficient: bool = Field(
        ...,
        description="True if we have enough context to review accurately"
    )
    need_more_context_for: list[str] = Field(
        default_factory=list,
        description="List of class/service names to search for next iteration"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level in this evaluation"
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why more context is or isn't needed"
    )
