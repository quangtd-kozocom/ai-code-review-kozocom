"""
Configuration service - main entry point.

Orchestrates: Cache → GitHub → Database → Defaults
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from .cache import ConfigCache
from .loader import ConfigLoader
from .models import ConfigModel
from .repository import ConfigRepository
from .schemas import ReviewerConfig

if TYPE_CHECKING:
    from ...app.services.github import GitHubService

log = structlog.get_logger()


class ConfigService:
    """Service for loading and managing repository configuration."""

    def __init__(
        self,
        github: GitHubService,
        cache: ConfigCache | None = None,
        repository: ConfigRepository | None = None,
    ) -> None:
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
        """Get config: cache → GitHub → database → defaults."""
        if self.cache:
            try:
                cached = await self.cache.get(owner, repo)
                if cached is not None:
                    log.debug("Using cached config", owner=owner, repo=repo)
                    return ReviewerConfig(**cached)
            except Exception as e:
                log.warning("Cache read failed", error=str(e))

        config_dict = await self.loader.load(owner, repo, ref)

        if config_dict is None:
            config_dict = await self._load_from_db(owner, repo)

        if config_dict is None:
            log.info("Using default config", owner=owner, repo=repo)
            config_dict = {}

        config = ReviewerConfig(**config_dict)

        if self.cache:
            try:
                await self.cache.set(owner, repo, config.model_dump())
            except Exception as e:
                log.warning("Cache write failed", error=str(e))

        return config

    async def _load_from_db(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any] | None:
        """Load config from database."""
        if not self.repository:
            return None

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
        created_by: str | None = None,
    ) -> ConfigModel | None:
        """Save config to database, invalidate cache."""
        if not self.repository:
            log.warning("Cannot save config: no repository configured")
            return None

        db_config = await self.repository.upsert(
            owner=owner,
            repo=repo,
            config_data=config.model_dump(),
            updated_by=created_by,
        )

        if self.cache:
            await self.cache.delete(owner, repo)

        log.info("Config saved", owner=owner, repo=repo)
        return db_config

    async def delete_config(self, owner: str, repo: str) -> bool:
        """Delete stored config from database and cache."""
        deleted = False

        if self.repository:
            deleted = await self.repository.delete(owner, repo)

        if self.cache:
            await self.cache.delete(owner, repo)

        return deleted

    async def invalidate_cache(self, owner: str, repo: str) -> None:
        """Invalidate cached config."""
        if self.cache:
            await self.cache.delete(owner, repo)
            log.debug("Cache invalidated", owner=owner, repo=repo)


async def create_config_service(
    github: GitHubService,
    *,
    with_cache: bool = True,
    with_database: bool = True,
) -> ConfigService:
    """Create ConfigService with optional cache and database support."""
    cache: ConfigCache | None = None
    repository: ConfigRepository | None = None

    if with_cache:
        try:
            from ..redis import get_redis, is_redis_configured

            if is_redis_configured():
                redis = await get_redis()
                cache = ConfigCache(redis)
                log.debug("Config cache enabled")
        except Exception as e:
            log.warning("Failed to setup config cache", error=str(e))

    return ConfigService(
        github=github,
        cache=cache,
        repository=repository,
    )
