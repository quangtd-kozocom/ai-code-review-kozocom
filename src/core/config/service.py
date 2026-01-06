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
        github: GitHubService,
        cache: ConfigCache | None = None,
        repository: ConfigRepository | None = None,
    ) -> None:
        """
        Initialize ConfigService.

        Args:
            github: GitHubService for loading .reviewer.yaml.
            cache: Optional ConfigCache for Redis caching.
            repository: Optional ConfigRepository for database fallback.
        """
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

        Resolution order:
        1. Redis cache
        2. .reviewer.yaml from GitHub
        3. Database config
        4. Default values

        Args:
            owner: Repository owner.
            repo: Repository name.
            ref: Git ref to read config from.

        Returns:
            ReviewerConfig with resolved settings.
        """
        # 1. Check cache
        if self.cache:
            try:
                cached = await self.cache.get(owner, repo)
                if cached is not None:
                    log.debug("Using cached config", owner=owner, repo=repo)
                    return ReviewerConfig(**cached)
            except Exception as e:
                log.warning("Cache read failed", error=str(e))

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
        """
        Save config to database.

        Use for setting defaults via API.

        Args:
            owner: Repository owner.
            repo: Repository name.
            config: Config to save.
            created_by: Username making the change.

        Returns:
            Saved ConfigModel, or None if no repository configured.
        """
        if not self.repository:
            log.warning("Cannot save config: no repository configured")
            return None

        # Upsert to database
        db_config = await self.repository.upsert(
            owner=owner,
            repo=repo,
            config_data=config.model_dump(),
            updated_by=created_by,
        )

        # Invalidate cache
        if self.cache:
            await self.cache.delete(owner, repo)

        log.info("Config saved", owner=owner, repo=repo)
        return db_config

    async def delete_config(self, owner: str, repo: str) -> bool:
        """
        Delete stored config.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            True if deleted.
        """
        deleted = False

        if self.repository:
            deleted = await self.repository.delete(owner, repo)

        if self.cache:
            await self.cache.delete(owner, repo)

        return deleted

    async def invalidate_cache(self, owner: str, repo: str) -> None:
        """
        Invalidate cached config.

        Args:
            owner: Repository owner.
            repo: Repository name.
        """
        if self.cache:
            await self.cache.delete(owner, repo)
            log.debug("Cache invalidated", owner=owner, repo=repo)


async def create_config_service(
    github: GitHubService,
    *,
    with_cache: bool = True,
    with_database: bool = True,
) -> ConfigService:
    """
    Create ConfigService with all dependencies.

    Factory function for creating ConfigService with optional
    cache and database support. Gracefully degrades if services
    are not configured.

    Args:
        github: GitHubService instance.
        with_cache: Whether to enable Redis caching.
        with_database: Whether to enable database fallback.

    Returns:
        Configured ConfigService instance.
    """
    cache: ConfigCache | None = None
    repository: ConfigRepository | None = None

    # Setup cache if configured
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
