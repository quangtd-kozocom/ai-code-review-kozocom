# src/core/services/config_service.py
"""
Config service with Redis cache + DB fallback.
Auto-creates default config for new repos.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import structlog

from ..database import get_session
from ..models import RepoConfig
from ..redis import get_redis

if TYPE_CHECKING:
    from redis.asyncio import Redis

log = structlog.get_logger()

CACHE_TTL = 3600  # 1 hour
CACHE_PREFIX = "repo_config:"


class ConfigService:
    def __init__(self, redis: "Redis | None" = None):
        self.redis = redis

    async def get_config(self, owner: str, repo: str, installation_id: int = 0) -> RepoConfig:
        """Get config from cache or DB. Auto-creates if not exists."""
        cache_key = f"{CACHE_PREFIX}{owner}/{repo}"

        # Try cache first
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    log.debug("config.cache_hit", owner=owner, repo=repo)
                    return RepoConfig.model_validate_json(cached)
            except Exception as e:
                log.warning("config.cache_error", error=str(e))

        # Query/create from DB
        config = await self._get_or_create_from_db(owner, repo, installation_id)

        # Cache it
        if self.redis:
            try:
                await self.redis.setex(cache_key, CACHE_TTL, config.model_dump_json())
                log.debug("config.cached", owner=owner, repo=repo)
            except Exception as e:
                log.warning("config.cache_set_error", error=str(e))

        return config

    async def invalidate(self, owner: str, repo: str) -> None:
        """Invalidate cached config."""
        if not self.redis:
            return
        cache_key = f"{CACHE_PREFIX}{owner}/{repo}"
        try:
            await self.redis.delete(cache_key)
            log.info("config.invalidated", owner=owner, repo=repo)
        except Exception as e:
            log.warning("config.invalidate_error", error=str(e))

    async def _get_or_create_from_db(self, owner: str, repo: str, installation_id: int) -> RepoConfig:
        """Get or create config from database."""
        from sqlalchemy import select
        from ..models import Repository

        async with get_session() as session:
            # Get or create repository
            result = await session.execute(
                select(Repository).where(Repository.owner == owner, Repository.name == repo)
            )
            repository = result.scalars().first()

            if not repository:
                repository = Repository(owner=owner, name=repo, installation_id=installation_id)
                session.add(repository)
                await session.flush()
                log.info("config.repo_created", owner=owner, repo=repo)

            # Get or create config
            result = await session.execute(
                select(RepoConfig).where(RepoConfig.repository_id == repository.id)
            )
            config = result.scalars().first()

            if not config:
                config = RepoConfig(repository_id=repository.id)
                session.add(config)
                await session.flush()
                log.info("config.created", owner=owner, repo=repo)

            return config


# Singleton instance
_config_service: ConfigService | None = None


async def get_config_service() -> ConfigService:
    """Get or create config service singleton."""
    global _config_service
    if _config_service is None:
        redis = await get_redis()
        _config_service = ConfigService(redis)
    return _config_service
