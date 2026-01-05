# 07 - Testing Guide

## 🧪 Testing Strategy

### Test Levels

```
┌─────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                    ┌─────────┐                               │
│                    │   E2E   │  1-2 tests                    │
│                   ─┴─────────┴─                              │
│                  ┌─────────────┐                             │
│                  │ Integration │  5-10 tests                 │
│                 ─┴─────────────┴─                            │
│                ┌─────────────────┐                           │
│                │    Unit Tests   │  20+ tests                │
│               ─┴─────────────────┴─                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Unit Tests

### Test Models

```python
# tests/core/config/test_models.py

import pytest
from src.core.config.models import (
    ReviewerConfig,
    ReviewProfile,
    PathInstruction,
)


class TestReviewerConfig:
    """Test ReviewerConfig model."""

    def test_default_values(self):
        """Default config should have sane values."""
        config = ReviewerConfig()

        assert config.language == "en"
        assert config.reviews.profile == ReviewProfile.DEFAULT
        assert config.reviews.confidence_threshold == 0.7
        assert config.reviews.agents == ["security", "logic", "style"]
        assert config.ignore == []
        assert config.chat.enabled is True

    def test_parse_minimal_yaml(self):
        """Should parse minimal YAML config."""
        data = {"language": "vi"}
        config = ReviewerConfig(**data)

        assert config.language == "vi"
        assert config.reviews.profile == ReviewProfile.DEFAULT  # default

    def test_parse_full_yaml(self):
        """Should parse full YAML config."""
        data = {
            "language": "vi",
            "reviews": {
                "profile": "strict",
                "confidence_threshold": 0.6,
                "agents": ["security"],
                "path_instructions": [
                    {"path": "src/api/**", "instructions": "Check auth"}
                ],
            },
            "ignore": ["**/migrations/**"],
        }
        config = ReviewerConfig(**data)

        assert config.language == "vi"
        assert config.reviews.profile == ReviewProfile.STRICT
        assert config.reviews.confidence_threshold == 0.6
        assert config.reviews.agents == ["security"]
        assert len(config.reviews.path_instructions) == 1
        assert len(config.ignore) == 1

    def test_invalid_agent_raises(self):
        """Invalid agent name should raise."""
        with pytest.raises(ValueError, match="Invalid agent"):
            ReviewerConfig(**{
                "reviews": {"agents": ["invalid_agent"]}
            })

    def test_invalid_threshold_raises(self):
        """Threshold outside 0-1 should raise."""
        with pytest.raises(ValueError):
            ReviewerConfig(**{
                "reviews": {"confidence_threshold": 1.5}
            })

    def test_extra_fields_ignored(self):
        """Unknown fields should be ignored."""
        data = {
            "language": "en",
            "future_field": "value",
            "reviews": {
                "unknown_nested": True,
            },
        }
        config = ReviewerConfig(**data)
        assert config.language == "en"


class TestShouldIgnore:
    """Test should_ignore method."""

    def test_simple_pattern(self):
        config = ReviewerConfig(ignore=["*.lock"])

        assert config.should_ignore("poetry.lock") is True
        assert config.should_ignore("package-lock.json") is False

    def test_directory_pattern(self):
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
        assert config.should_ignore("src/__pycache__/bar.pyc") is True
        assert config.should_ignore("yarn.lock") is True
        assert config.should_ignore("src/main.py") is False


class TestPathInstructions:
    """Test get_path_instructions method."""

    def test_matching_pattern(self):
        config = ReviewerConfig(
            reviews={
                "path_instructions": [
                    {"path": "src/api/**", "instructions": "Check auth"},
                ]
            }
        )

        instructions = config.get_path_instructions("src/api/users.py")
        assert "Check auth" in instructions

    def test_no_match(self):
        config = ReviewerConfig(
            reviews={
                "path_instructions": [
                    {"path": "src/api/**", "instructions": "Check auth"},
                ]
            }
        )

        instructions = config.get_path_instructions("tests/test_foo.py")
        assert instructions == []

    def test_multiple_matches(self):
        config = ReviewerConfig(
            reviews={
                "path_instructions": [
                    {"path": "src/**", "instructions": "General rule"},
                    {"path": "src/api/**", "instructions": "API rule"},
                ]
            }
        )

        instructions = config.get_path_instructions("src/api/users.py")
        assert len(instructions) == 2
        assert "General rule" in instructions
        assert "API rule" in instructions


class TestProfileThresholds:
    """Test profile affects thresholds."""

    def test_chill_profile(self):
        config = ReviewerConfig(reviews={"profile": "chill"})

        assert config.get_threshold() == 0.85
        assert config.get_max_comments() == 5

    def test_strict_profile(self):
        config = ReviewerConfig(reviews={"profile": "strict"})

        assert config.get_threshold() == 0.6
        assert config.get_max_comments() == 20

    def test_explicit_overrides_profile(self):
        config = ReviewerConfig(
            reviews={
                "profile": "chill",
                "confidence_threshold": 0.5,
            }
        )

        # Explicit value wins
        assert config.get_threshold() == 0.5


class TestShouldAutoReview:
    """Test auto-review logic."""

    def test_disabled(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"enabled": False}}
        )

        assert config.should_auto_review(
            title="feat: new feature",
            author="dev",
            base_branch="main",
            is_draft=False,
        ) is False

    def test_skip_wip(self):
        config = ReviewerConfig(
            reviews={
                "auto_review": {"skip_keywords": ["[WIP]"]}
            }
        )

        assert config.should_auto_review(
            title="[WIP] feat: work in progress",
            author="dev",
            base_branch="main",
            is_draft=False,
        ) is False

    def test_skip_draft(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"drafts": False}}
        )

        assert config.should_auto_review(
            title="feat: new feature",
            author="dev",
            base_branch="main",
            is_draft=True,
        ) is False

    def test_allow_draft_when_enabled(self):
        config = ReviewerConfig(
            reviews={"auto_review": {"drafts": True}}
        )

        assert config.should_auto_review(
            title="feat: new feature",
            author="dev",
            base_branch="main",
            is_draft=True,
        ) is True
