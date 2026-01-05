"""
Database connection management with SQLModel + asyncpg.

Provides async session management and lifecycle hooks.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from .app.config import get_settings

log = structlog.get_logger()

# Global engine (created lazily)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create async engine.

    Returns:
        AsyncEngine configured for PostgreSQL.

    Raises:
        RuntimeError: If DATABASE_URL not configured.
    """
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


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory."""
    global _session_factory

    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as async context manager.

    Usage:
        async with get_session() as session:
            # use session

    Yields:
        AsyncSession with auto-commit on success, rollback on error.
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
    # Import models to register them with SQLModel.metadata
    from .config.models import ConfigModel  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    log.info("Database tables created")


async def close_db() -> None:
    """Close database engine on shutdown."""
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("Database engine closed")


def is_db_configured() -> bool:
    """Check if database is configured."""
    settings = get_settings()
    return bool(settings.DATABASE_URL)
