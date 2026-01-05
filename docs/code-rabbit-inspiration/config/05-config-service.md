# 05 - Config Service (SQLModel + Redis)

## 🎯 Overview

`ConfigService` orchestrates config loading với:

- **SQLModel** repository cho database
- **redis-py** cho caching
- **ConfigLoader** cho GitHub

---

## 📦 Cache Layer (redis-py)

### File: `src/core/config/cache.py`

```python
"""
Redis cache for configurations using redis-py.

Features:
- Async operations with redis-py
- JSON serialization
- TTL-based expiration
- Graceful error handling
"""

import json
from typing import Optional

import structlog
from redis.asyncio import Redis

log = structlog.get_logger()

# Cache settings
CACHE_PREFIX = "config"
CACHE_TTL = 300  # 5 minutes


class ConfigCache:
    """
    Redis cache for repository configurations.

    Uses redis-py async client with hiredis for performance.
    """

    def __init__(self, redis: Redis):
        """
        Initialize cache with Redis connection.

        Args:
            redis: Async Redis client
        """
        self.redis = redis
        self.prefix = CACHE_PREFIX
        self.ttl = CACHE_TTL

    def _key(self, owner: str, repo: str) -> str:
        """Build cache key."""
        return f"{self.prefix}:{owner}:{repo}"

    async def get(self, owner: str, repo: str) -> Optional[dict]:
        """
        Get cached config.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Config dict if cached and valid, None otherwise.
        """
        key = self._key(owner, repo)

        try:
            data = await self.redis.get(key)
            if data:
                log.debug("Cache hit", key=key)
                return json.loads(data)
            log.debug("Cache miss", key=key)
            return None
        except Exception as e:
            log.warning("Cache get error", key=key, error=str(e))
            return None

    async def set(
        self,
        owner: str,
        repo: str,
        config: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache config.

        Args:
            owner: Repository owner
            repo: Repository name
            config: Config dict to cache
            ttl: Optional custom TTL in seconds

        Returns:
            True if cached successfully.
        """
        key = self._key(owner, repo)
        expire = ttl or self.ttl

        try:
            await self.redis.set(
                key,
                json.dumps(config),
                ex=expire,
            )
            log.debug("Cache set", key=key, ttl=expire)
            return True
        except Exception as e:
            log.warning("Cache set error", key=key, error=str(e))
            return False

    async def delete(self, owner: str, repo: str) -> bool:
        """
        Delete cached config.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if deleted.
        """
        key = self._key(owner, repo)

        try:
            await self.redis.delete(key)
            log.debug("Cache deleted", key=key)
            return True
        except Exception as e:
            log.warning("Cache delete error", key=key, error=str(e))
            return False

    async def exists(self, owner: str, repo: str) -> bool:
        """Check if config is cached."""
        key = self._key(owner, repo)
        try:
            return await self.redis.exists(key) > 0
        except Exception:
            return False
```

---

## 📦 Redis Connection

### File: `src/core/redis.py`

```python
"""
Redis connection management.

Uses redis-py with hiredis for optimal performance.
"""

from typing import Optional

import structlog
from redis.asyncio import Redis, from_url

from ..app.config import get_settings

log = structlog.get_logger()

# Global connection
_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    """
    Get or create Redis connection.

    Returns:
        Async Redis client.
    """
    global _redis

    if _redis is None:
        settings = get_settings()

        if not settings.UPSTASH_REDIS_URL:
            raise RuntimeError("UPSTASH_REDIS_URL not configured")

        _redis = from_url(
            settings.UPSTASH_REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        log.info("Redis connection created")

    return _redis


async def close_redis() -> None:
    """Close Redis connection on shutdown."""
    global _redis

    if _redis:
        await _redis.close()
        _redis = None
        log.info("Redis connection closed")
```

---

## 📦 YAML Loader

### File: `src/core/config/loader.py`

