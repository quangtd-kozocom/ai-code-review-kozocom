# 04 - Models & Schemas

## 📦 Model Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MODELS STRUCTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  schemas.py (Pure Pydantic)          models.py (SQLModel)       │
│  ┌──────────────────────────┐        ┌─────────────────────┐    │
│  │ ReviewerConfig           │        │ ConfigModel (table) │    │
│  │ ReviewsConfig            │        │ ConfigCreate        │    │
│  │ PathInstruction          │        │ ConfigUpdate        │    │
│  │ AutoReviewConfig         │        │ ConfigRead          │    │
│  │ ChatConfig               │        └─────────────────────┘    │
│  │ + Helper methods         │                                   │
│  └──────────────────────────┘                                   │
│       ▲                                      ▲                   │
│       │ Validation & Business Logic          │ Database I/O     │
│       └──────────────────────────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Pydantic Schemas (Validation)

### File: `src/core/config/schemas.py`

````python
"""
Pydantic schemas for configuration validation.

These are pure Pydantic models for:
- YAML file validation
- API request/response
- Business logic helpers
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class ReviewProfile(StrEnum):
    """Review strictness profiles."""

    CHILL = "chill"      # High threshold, fewer comments
    DEFAULT = "default"  # Balanced
    STRICT = "strict"    # Low threshold, more comments


class PathInstruction(BaseModel):
    """Path-specific review instructions."""

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

    profile: ReviewProfile = Field(
        default=ReviewProfile.DEFAULT,
        description="Review strictness profile",
    )
    agents: list[str] = Field(
        default=["security", "logic", "style"],
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
                raise ValueError(
                    f"Invalid agent: {agent}. Valid: {valid_agents}"
                )
        return v


class ChatConfig(BaseModel):
    """Chat command configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable @reviewer commands",
    )
    allowed_commands: list[str] = Field(
        default=["fix", "explain", "tests", "help"],
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

    class Config:
        """Pydantic config."""
        extra = "ignore"  # Forward compatibility

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

    def should_ignore(self, file_path: str) -> bool:
        """
        Check if file should be ignored.

        Supports glob patterns with ** for recursive matching.
        """
        import fnmatch
        import re

        for pattern in self.ignore:
            if "**" in pattern:
                # Convert ** to regex
                regex = pattern.replace("**", ".*").replace("*", "[^/]*")
                if re.match(regex, file_path):
                    return True
            elif fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def get_path_instructions(self, file_path: str) -> list[str]:
        """
        Get matching instructions for a file.

        Returns list of instruction strings.
        """
        import fnmatch
        import re

        instructions = []
        for pi in self.reviews.path_instructions:
            if "**" in pi.path:
                regex = pi.path.replace("**", ".*").replace("*", "[^/]*")
                if re.match(regex, file_path):
                    instructions.append(pi.instructions)
            elif fnmatch.fnmatch(file_path, pi.path):
                instructions.append(pi.instructions)
        return instructions

    def should_auto_review(
        self,
        title: str,
        author: str,
        base_branch: str,
        is_draft: bool,
    ) -> bool:
        """Determine if PR should be auto-reviewed."""
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
````

---

## 🗄️ SQLModel Models (Database)

### File: `src/core/config/models.py`

```python
"""
SQLModel definitions for database storage.

SQLModel = SQLAlchemy + Pydantic combined.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class ConfigBase(SQLModel):
    """Base fields shared across models."""

    owner: str = Field(index=True, max_length=255)
    repo: str = Field(index=True, max_length=255)


class ConfigModel(ConfigBase, table=True):
    """
    Database table for configs.

    Stores full config as JSONB for schema flexibility.
    """
    __tablename__ = "configs"
    __table_args__ = (
        UniqueConstraint("owner", "repo", name="uq_configs_owner_repo"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Config stored as JSONB
    config_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, default={}),
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Audit
    created_by: Optional[str] = Field(default=None, max_length=255)


class ConfigCreate(ConfigBase):
    """Schema for creating config."""
    config_data: dict = Field(default_factory=dict)
    created_by: Optional[str] = None


class ConfigUpdate(SQLModel):
    """Schema for updating config."""
    config_data: dict
    updated_by: Optional[str] = None


class ConfigRead(ConfigBase):
    """Schema for API response."""
    id: int
    config_data: dict
    created_at: datetime
    updated_at: datetime
```

---

## 🧪 Tests

### File: `tests/core/config/test_schemas.py`

```python
"""Tests for config schemas."""

import pytest
from src.core.config.schemas import (
    ReviewerConfig,
    ReviewProfile,
    PathInstruction,
)


class TestReviewerConfig:
    """Test ReviewerConfig schema."""

    def test_default_values(self):
        """Test defaults are sensible."""
        config = ReviewerConfig()

        assert config.language == "en"
        assert config.reviews.profile == ReviewProfile.DEFAULT
        assert config.reviews.confidence_threshold == 0.7
        assert config.reviews.agents == ["security", "logic", "style"]
        assert config.ignore == []
        assert config.chat.enabled is True

    def test_parse_yaml_dict(self):
        """Test parsing YAML-like dict."""
        data = {
            "language": "vi",
            "reviews": {
                "profile": "strict",
                "confidence_threshold": 0.6,
            },
            "ignore": ["**/migrations/**"],
        }

        config = ReviewerConfig(**data)

        assert config.language == "vi"
        assert config.reviews.profile == ReviewProfile.STRICT
        assert config.reviews.confidence_threshold == 0.6
        assert len(config.ignore) == 1

    def test_extra_fields_ignored(self):
        """Unknown fields should be ignored."""
        data = {
            "language": "en",
            "unknown_field": "value",
            "reviews": {"future_option": True},
        }

        config = ReviewerConfig(**data)
        assert config.language == "en"

    def test_invalid_agent_raises(self):
        """Invalid agent name should raise."""
        with pytest.raises(ValueError, match="Invalid agent"):
            ReviewerConfig(**{
                "reviews": {"agents": ["invalid"]}
            })


class TestShouldIgnore:
    """Test ignore pattern matching."""

    def test_simple_pattern(self):
        config = ReviewerConfig(ignore=["*.lock"])

        assert config.should_ignore("poetry.lock") is True
        assert config.should_ignore("main.py") is False

    def test_recursive_pattern(self):
        config = ReviewerConfig(ignore=["**/migrations/**"])

        assert config.should_ignore("src/migrations/001.py") is True
        assert config.should_ignore("migrations/init.py") is True
        assert config.should_ignore("src/main.py") is False

    def test_multiple_patterns(self):
        config = ReviewerConfig(ignore=[
            "**/migrations/**",
            "**/__pycache__/**",
            "*.lock",
        ])

        assert config.should_ignore("src/migrations/foo.py") is True
        assert config.should_ignore("lib/__pycache__/bar.pyc") is True
        assert config.should_ignore("yarn.lock") is True
        assert config.should_ignore("src/app.py") is False


class TestPathInstructions:
    """Test path instruction matching."""

    def test_single_match(self):
        config = ReviewerConfig(
            reviews={
                "path_instructions": [
                    {"path": "src/api/**", "instructions": "Check auth"},
                ]
            }
        )

        result = config.get_path_instructions("src/api/users.py")
        assert "Check auth" in result

    def test_no_match(self):
        config = ReviewerConfig(
            reviews={
                "path_instructions": [
                    {"path": "src/api/**", "instructions": "Check auth"},
                ]
            }
        )

        result = config.get_path_instructions("tests/test.py")
        assert result == []

    def test_multiple_matches(self):
        config = ReviewerConfig(
            reviews={
                "path_instructions": [
                    {"path": "src/**", "instructions": "General rule"},
                    {"path": "src/api/**", "instructions": "API rule"},
                ]
            }
        )

        result = config.get_path_instructions("src/api/users.py")
        assert len(result) == 2


class TestProfileBehavior:
    """Test profile affects thresholds."""

    def test_chill_profile(self):
        config = ReviewerConfig(reviews={"profile": "chill"})

        assert config.get_threshold() == 0.85
        assert config.get_max_comments() == 5

    def test_strict_profile(self):
        config = ReviewerConfig(reviews={"profile": "strict"})

        assert config.get_threshold() == 0.6
        assert config.get_max_comments() == 20

    def test_explicit_overrides(self):
        config = ReviewerConfig(
            reviews={
                "profile": "chill",
                "confidence_threshold": 0.5,
            }
        )

        # Explicit wins over profile
        assert config.get_threshold() == 0.5


class TestAutoReview:
    """Test auto-review logic."""

    def test_disabled(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"enabled": False}}
        )

        assert config.should_auto_review(
            title="feat: new", author="dev",
            base_branch="main", is_draft=False
        ) is False

    def test_skip_keyword(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"skip_keywords": ["[WIP]"]}}
        )

        assert config.should_auto_review(
            title="[WIP] work in progress", author="dev",
            base_branch="main", is_draft=False
        ) is False

    def test_skip_draft(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"drafts": False}}
        )

        assert config.should_auto_review(
            title="feat: new", author="dev",
            base_branch="main", is_draft=True
        ) is False

    def test_allow_draft(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"drafts": True}}
        )

        assert config.should_auto_review(
            title="feat: new", author="dev",
            base_branch="main", is_draft=True
        ) is True
```

---

## ✅ Key Design Decisions

1. **Separate schemas.py and models.py**

   - schemas.py → Validation + business logic
   - models.py → Database operations

2. **JSONB for config_data**

   - Flexible schema evolution
   - No migrations for new fields

3. **Helper methods on ReviewerConfig**

   - `get_threshold()`, `should_ignore()`, etc.
   - Business logic in one place

4. **Forward compatibility**
   - `extra = "ignore"` allows new fields
