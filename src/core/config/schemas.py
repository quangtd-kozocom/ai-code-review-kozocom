"""
Pydantic schemas for configuration validation.

These are pure Pydantic models for:
- YAML file validation
- API request/response
- Business logic helpers
"""

from __future__ import annotations

import fnmatch
import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewProfile(StrEnum):
    """Review strictness profiles."""

    CHILL = "chill"  # High threshold, fewer comments
    DEFAULT = "default"  # Balanced
    STRICT = "strict"  # Low threshold, more comments


class PathInstruction(BaseModel):
    """Path-specific review instructions."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(
        ...,
        description="Glob pattern (e.g., 'src/api/**/*.py')",
        min_length=1,
    )
    instructions: str = Field(
        ...,
        description="Instructions for files matching this path",
        min_length=1,
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Ensure path is not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Path cannot be empty")
        return v


class AutoReviewConfig(BaseModel):
    """Auto-review trigger settings."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(
        default=True,
        description="Enable automatic review on PR open/sync",
    )
    drafts: bool = Field(
        default=False,
        description="Review draft PRs",
    )
    skip_keywords: list[str] = Field(
        default_factory=list,
        description="Skip PRs with these keywords in title",
    )
    base_branches: list[str] = Field(
        default_factory=list,
        description="Only review PRs targeting these branches",
    )
    ignore_authors: list[str] = Field(
        default_factory=list,
        description="Skip PRs from these authors",
    )


class ReviewsConfig(BaseModel):
    """Reviews section configuration."""

    model_config = ConfigDict(frozen=True)

    profile: ReviewProfile = Field(
        default=ReviewProfile.DEFAULT,
        description="Review strictness profile",
    )
    agents: list[str] = Field(
        default_factory=lambda: ["security", "logic", "style"],
        description="Agents to run",
    )
    confidence_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.7,
        description="Minimum confidence to report",
    )
    max_comments_per_file: Annotated[int, Field(ge=1, le=50)] = Field(
        default=10,
        description="Max comments per file",
    )
    path_instructions: list[PathInstruction] = Field(
        default_factory=list,
        description="Path-specific instructions",
    )
    auto_review: AutoReviewConfig = Field(
        default_factory=AutoReviewConfig,
        description="Auto-review settings",
    )

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, v: list[str]) -> list[str]:
        """Validate agent names."""
        valid_agents = {"security", "logic", "style"}
        for agent in v:
            if agent not in valid_agents:
                raise ValueError(f"Invalid agent: {agent}. Valid: {valid_agents}")
        return v


