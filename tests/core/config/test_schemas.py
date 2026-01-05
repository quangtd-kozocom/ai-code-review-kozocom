"""Tests for config schemas."""

import pytest

from src.core.config.schemas import (
    AutoReviewConfig,
    PathInstruction,
    ReviewerConfig,
    ReviewProfile,
    ReviewsConfig,
)


class TestReviewerConfig:
    """Test ReviewerConfig schema."""

    def test_default_values(self) -> None:
        """Test defaults are sensible."""
        config = ReviewerConfig()

        assert config.language == "en"
        assert config.reviews.profile == ReviewProfile.DEFAULT
        assert config.reviews.confidence_threshold == 0.7
        assert config.reviews.agents == ["security", "logic", "style"]
        assert config.ignore == []
        assert config.chat.enabled is True

    def test_parse_yaml_dict(self) -> None:
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

    def test_extra_fields_ignored(self) -> None:
        """Unknown fields should be ignored."""
        data = {
            "language": "en",
            "unknown_field": "value",
            "reviews": {"future_option": True},
        }

        config = ReviewerConfig(**data)
        assert config.language == "en"

    def test_invalid_agent_raises(self) -> None:
        """Invalid agent name should raise."""
        with pytest.raises(ValueError, match="Invalid agent"):
            ReviewerConfig(**{"reviews": {"agents": ["invalid"]}})

    def test_invalid_threshold_raises(self) -> None:
        """Threshold outside 0-1 should raise."""
        with pytest.raises(ValueError):
            ReviewerConfig(**{"reviews": {"confidence_threshold": 1.5}})


class TestShouldIgnore:
    """Test ignore pattern matching."""

    def test_simple_pattern(self) -> None:
        config = ReviewerConfig(ignore=["*.lock"])

        assert config.should_ignore("poetry.lock") is True
        assert config.should_ignore("main.py") is False

    def test_recursive_pattern(self) -> None:
        config = ReviewerConfig(ignore=["**/migrations/**"])

        assert config.should_ignore("src/migrations/001.py") is True
        assert config.should_ignore("migrations/init.py") is True
        assert config.should_ignore("src/main.py") is False

    def test_multiple_patterns(self) -> None:
        config = ReviewerConfig(
            ignore=[
                "**/migrations/**",
                "**/__pycache__/**",
                "*.lock",
            ]
        )

        assert config.should_ignore("src/migrations/foo.py") is True
        assert config.should_ignore("lib/__pycache__/bar.pyc") is True
        assert config.should_ignore("yarn.lock") is True
        assert config.should_ignore("src/app.py") is False


class TestPathInstructions:
    """Test path instruction matching."""

    def test_single_match(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(
                path_instructions=[
                    PathInstruction(path="src/api/**", instructions="Check auth"),
                ]
            )
        )

        result = config.get_path_instructions("src/api/users.py")
        assert "Check auth" in result

    def test_no_match(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(
                path_instructions=[
                    PathInstruction(path="src/api/**", instructions="Check auth"),
                ]
            )
        )

        result = config.get_path_instructions("tests/test.py")
        assert result == []

    def test_multiple_matches(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(
                path_instructions=[
                    PathInstruction(path="src/**", instructions="General rule"),
                    PathInstruction(path="src/api/**", instructions="API rule"),
                ]
            )
        )

        result = config.get_path_instructions("src/api/users.py")
        assert len(result) == 2


class TestProfileBehavior:
    """Test profile affects thresholds."""

    def test_chill_profile(self) -> None:
        config = ReviewerConfig(reviews=ReviewsConfig(profile=ReviewProfile.CHILL))

        assert config.get_threshold() == 0.85
        assert config.get_max_comments() == 5

    def test_strict_profile(self) -> None:
        config = ReviewerConfig(reviews=ReviewsConfig(profile=ReviewProfile.STRICT))

        assert config.get_threshold() == 0.6
        assert config.get_max_comments() == 20

    def test_default_profile(self) -> None:
        config = ReviewerConfig()

        assert config.get_threshold() == 0.7
        assert config.get_max_comments() == 10

    def test_explicit_overrides(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(
                profile=ReviewProfile.CHILL,
                confidence_threshold=0.5,
            )
        )

        # Explicit wins over profile
        assert config.get_threshold() == 0.5


class TestAutoReview:
    """Test auto-review logic."""

    def test_disabled(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(auto_review=AutoReviewConfig(enabled=False))
        )

        assert (
            config.should_auto_review(
                title="feat: new",
                author="dev",
                base_branch="main",
                is_draft=False,
            )
            is False
        )

    def test_skip_keyword(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(auto_review=AutoReviewConfig(skip_keywords=["[WIP]"]))
        )

        assert (
            config.should_auto_review(
                title="[WIP] work in progress",
                author="dev",
                base_branch="main",
                is_draft=False,
            )
            is False
        )

    def test_skip_draft(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(auto_review=AutoReviewConfig(drafts=False))
        )

        assert (
            config.should_auto_review(
                title="feat: new",
                author="dev",
                base_branch="main",
                is_draft=True,
            )
            is False
        )

    def test_allow_draft(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(auto_review=AutoReviewConfig(drafts=True))
        )

        assert (
            config.should_auto_review(
                title="feat: new",
                author="dev",
                base_branch="main",
                is_draft=True,
            )
            is True
        )

    def test_ignore_authors(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(
                auto_review=AutoReviewConfig(ignore_authors=["bot", "dependabot"])
            )
        )

        assert (
            config.should_auto_review(
                title="chore: update deps",
                author="dependabot",
                base_branch="main",
                is_draft=False,
            )
            is False
        )

    def test_base_branch_filter(self) -> None:
        config = ReviewerConfig(
            reviews=ReviewsConfig(
                auto_review=AutoReviewConfig(base_branches=["main", "develop"])
            )
        )

        assert (
            config.should_auto_review(
                title="feat: new",
                author="dev",
                base_branch="main",
                is_draft=False,
            )
            is True
        )

        assert (
            config.should_auto_review(
                title="feat: new",
                author="dev",
                base_branch="feature/test",
                is_draft=False,
            )
            is False
        )


class TestAgentEnabled:
    """Test agent enable/disable."""

    def test_default_agents_enabled(self) -> None:
        config = ReviewerConfig()

        assert config.is_agent_enabled("security") is True
        assert config.is_agent_enabled("logic") is True
        assert config.is_agent_enabled("style") is True

    def test_custom_agents(self) -> None:
        config = ReviewerConfig(reviews=ReviewsConfig(agents=["security"]))

        assert config.is_agent_enabled("security") is True
        assert config.is_agent_enabled("logic") is False
        assert config.is_agent_enabled("style") is False