```python
"""
Load configuration from GitHub repository.
"""

from typing import Any, Optional, TYPE_CHECKING

import structlog
import yaml

if TYPE_CHECKING:
    from ...app.services.github import GitHubService

log = structlog.get_logger()

CONFIG_FILENAME = ".reviewer.yaml"


class ConfigLoader:
    """
    Load .reviewer.yaml from GitHub repository.
    """

    def __init__(self, github: "GitHubService"):
        self.github = github

    async def load(
        self,
        owner: str,
        repo: str,
        ref: str = "HEAD",
    ) -> Optional[dict[str, Any]]:
        """
        Load and parse .reviewer.yaml from repository.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git reference (branch/commit/tag)

        Returns:
            Parsed config dict, or None if file doesn't exist.
        """
        try:
            content = await self.github.get_file_raw(
                owner, repo, CONFIG_FILENAME, ref
            )

            if content is None:
                log.debug(
                    "No config file found",
                    owner=owner,
                    repo=repo,
                    file=CONFIG_FILENAME,
                )
                return None

            # Parse YAML
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                log.warning(
                    "Config file is not a valid dict",
                    owner=owner,
                    repo=repo,
                )
                return None

            log.info(
                "Config loaded from repository",
                owner=owner,
                repo=repo,
            )
            return data

        except yaml.YAMLError as e:
            log.warning(
                "Invalid YAML in config file",
                owner=owner,
                repo=repo,
                error=str(e),
            )
            return None
        except Exception as e:
            log.warning(
                "Failed to load config from GitHub",
                owner=owner,
                repo=repo,
                error=str(e),
            )
            return None
```

---

## 📦 Config Service

### File: `src/core/config/service.py`

```python
"""
Configuration service - main entry point.

Orchestrates: Cache → GitHub → Database → Defaults
"""

from typing import Optional, TYPE_CHECKING

import structlog

from .models import ConfigModel
from .schemas import ReviewerConfig
from .repository import ConfigRepository
from .cache import ConfigCache
from .loader import ConfigLoader

if TYPE_CHECKING:
    from ...app.services.github import GitHubService

log = structlog.get_logger()


class ConfigService:
    """
    Service for loading and managing repository configuration.

    Resolution order:
    1. Redis cache (5 min TTL)
    2. .reviewer.yaml from GitHub
    3. Database stored config
    4. Default values

    Usage:
        service = ConfigService(github, cache, repository)
        config = await service.get_config("owner", "repo")
    """

    def __init__(
        self,
        github: "GitHubService",
        cache: ConfigCache,
        repository: ConfigRepository,
    ):
        self.github = github
        self.cache = cache
        self.repository = repository
        self.loader = ConfigLoader(github)

    async def get_config(
        self,
        owner: str,
        repo: str,
        ref: str = "HEAD",
    ) -> ReviewerConfig:
        """
        Get configuration for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git ref to read config from

        Returns:
            ReviewerConfig with resolved settings.
        """
        # 1. Check cache
        cached = await self.cache.get(owner, repo)
        if cached is not None:
            log.debug("Using cached config", owner=owner, repo=repo)
            return ReviewerConfig(**cached)

        # 2. Try loading from .reviewer.yaml
        config_dict = await self.loader.load(owner, repo, ref)

        # 3. Fallback to database
        if config_dict is None:
            config_dict = await self._load_from_db(owner, repo)

        # 4. Fallback to defaults
        if config_dict is None:
            log.info("Using default config", owner=owner, repo=repo)
            config_dict = {}

        # Validate through Pydantic
        config = ReviewerConfig(**config_dict)

        # Cache the result
        await self.cache.set(owner, repo, config.model_dump())

        return config

    async def _load_from_db(
        self,
        owner: str,
        repo: str,
    ) -> Optional[dict]:
        """Load config from database."""
        try:
            db_config = await self.repository.get(owner, repo)
            if db_config:
                log.info("Loaded config from database", owner=owner, repo=repo)
                return db_config.config_data
        except Exception as e:
            log.warning(
                "Failed to load from database",
                owner=owner,
                repo=repo,
                error=str(e),
            )
        return None

    async def save_config(
        self,
        owner: str,
        repo: str,
        config: ReviewerConfig,
        created_by: Optional[str] = None,
    ) -> ConfigModel:
        """
        Save config to database.

        Use for setting defaults via API.

        Args:
            owner: Repository owner
            repo: Repository name
            config: Config to save
            created_by: Username making the change

        Returns:
            Saved ConfigModel.
        """
        # Upsert to database
        db_config = await self.repository.upsert(
            owner=owner,
            repo=repo,
            config_data=config.model_dump(),
            updated_by=created_by,
        )

        # Invalidate cache
        await self.cache.delete(owner, repo)

        log.info("Config saved", owner=owner, repo=repo)
        return db_config

    async def delete_config(self, owner: str, repo: str) -> bool:
        """
        Delete stored config.

        Returns:
            True if deleted.
        """
        deleted = await self.repository.delete(owner, repo)
        await self.cache.delete(owner, repo)
        return deleted

    async def invalidate_cache(self, owner: str, repo: str) -> None:
        """Invalidate cached config."""
        await self.cache.delete(owner, repo)
        log.debug("Cache invalidated", owner=owner, repo=repo)
```