class ChatConfig(BaseModel):
    """Chat command configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(
        default=True,
        description="Enable @reviewer commands",
    )
    allowed_commands: list[str] = Field(
        default_factory=lambda: ["fix", "explain", "tests", "help"],
        description="Allowed commands",
    )


class ReviewerConfig(BaseModel):
    """
    Root configuration model for .reviewer.yaml.

    Example:
        ```yaml
        language: "vi"
        reviews:
          profile: "chill"
          confidence_threshold: 0.8
        ignore:
          - "**/migrations/**"
        ```
    """

    model_config = ConfigDict(extra="ignore")  # Forward compatibility

    language: str = Field(
        default="en",
        description="Response language code",
    )
    reviews: ReviewsConfig = Field(
        default_factory=ReviewsConfig,
    )
    ignore: list[str] = Field(
        default_factory=list,
        description="Glob patterns to ignore",
    )
    chat: ChatConfig = Field(
        default_factory=ChatConfig,
    )

    # ═══════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════

    def get_threshold(self) -> float:
        """Get effective threshold based on profile."""
        profile_thresholds = {
            ReviewProfile.CHILL: 0.85,
            ReviewProfile.DEFAULT: 0.7,
            ReviewProfile.STRICT: 0.6,
        }
        # Explicit value overrides profile default
        if self.reviews.confidence_threshold != 0.7:
            return self.reviews.confidence_threshold
        return profile_thresholds.get(self.reviews.profile, 0.7)

    def get_max_comments(self) -> int:
        """Get effective max comments based on profile."""
        profile_limits = {
            ReviewProfile.CHILL: 5,
            ReviewProfile.DEFAULT: 10,
            ReviewProfile.STRICT: 20,
        }
        if self.reviews.max_comments_per_file != 10:
            return self.reviews.max_comments_per_file
        return profile_limits.get(self.reviews.profile, 10)

    @staticmethod
    def _glob_to_regex(pattern: str) -> str:
        """
        Convert glob pattern to regex with proper ** handling.

        Handles:
        - ** matches any path including / (zero or more path segments)
        - * matches anything except /
        - ? matches single char except /

        Special handling:
        - **/ at start means "any prefix or no prefix"
        - /** at end means "any suffix or no suffix"

        Args:
            pattern: Glob pattern string.

        Returns:
            Regex pattern string.
        """
        # Handle special cases for ** at boundaries
        start_placeholder = "\x00START\x00"
        end_placeholder = "\x00END\x00"
        ds_placeholder = "\x00DS\x00"

        # **/ at start: optional prefix
        if pattern.startswith("**/"):
            pattern = start_placeholder + pattern[3:]
        # /** at end: optional suffix
        if pattern.endswith("/**"):
            pattern = pattern[:-3] + end_placeholder

        # Protect remaining ** from being processed as *
        pattern = pattern.replace("**", ds_placeholder)

        # Build regex character by character
        result: list[str] = []
        i = 0
        while i < len(pattern):
            # Check for placeholders
            if pattern[i:].startswith(start_placeholder):
                result.append("(.*/)?")  # Optional prefix with /
                i += len(start_placeholder)
                continue
            if pattern[i:].startswith(end_placeholder):
                result.append("(/.*)?")  # Optional suffix with /
                i += len(end_placeholder)
                continue
            if pattern[i:].startswith(ds_placeholder):
                result.append(".*")  # ** -> match anything including /
                i += len(ds_placeholder)
                continue

            c = pattern[i]
            if c == "*":
                result.append("[^/]*")  # * -> match anything except /
            elif c == "?":
                result.append("[^/]")  # ? -> match single char except /
            elif c in ".^$+{}[]|()":
                result.append("\\" + c)  # Escape regex special chars
            elif c == "\\":
                result.append("\\\\")  # Escape backslash
            else:
                result.append(c)
            i += 1

        return "".join(result)

    def should_ignore(self, file_path: str) -> bool:
        """
        Check if file should be ignored.

        Supports glob patterns with ** for recursive matching.

        Args:
            file_path: Path to check against ignore patterns.

        Returns:
            True if file should be ignored.
        """
        for pattern in self.ignore:
            if "**" in pattern or "*" in pattern or "?" in pattern:
                regex = self._glob_to_regex(pattern)
                if re.match(f"^{regex}$", file_path):
                    return True
            elif file_path == pattern:
                return True
        return False

    def get_path_instructions(self, file_path: str) -> list[str]:
        """
        Get matching instructions for a file.

        Args:
            file_path: Path to check against instruction patterns.

        Returns:
            List of instruction strings.
        """
        instructions: list[str] = []
        for pi in self.reviews.path_instructions:
            if "**" in pi.path or "*" in pi.path or "?" in pi.path:
                regex = self._glob_to_regex(pi.path)
                if re.match(f"^{regex}$", file_path):
                    instructions.append(pi.instructions)
            elif file_path == pi.path:
                instructions.append(pi.instructions)
        return instructions

    def should_auto_review(
        self,
        title: str,
        author: str,
        base_branch: str,
        is_draft: bool,
    ) -> bool:
        """
        Determine if PR should be auto-reviewed.

        Args:
            title: PR title.
            author: PR author username.
            base_branch: Target branch name.
            is_draft: Whether PR is a draft.

        Returns:
            True if PR should be auto-reviewed.
        """
        auto = self.reviews.auto_review

        if not auto.enabled:
            return False

        if is_draft and not auto.drafts:
            return False

        # Check skip keywords
        title_lower = title.lower()
        for keyword in auto.skip_keywords:
            if keyword.lower() in title_lower:
                return False

        # Check ignored authors
        if author in auto.ignore_authors:
            return False

        # Check base branch filter
        if auto.base_branches and base_branch not in auto.base_branches:
            return False

        return True

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if specific agent is enabled."""
        return agent_name in self.reviews.agents
