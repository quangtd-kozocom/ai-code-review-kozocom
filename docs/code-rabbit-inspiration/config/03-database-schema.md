# 03 - Database Schema (SQLModel)

## 🗄️ SQLModel + Neon PostgreSQL

### Why SQLModel?

- ✅ **One model** for DB + Pydantic validation
- ✅ **Async native** with asyncpg
- ✅ **Type-safe** queries
- ✅ **FastAPI creator** (Sebastián Ramírez)

---

## 📦 Models Definition

### File: `src/core/config/models.py`

```python
"""
SQLModel definitions for config storage.

SQLModel = SQLAlchemy + Pydantic combined.
Same model works for DB operations AND validation.
"""

from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class ConfigBase(SQLModel):
    """
    Base config model with shared fields.

    This is NOT a table - just shared schema.
    """
    owner: str = Field(index=True, max_length=255)
    repo: str = Field(index=True, max_length=255)


class ConfigModel(ConfigBase, table=True):
    """
    Database table model for configs.

    Stores the full config as JSONB for flexibility.
    """
    __tablename__ = "configs"
    __table_args__ = (
        UniqueConstraint("owner", "repo", name="uq_configs_owner_repo"),
    )

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Config stored as JSONB (flexible schema)
    config_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, default={}),
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    created_by: Optional[str] = Field(default=None, max_length=255)


class ConfigCreate(ConfigBase):
    """Schema for creating a new config."""
    config_data: dict = Field(default_factory=dict)
    created_by: Optional[str] = None


class ConfigUpdate(SQLModel):
    """Schema for updating config."""
    config_data: dict
    updated_by: Optional[str] = None


class ConfigRead(ConfigBase):
    """Schema for reading config (API response)."""
    id: int
    config_data: dict
    created_at: datetime
    updated_at: datetime
```

---

## 🔌 Database Connection

### File: `src/core/database.py`

```python
"""
Database connection management with SQLModel + asyncpg.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..app.config import get_settings

log = structlog.get_logger()

# Global engine (created once)
_engine = None


def get_engine():
    """Get or create async engine."""
    global _engine

    if _engine is None:
        settings = get_settings()

        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL not configured")

        # Convert to async URL format
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        _engine = create_async_engine(
            db_url,
            echo=settings.DEBUG,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        log.info("Database engine created")

    return _engine


# Session factory
def get_session_factory():
    """Get async session factory."""
    return sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as async context manager.

    Usage:
        async with get_session() as session:
            # use session
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize database - create all tables.

    Run this on app startup or via migration script.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    log.info("Database tables created")


async def close_db() -> None:
    """Close database engine on shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        log.info("Database engine closed")
```

---

## 📋 Repository Pattern

### File: `src/core/config/repository.py`

```python
"""
Config repository - SQLModel CRUD operations.
"""

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConfigModel, ConfigCreate

log = structlog.get_logger()


class ConfigRepository:
    """
    Repository for config database operations.

    Uses SQLModel for type-safe queries.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, owner: str, repo: str) -> Optional[ConfigModel]:
        """
        Get config by owner/repo.

        Returns:
            ConfigModel if found, None otherwise.
        """
        statement = select(ConfigModel).where(
            ConfigModel.owner == owner,
            ConfigModel.repo == repo,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: int) -> Optional[ConfigModel]:
        """Get config by ID."""
        return await self.session.get(ConfigModel, config_id)

    async def create(self, data: ConfigCreate) -> ConfigModel:
        """
        Create new config.

        Args:
            data: ConfigCreate schema

        Returns:
            Created ConfigModel
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
        config_data: dict,
        updated_by: Optional[str] = None,
    ) -> ConfigModel:
        """
        Insert or update config.

        Args:
            owner: Repository owner
            repo: Repository name
            config_data: Config as dict
            updated_by: Username who made the change

        Returns:
            Upserted ConfigModel
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
            return await self.create(ConfigCreate(
                owner=owner,
                repo=repo,
                config_data=config_data,
                created_by=updated_by,
            ))

    async def delete(self, owner: str, repo: str) -> bool:
        """
        Delete config.

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
        """List all configs (admin use)."""
        statement = select(ConfigModel).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())
```

---

## 🧪 Migration Script

### File: `scripts/migrate_db.py`

```python
#!/usr/bin/env python3
"""
Database migration script.

Usage:
    python scripts/migrate_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import init_db, close_db


async def main():
    """Run database migrations."""
    print("🚀 Running database migration...")

    try:
        await init_db()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📊 SQL Generated by SQLModel

```sql
-- Auto-generated by SQLModel
CREATE TABLE IF NOT EXISTS configs (
    id SERIAL PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    repo VARCHAR(255) NOT NULL,
    config_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by VARCHAR(255),

    CONSTRAINT uq_configs_owner_repo UNIQUE (owner, repo)
);

CREATE INDEX ix_configs_owner ON configs (owner);
CREATE INDEX ix_configs_repo ON configs (repo);
```

---

## ✅ Key Benefits of SQLModel

1. **Single Source of Truth** - One model for DB + API
2. **Pydantic Validation** - Built-in validation
3. **Type Hints** - Full IDE support
4. **Async Native** - Works with asyncpg
5. **FastAPI Integration** - Same author, perfect fit