```

---

### Test Cache

```python
# tests/core/config/test_cache.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.config.cache import ConfigCache
from src.core.config.models import ReviewerConfig


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    return redis


@pytest.fixture
def cache(mock_redis):
    return ConfigCache(mock_redis)


class TestConfigCache:

    async def test_get_miss(self, cache, mock_redis):
        mock_redis.get.return_value = None

        result = await cache.get("owner/repo")

        assert result is None
        mock_redis.get.assert_called_once()

    async def test_get_hit(self, cache, mock_redis):
        config = ReviewerConfig(language="vi")
        mock_redis.get.return_value = config.model_dump_json()

        result = await cache.get("owner/repo")

        assert result is not None
        assert result.language == "vi"

    async def test_set(self, cache, mock_redis):
        config = ReviewerConfig(language="vi")

        await cache.set("owner/repo", config)

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "config:owner/repo" in call_args[0]

    async def test_delete(self, cache, mock_redis):
        await cache.delete("owner/repo")

        mock_redis.delete.assert_called_once_with("config:owner/repo")
```

---

### Test Service

```python
# tests/core/config/test_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.config.service import ConfigService
from src.core.config.models import ReviewerConfig


@pytest.fixture
def mock_github():
    return MagicMock()


@pytest.fixture
def mock_cache():
    return AsyncMock()


@pytest.fixture
def mock_repository():
    return AsyncMock()


@pytest.fixture
def service(mock_github, mock_cache, mock_repository):
    return ConfigService(mock_github, mock_cache, mock_repository)


class TestConfigService:

    async def test_cache_hit(self, service, mock_cache):
        """Should return cached config without loading."""
        cached = ReviewerConfig(language="vi")
        mock_cache.get.return_value = cached

        result = await service.get_config("owner", "repo")

        assert result.language == "vi"
        mock_cache.get.assert_called_once()

    async def test_load_from_github(self, service, mock_cache, mock_github):
        """Should load from GitHub when cache miss."""
        mock_cache.get.return_value = None

        # Mock loader
        service.loader.load_yaml = AsyncMock(return_value={"language": "ja"})

        result = await service.get_config("owner", "repo")

        assert result.language == "ja"
        mock_cache.set.assert_called_once()

    async def test_fallback_to_database(
        self, service, mock_cache, mock_repository
    ):
        """Should fallback to database when no YAML."""
        mock_cache.get.return_value = None
        service.loader.load_yaml = AsyncMock(return_value=None)

        db_config = ReviewerConfig(language="ko")
        mock_repository.get.return_value = db_config

        result = await service.get_config("owner", "repo")

        assert result.language == "ko"

    async def test_fallback_to_defaults(
        self, service, mock_cache, mock_repository
    ):
        """Should use defaults when nothing found."""
        mock_cache.get.return_value = None
        service.loader.load_yaml = AsyncMock(return_value=None)
        mock_repository.get.return_value = None

        result = await service.get_config("owner", "repo")

        assert result.language == "en"  # default
```

---

## 🔌 Integration Tests

```python
# tests/integration/test_config_integration.py

import pytest
import asyncio
from src.core.config import ConfigService, ReviewerConfig


@pytest.mark.integration
class TestConfigIntegration:
    """Integration tests with real services."""

    async def test_load_real_config(self, real_github, real_redis, real_db):
        """Test loading config from actual services."""
        service = ConfigService(
            github=real_github,
            cache=ConfigCache(real_redis),
            repository=ConfigRepository(real_db),
        )

        config = await service.get_config("test-owner", "test-repo")

        assert isinstance(config, ReviewerConfig)

    async def test_cache_persistence(self, real_redis):
        """Test that cache actually persists."""
        cache = ConfigCache(real_redis)
        config = ReviewerConfig(language="test")

        await cache.set("test/repo", config)
        result = await cache.get("test/repo")

        assert result is not None
        assert result.language == "test"

        # Cleanup
        await cache.delete("test/repo")
```

---

## ✅ Test Checklist

### Unit Tests

- [ ] `ReviewerConfig` default values
- [ ] `ReviewerConfig` YAML parsing
- [ ] `ReviewerConfig` validation errors
- [ ] `should_ignore()` pattern matching
- [ ] `get_path_instructions()` pattern matching
- [ ] `get_threshold()` profile behavior
- [ ] `should_auto_review()` all conditions
- [ ] `ConfigCache` get/set/delete
- [ ] `ConfigRepository` CRUD
- [ ] `ConfigService` resolution order

### Integration Tests

- [ ] Load config from real GitHub
- [ ] Cache round-trip with Redis
- [ ] Database persistence

### E2E Tests

- [ ] PR with `.reviewer.yaml` uses config
- [ ] PR without config uses defaults
- [ ] Ignore patterns filter files
- [ ] Path instructions in prompts

---

## 🏃 Running Tests

```bash
# Unit tests only
pytest tests/core/config/ -v

# With coverage
pytest tests/core/config/ --cov=src/core/config --cov-report=html

# Integration tests (requires services)
pytest tests/integration/ -v -m integration

# All tests
pytest -v
```
