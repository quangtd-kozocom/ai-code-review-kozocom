# Configuration System

## Overview

The AI Code Reviewer uses a layered configuration system that allows per-repository settings with graceful fallback to defaults. Configuration is resolved in the following priority order:

1. **Redis Cache** (5 minute TTL)
2. **.reviewer.yaml** file in repository
3. **Database** stored configuration
4. **Default values**

This design ensures that the system always returns a valid configuration, even if all external sources fail.

---

## .reviewer.yaml

Place a `.reviewer.yaml` file in the repository root to configure the reviewer. Alternative filenames are also supported: `.reviewer.yml`, `.ai-reviewer.yaml`, `.ai-reviewer.yml`.

### Complete Example

```yaml
# Response language (ISO 639-1 code)
language: "vi"

# Review settings
reviews:
  # Profile: chill, default, strict
  profile: "chill"

  # Active agents
  agents:
    - security
    - logic
    - style

  # LLM confidence threshold (0.0 - 1.0)
  confidence_threshold: 0.7

  # Max comments per file (1 - 50)
  max_comments_per_file: 10

  # Path-specific review instructions
  path_instructions:
    - path: "src/api/**"
      instructions: "Check authentication and authorization"
    - path: "src/tests/**"
      instructions: "Verify test coverage is adequate"

  # Auto-review trigger settings
  auto_review:
    enabled: true
    drafts: false
    skip_keywords: ["WIP", "draft", "RFC"]
    base_branches: ["main", "develop"]
    ignore_authors: ["bot", "dependabot", "github-actions"]

# File patterns to ignore
ignore:
  - "**/migrations/**"
  - "**/*.test.js"
  - "**/node_modules/**"
  - "**/.venv/**"

# Interactive chat settings
chat:
  enabled: true
  allowed_commands:
    - fix
    - explain
    - tests
    - help
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `language` | string | `"en"` | Response language code (ISO 639-1) |
| `reviews.profile` | enum | `"default"` | Review strictness: `chill`, `default`, `strict` |
| `reviews.agents` | list[str] | All agents | Active agents: `security`, `logic`, `style` |
| `reviews.confidence_threshold` | float | `0.7` | LLM confidence threshold (0.0 - 1.0) |
| `reviews.max_comments_per_file` | int | `10` | Maximum comments per file (1 - 50) |
| `reviews.auto_review.enabled` | bool | `true` | Enable automatic review on PR events |
| `reviews.auto_review.drafts` | bool | `false` | Review draft PRs |
| `reviews.auto_review.skip_keywords` | list[str] | `[]` | Skip PRs with these title keywords |
| `reviews.auto_review.base_branches` | list[str] | `[]` | Only review PRs targeting these branches |
| `reviews.auto_review.ignore_authors` | list[str] | `[]` | Skip PRs from these authors |
| `ignore` | list[str] | `[]` | Glob patterns for files to ignore |
| `chat.enabled` | bool | `true` | Enable interactive chat commands |
| `chat.allowed_commands` | list[str] | All commands | Available chat commands |

---

## Profile Defaults

Each profile defines baseline thresholds for comment generation. Explicit values in the config override these defaults.

| Profile | Confidence Threshold | Max Comments/File | Use Case |
|---------|---------------------|-------------------|----------|
| `chill` | 0.85 | 5 | Minimal feedback, focus on critical issues only |
| `default` | 0.70 | 10 | Balanced review for most projects |
| `strict` | 0.60 | 20 | Comprehensive review, lower confidence threshold |

### Profile Usage

```yaml
reviews:
  profile: "strict"  # Use strict defaults
  # confidence_threshold and max_comments_per_file will use strict defaults
  # but can be overridden explicitly:

  confidence_threshold: 0.75  # Override threshold
  max_comments_per_file: 15  # Override max comments
```

---

## Path Instructions

Path instructions allow you to specify custom review focus for specific file patterns. Uses glob matching with `**` for recursive matching.

### Examples

```yaml
reviews:
  path_instructions:
    # API endpoints - focus on security
    - path: "src/api/**/*.py"
      instructions: "Check for authentication, authorization, and input validation"

    # Database models - focus on data integrity
    - path: "**/models.py"
      instructions: "Verify proper constraints, indexes, and relationships"

    # Tests - focus on coverage and edge cases
    - path: "tests/**/*"
      instructions: "Ensure edge cases are covered and tests are meaningful"

    # Configuration files - be strict
    - path: "**/{Dockerfile,*.yml,*.yaml}"
      instructions: "Check for security vulnerabilities and best practices"
```

### Supported Glob Patterns

| Pattern | Matches | Example |
|---------|---------|---------|
| `*.py` | Single extension | `utils.py`, `models.py` |
| `**/*.py` | Recursive extension | `src/utils.py`, `src/sub/utils.py` |
| `src/api/**` | Directory and contents | `src/api/main.py`, `src/api/routes/users.py` |
| `**/models.py` | Any directory | `models.py`, `src/models.py`, `app/models.py` |

---

## Priority Resolution

The configuration resolution follows a specific flow to ensure a valid configuration is always returned:

```
get_config(owner, repo, ref)
    |
    +-> Check Redis Cache (5 min TTL)
    |       |
    |       +-> HIT: Return cached config
    |       |
    |       +-> MISS: Continue
    |
    +-> Load from .reviewer.yaml
    |       |
    |       +-> Found: Validate and use
    |       |
    |       +-> Not Found / Error: Continue
    |
    +-> Load from Database
    |       |
    |       +-> Found: Use database config
    |       |
    |       +-> Not Found / Error: Continue
    |
    +-> Use Default Values
    |
    +-> Cache result and return
