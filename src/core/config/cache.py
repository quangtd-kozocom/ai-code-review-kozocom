"""
Redis cache for configurations using redis-py.

Features:
- Async operations with redis-py
- JSON serialization
- TTL-based expiration
- Graceful error handling
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis

from ...app.config import get_settings

log = structlog.get_logger()

# Cache settings
CACHE_PREFIX = "config"


class ConfigCache:
    """
    Redis cache for repository configurations.

    Uses redis-py async client with hiredis for performance.
    """

    def __init__(self, redis: Redis) -> None:
        """
        Initialize cache with Redis connection.

        Args:
            redis: Async Redis client.
        """
        self.redis = redis
        self.prefix = CACHE_PREFIX
        self.ttl = get_settings().CONFIG_CACHE_TTL

    def _key(self, owner: str, repo: str) -> str:
        """Build cache key."""
        return f"{self.prefix}:{owner}:{repo}"

    async def get(self, owner: str, repo: str) -> dict[str, Any] | None:
        """
        Get cached config.

        Args:
            owner: Repository owner.
            repo: Repository name.

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
        config: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """
        Cache config.

        Args:
            owner: Repository owner.
            repo: Repository name.
            config: Config dict to cache.
            ttl: Optional custom TTL in seconds.

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
            owner: Repository owner.
            repo: Repository name.

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
