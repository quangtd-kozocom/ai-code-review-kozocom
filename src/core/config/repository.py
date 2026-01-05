"""
Config repository - SQLModel CRUD operations.

Provides database operations for config storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConfigCreate, ConfigModel

log = structlog.get_logger()


class ConfigRepository:
    """
    Repository for config database operations.

    Uses SQLModel for type-safe queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session.
        """
        self.session = session

    async def get(self, owner: str, repo: str) -> ConfigModel | None:
        """
        Get config by owner/repo.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            ConfigModel if found, None otherwise.
        """
        statement = select(ConfigModel).where(
            ConfigModel.owner == owner,
            ConfigModel.repo == repo,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: int) -> ConfigModel | None:
        """
        Get config by ID.

        Args:
            config_id: Primary key ID.

        Returns:
            ConfigModel if found, None otherwise.
        """
        return await self.session.get(ConfigModel, config_id)

    async def create(self, data: ConfigCreate) -> ConfigModel:
        """
        Create new config.

        Args:
            data: ConfigCreate schema.

        Returns:
            Created ConfigModel.
        """
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
        """
        Insert or update config.

        Args:
            owner: Repository owner.
            repo: Repository name.
            config_data: Config as dict.
            updated_by: Username who made the change.

        Returns:
            Upserted ConfigModel.
        """
        existing = await self.get(owner, repo)

        if existing:
            # Update
            existing.config_data = config_data
            existing.updated_at = datetime.now(timezone.utc)
            self.session.add(existing)
            await self.session.flush()
            log.info("Config updated", owner=owner, repo=repo)
            return existing
        else:
            # Create
            return await self.create(
                ConfigCreate(
                    owner=owner,
                    repo=repo,
                    config_data=config_data,
                    created_by=updated_by,
                )
            )

    async def delete(self, owner: str, repo: str) -> bool:
        """
        Delete config.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            True if deleted, False if not found.
        """
        config = await self.get(owner, repo)
        if config:
            await self.session.delete(config)
            await self.session.flush()
            log.info("Config deleted", owner=owner, repo=repo)
            return True
        return False

    async def list_all(self, limit: int = 100) -> list[ConfigModel]:
        """
        List all configs (admin use).

        Args:
            limit: Maximum results.

        Returns:
            List of ConfigModel.
        """
        statement = select(ConfigModel).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())