---

## 📦 Factory Function

### File: `src/core/config/factory.py`

```python
"""
Factory for creating ConfigService with dependencies.
"""

from typing import TYPE_CHECKING

from .service import ConfigService
from .cache import ConfigCache
from .repository import ConfigRepository
from ..database import get_session
from ..redis import get_redis

if TYPE_CHECKING:
    from ...app.services.github import GitHubService


async def create_config_service(
    github: "GitHubService",
) -> ConfigService:
    """
    Create ConfigService with all dependencies.

    Usage:
        service = await create_config_service(github)
        config = await service.get_config("owner", "repo")
    """
    # Get connections
    redis = await get_redis()

    # Create components
    cache = ConfigCache(redis)

    # For repository, we need a session context
    async with get_session() as session:
        repository = ConfigRepository(session)

        service = ConfigService(
            github=github,
            cache=cache,
            repository=repository,
        )

        return service
```

---

## 📦 Module Exports

### File: `src/core/config/__init__.py`

```python
"""
Configuration module.

Usage:
    from src.core.config import ConfigService, ReviewerConfig
    from src.core.config import create_config_service
"""

from .schemas import (
    ReviewerConfig,
    ReviewProfile,
    PathInstruction,
    ReviewsConfig,
    AutoReviewConfig,
    ChatConfig,
)
from .models import ConfigModel, ConfigCreate, ConfigUpdate, ConfigRead
from .service import ConfigService
from .cache import ConfigCache
from .repository import ConfigRepository
from .loader import ConfigLoader
from .factory import create_config_service

__all__ = [
    # Schemas (Pydantic)
    "ReviewerConfig",
    "ReviewProfile",
    "PathInstruction",
    "ReviewsConfig",
    "AutoReviewConfig",
    "ChatConfig",
    # Models (SQLModel)
    "ConfigModel",
    "ConfigCreate",
    "ConfigUpdate",
    "ConfigRead",
    # Services
    "ConfigService",
    "ConfigCache",
    "ConfigRepository",
    "ConfigLoader",
    # Factory
    "create_config_service",
]
```

---

## ✅ Key Design Decisions

1. **Separation of Models**

   - `models.py` → SQLModel (database)
   - `schemas.py` → Pure Pydantic (validation/API)

2. **redis-py over Redis-OM**

   - Simpler for caching
   - No need for complex queries
   - Less overhead

3. **Factory Pattern**

   - Clean dependency creation
   - Easy to test with mocks

4. **Graceful Degradation**
   - Each layer can fail independently
   - Always returns valid config
