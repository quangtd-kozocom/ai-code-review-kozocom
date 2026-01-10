"""Pydantic models for LLM structured outputs.

These models define the expected JSON schema for LLM responses.
Using Pydantic ensures type safety and automatic validation.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "AgentFinding",
    "AgentFindings",
    "FixResult",
    "ExplainResult",
    "Evidence",
]


class Evidence(BaseModel):
    """Evidence citation for a finding."""

    source_file: str = Field(description="File containing the evidence")
    source_function: str = Field(description="Function name in the evidence")
    quote: str = Field(description="Exact code quote proving the issue")
    line_number: int | None = Field(default=None, description="Line number if available")


class AgentFinding(BaseModel):
    """
    A single finding from a code review agent.

    This is the structured output expected from Security, Logic, and Style agents.
    """

    line: int = Field(
        ...,
        description="Line number in the file where the issue was found",
        ge=1,
    )
    severity: Literal["critical", "warning", "info", "suggestion"] = Field(
        ...,
        description="Severity level of the finding",
    )
    message: str = Field(
        ...,
        description="Clear description of the issue",
        min_length=10,
    )
    suggestion: str | None = Field(
        default=None,
        description="Suggested fix for the issue",
    )
    confidence: float = Field(
        ...,
        description="Confidence score between 0 and 1",
        ge=0.0,
        le=1.0,
    )
    evidence: Evidence | None = Field(
        default=None,
        description="Citation proving this issue (strongly recommended for confidence >= 0.85)"
    )

    @field_validator("confidence")
    @classmethod
    def validate_high_confidence(cls, v: float, info) -> float:
        if v >= 0.90 and not info.data.get("evidence"):
            return 0.84
        return v


class AgentFindings(BaseModel):
    """
    Collection of findings from a code review agent.

    The LLM will return this structure containing all findings for a file.
    """

    findings: list[AgentFinding] = Field(
        default_factory=list,
        description="List of findings from the analysis",
    )


class FixResult(BaseModel):
    """
    Result from the fix command handler.

    Contains the fixed code and an explanation.
    """

    fixed_code: str = Field(
        ...,
        description="The corrected code that fixes the issue",
    )
    explanation: str = Field(
        default="",
        description="Brief explanation of what was fixed",
    )


class ExplainResult(BaseModel):
    """
    Result from the explain command handler.

    Contains structured explanation sections.
    """

    problem: str = Field(
        ...,
        description="What is the problem",
    )
    why_problem: str = Field(
        ...,
        description="Why is this a problem",
    )
    how_to_fix: str = Field(
        ...,
        description="How to fix it",
    )
    example: str | None = Field(
        default=None,
        description="Example of correct code",
    )