```

### Cache Key Format

```
config:{owner}:{repo}
# Example: config:owner-name:repository-name
```

### Cache Invalidation

Cache is automatically invalidated when:
1. Config is saved via `save_config()`
2. Config is deleted via `delete_config()`
3. Cache TTL expires (5 minutes)

Manual invalidation:
```python
await service.invalidate_cache(owner, repo)
```

---

## API Reference

### ConfigService

The main service for loading and managing repository configuration.

```python
from src.core.config import ReviewerConfig, ConfigService, create_config_service

# Factory function to create service with optional dependencies
service = await create_config_service(github)
```

#### Methods

##### `get_config(owner: str, repo: str, ref: str = "HEAD") -> ReviewerConfig`

Get configuration for a repository.

```python
config = await service.get_config("owner", "repo-name")
print(config.language)
print(config.reviews.profile)
```

**Parameters:**
- `owner`: Repository owner (user or organization)
- `repo`: Repository name
- `ref`: Git reference (branch, tag, or SHA)

**Returns:** `ReviewerConfig` - Always returns a valid config

---

##### `save_config(owner: str, repo: str, config: ReviewerConfig, created_by: str | None = None) -> ConfigModel | None`

Save configuration to database.

```python
from src.core.config import ReviewerConfig

config = ReviewerConfig(
    language="vi",
    reviews={"profile": "strict"}
)
saved = await service.save_config("owner", "repo", config, created_by="user")
```

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `config`: ReviewerConfig to save
- `created_by`: User who saved the config (optional)

**Returns:** `ConfigModel` or `None` (if database not configured)

---

##### `delete_config(owner: str, repo: str) -> bool`

Delete stored configuration.

```python
deleted = await service.delete_config("owner", "repo")
```

**Returns:** `True` if deleted, `False` if not found

---

##### `invalidate_cache(owner: str, repo: str) -> None`

Invalidate cached configuration.

```python
await service.invalidate_cache("owner", "repo")
```

---

### ReviewerConfig Methods

The resolved `ReviewerConfig` object provides helper methods:

```python
config = await service.get_config(owner, repo)

# Get effective threshold
threshold = config.get_threshold()  # Uses profile default or explicit value

# Get effective max comments
max_comments = config.get_max_comments()

# Check if file should be ignored
should_ignore = config.should_ignore("src/migration.py")  # True

# Get matching instructions for file
instructions = config.get_path_instructions("src/api/main.py")
# Returns: ["Check authentication", "Validate inputs"]

# Check if PR should be auto-reviewed
should_review = config.should_auto_review(
    title="feat: add new endpoint",
    author="developer",
    base_branch="main",
    is_draft=False
)

# Check if agent is enabled
is_logic_enabled = config.is_agent_enabled("logic")
```

---

### ConfigLoader

Low-level loader for .reviewer.yaml files.

```python
from src.core.config import ConfigLoader

loader = ConfigLoader(github)

# Load with exception handling
config_dict = await loader.load_with_fallback("owner", "repo", "main")

# Load and raise on errors
config_dict = await loader.load("owner", "repo", "main")
```

---

### ConfigRepository

Database operations for configuration CRUD.

```python
from src.core.config import ConfigRepository

repository = ConfigRepository(session)

# Get config
config = await repository.get("owner", "repo")

# Create config
new_config = await repository.create("owner", "repo", config_data)

# Update config
updated = await repository.update("owner", "repo", config_data)

# Upsert (create or update)
upserted = await repository.upsert("owner", "repo", config_data)

# Delete config
deleted = await repository.delete("owner", "repo")

# List by owner
configs = await repository.list_by_owner("owner")
```

---

### Cache Implementations

```python
from src.core.config import ConfigCache, NullCache

# Redis-backed cache
redis_cache = ConfigCache(redis_client, ttl=300)  # 5 min TTL

# No-op cache (when Redis unavailable)
null_cache = NullCache()
```

---

## Error Handling

The configuration system uses specific exception types:

```python
from src.core.config import (
    ConfigError,
    ConfigLoadError,
    ConfigValidationError,
    ConfigCacheError,
)

try:
    config = await service.get_config(owner, repo)
except ConfigLoadError as e:
    # YAML file fetch/parse failed
    print(f"Load error: {e}")
except ConfigValidationError as e:
    # YAML content invalid against schema
    print(f"Validation error: {e}")
except ConfigCacheError as e:
    # Cache operation failed
    print(f"Cache error: {e}")
except ConfigError as e:
    # General configuration error
    print(f"Config error: {e}")
```

---

## Best Practices

1. **Start with defaults**: Use the default profile initially, then tune based on team feedback.

2. **Use path instructions**: Add specific instructions for security-critical code paths.

3. **Ignore test patterns**: Add test file patterns to ignore list to reduce noise.

4. **Configure auto-review**: Set appropriate `skip_keywords` and `base_branches` to avoid reviewing irrelevant PRs.

5. **Cache warming**: For high-traffic repositories, pre-warm the cache by calling `get_config()` during startup.

6. **Version control config**: Keep `.reviewer.yaml` in version control to track configuration changes.
