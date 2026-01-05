# Configuration System - Testing Guide

Hướng dẫn chạy và viết tests cho Configuration System.

## Quick Start

```bash
# Chạy tất cả config tests
uv run pytest tests/core/config/ -v

# Chạy với coverage
uv run pytest tests/core/config/ --cov=src/core/config --cov-report=term-missing
```

## Test Structure

```
tests/core/config/
├── __init__.py
├── test_schemas.py      # Schema validation tests
├── test_cache.py        # Redis cache tests
└── test_service.py      # ConfigService tests
```

## Test Categories

### 1. Schema Tests (`test_schemas.py`)

#### Default Values
```python
def test_default_values(self) -> None:
    """Config với giá trị mặc định."""
    config = ReviewerConfig()
    assert config.language == "en"
    assert config.reviews.profile == ReviewProfile.DEFAULT
    assert config.reviews.agents == ["security", "logic", "style"]
```

#### YAML Parsing
```python
def test_parse_yaml_dict(self) -> None:
    """Parse config từ YAML dict."""
    data = {
        "language": "vi",
        "reviews": {"profile": "strict"},
        "ignore": ["*.lock"],
    }
    config = ReviewerConfig.model_validate(data)
    assert config.language == "vi"
```

#### Validation Errors
```python
def test_invalid_agent_raises(self) -> None:
    """Invalid agent name phải raise error."""
    with pytest.raises(ValidationError):
        ReviewerConfig(
            reviews=ReviewsConfig(agents=["invalid_agent"])
        )
```

#### Glob Pattern Matching
```python
def test_recursive_pattern(self) -> None:
    """Test ** pattern matching."""
    config = ReviewerConfig(ignore=["**/migrations/**"])
    
    assert config.should_ignore("src/migrations/001.py") is True
    assert config.should_ignore("migrations/init.py") is True
    assert config.should_ignore("src/main.py") is False
```

#### Profile Behaviors
```python
def test_chill_profile(self) -> None:
    """Chill profile có threshold cao, ít comments."""
    config = ReviewerConfig(
        reviews=ReviewsConfig(profile=ReviewProfile.CHILL)
    )
    assert config.get_threshold() == 0.85
    assert config.get_max_comments() == 5
```

### 2. Cache Tests (`test_cache.py`)

#### Basic Operations
```python
async def test_get_cache_hit(self) -> None:
    """Get trả về config khi có trong cache."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"language": "vi"}'
    
    cache = ConfigCache(mock_redis, ttl=300)
    result = await cache.get("config:owner:repo")
    
    assert result is not None
    assert result.language == "vi"
```

#### Error Handling
```python
async def test_get_handles_error(self) -> None:
    """Cache errors không raise, trả về None."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis error")
    
    cache = ConfigCache(mock_redis, ttl=300)
    result = await cache.get("config:owner:repo")
    
    assert result is None  # Graceful degradation
```

### 3. Service Tests (`test_service.py`)

#### Config Resolution
```python
async def test_cache_hit(self) -> None:
    """Cache hit trả về cached config."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = ReviewerConfig(language="cached")
    
    service = ConfigService(
        cache=mock_cache,
        loader=AsyncMock(),
        repository=AsyncMock(),
    )
    
    result = await service.get_config("owner", "repo")
    assert result.language == "cached"
```

```python
async def test_load_from_github(self) -> None:
    """Cache miss → load từ GitHub."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None  # Miss
    
    mock_loader = AsyncMock()
    mock_loader.load.return_value = ReviewerConfig(language="github")
    
    service = ConfigService(cache=mock_cache, loader=mock_loader)
    result = await service.get_config("owner", "repo")
    
    assert result.language == "github"
    mock_cache.set.assert_called_once()  # Cached
```

```python
async def test_fallback_to_defaults(self) -> None:
    """All sources fail → return defaults."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    
    mock_loader = AsyncMock()
    mock_loader.load.return_value = None
    
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None
    
    service = ConfigService(
        cache=mock_cache,
        loader=mock_loader,
        repository=mock_repo,
    )
    
    result = await service.get_config("owner", "repo")
    assert result.language == "en"  # Default
```

## Running Specific Tests

```bash
# Run by test class
uv run pytest tests/core/config/test_schemas.py::TestReviewerConfig -v

# Run by test name
uv run pytest tests/core/config/ -k "test_recursive_pattern" -v

# Run all glob pattern tests
uv run pytest tests/core/config/ -k "ignore" -v
```

## Coverage Report

```bash
# Terminal report
uv run pytest tests/core/config/ --cov=src/core/config --cov-report=term-missing

# HTML report
uv run pytest tests/core/config/ --cov=src/core/config --cov-report=html
open htmlcov/index.html
```

Expected coverage: > 90%

## Writing New Tests

### Test Template

```python
"""Tests for [component]."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.config import ReviewerConfig, ReviewsConfig


class TestFeatureName:
    """Test group for feature."""

    def test_expected_behavior(self) -> None:
        """Describe what this tests."""
        # Arrange
        config = ReviewerConfig(...)
        
        # Act
        result = config.some_method()
        
        # Assert
        assert result == expected

    def test_edge_case(self) -> None:
        """Test edge case handling."""
        ...

    def test_error_handling(self) -> None:
        """Test error scenarios."""
        with pytest.raises(ExpectedError):
            ...
```

### Async Test Template

```python
import pytest

class TestAsyncFeature:
    """Async tests require pytest-asyncio."""

    @pytest.mark.asyncio
    async def test_async_operation(self) -> None:
        """Test async method."""
        mock_dep = AsyncMock()
        mock_dep.method.return_value = "result"
        
        service = Service(dependency=mock_dep)
        result = await service.async_method()
        
        assert result == "expected"
        mock_dep.method.assert_awaited_once()
```

## Test Data Fixtures

### Sample YAML Config

```python
@pytest.fixture
def sample_yaml_config() -> dict:
    """Sample config as parsed YAML."""
    return {
        "language": "vi",
        "reviews": {
            "profile": "strict",
            "agents": ["security", "logic"],
            "path_instructions": [
                {"path": "src/**", "instructions": "Review carefully"},
            ],
        },
        "ignore": ["**/*.lock", "**/node_modules/**"],
    }
```

### Mock Redis

```python
@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = 1
    redis.exists.return_value = 0
    return redis
```

## Debugging Failed Tests

### Verbose Output

```bash
uv run pytest tests/core/config/ -v --tb=long
```

### Print Statements

```bash
uv run pytest tests/core/config/ -v -s
```

### Stop on First Failure

```bash
uv run pytest tests/core/config/ -x
```

### Debug with pdb

```bash
uv run pytest tests/core/config/ --pdb
```

## CI Integration

### GitHub Actions

```yaml
- name: Run Config Tests
  run: |
    uv sync
    uv run pytest tests/core/config/ -v --cov=src/core/config
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-config
        name: pytest config
        entry: uv run pytest tests/core/config/ -q
        language: system
        pass_filenames: false
        always_run: true
```
