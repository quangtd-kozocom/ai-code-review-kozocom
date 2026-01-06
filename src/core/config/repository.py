"""
Config repository - SQLModel CRUD operations.

Provides database operations for config storage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConfigCreate, ConfigModel

log = structlog.get_logger()


class ConfigRepository:
    """Repository for config database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, owner: str, repo: str) -> ConfigModel | None:
        """Get config by owner/repo."""
        statement = select(ConfigModel).where(
            ConfigModel.owner == owner,
            ConfigModel.repo == repo,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: int) -> ConfigModel | None:
        """Get config by ID."""
        return await self.session.get(ConfigModel, config_id)

    async def create(self, data: ConfigCreate) -> ConfigModel:
        """Create new config."""
        config = ConfigModel(
            owner=data.owner,
            repo=data.repo,
            config_data=data.config_data,
            created_by=data.created_by,
        )
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)

        log.info("Config created", owner=data.owner, repo=data.repo)
        return config

    async def upsert(
        self,
        owner: str,
        repo: str,
        config_data: dict[str, Any],
        updated_by: str | None = None,
    ) -> ConfigModel:
        """Insert or update config."""
        existing = await self.get(owner, repo)

        if existing:
            existing.config_data = config_data
            existing.updated_at = datetime.now(UTC)
            self.session.add(existing)
            await self.session.flush()
            log.info("Config updated", owner=owner, repo=repo)
            return existing

        return await self.create(
            ConfigCreate(
                owner=owner,
                repo=repo,
                config_data=config_data,
                created_by=updated_by,
            )
        )

    async def delete(self, owner: str, repo: str) -> bool:
        """Delete config, return True if deleted."""
        config = await self.get(owner, repo)
        if config:
            await self.session.delete(config)
            await self.session.flush()
            log.info("Config deleted", owner=owner, repo=repo)
            return True
        return False

    async def list_all(self, limit: int = 100) -> list[ConfigModel]:
        """List all configs with optional limit."""
        statement = select(ConfigModel).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())
