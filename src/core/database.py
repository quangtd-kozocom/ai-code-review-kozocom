"""
Database connection management with SQLModel + asyncpg.

Provides async session management and lifecycle hooks.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from ..app.config import get_settings
from .constants import DEFAULT_DB_MAX_OVERFLOW, DEFAULT_DB_POOL_SIZE

log = structlog.get_logger()

# Global engine (created lazily)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create async PostgreSQL engine. Raises RuntimeError if DATABASE_URL not set."""
    global _engine

    if _engine is None:
        settings = get_settings()

        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL not configured")

        # Convert to async URL format
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        # Remove libpq-specific parameters not supported by asyncpg
        # asyncpg has different parameter names (e.g., 'ssl' instead of 'sslmode')
        unsupported_params = {"sslmode", "channel_binding", "connect_timeout", "application_name"}
        if "?" in db_url:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(db_url)
            query_params = parse_qs(parsed.query)
            for param in unsupported_params:
                query_params.pop(param, None)
            new_query = urlencode(query_params, doseq=True)
            db_url = urlunparse(parsed._replace(query=new_query))

        _engine = create_async_engine(
            db_url,
            echo=False,  # Disable SQL logging
            pool_size=DEFAULT_DB_POOL_SIZE,
            max_overflow=DEFAULT_DB_MAX_OVERFLOW,
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
async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get database session with auto-commit on success, rollback on error."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database - create all tables."""
    # Import models to register them with SQLModel.metadata
    from .models import Repository, PRReview, BreakingChange, AffectedCaller, ReviewComment, RepoConfig  # noqa: F401

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


def reset_db() -> None:
    """
    Reset database engine synchronously (for Celery worker context).

    Called after asyncio.run() completes to prevent "attached to different loop" errors.
    The engine will be recreated lazily on next use with the new event loop.
    """
    global _engine, _session_factory

    if _engine:
        # Use sync dispose - connections will be terminated
        # This is safe because we're between asyncio.run() calls
        try:
            _engine.sync_engine.dispose()
        except Exception:
            pass  # Ignore errors during cleanup
        _engine = None
        _session_factory = None
        log.debug("Database engine reset for new event loop")


def is_db_configured() -> bool:
    """Check if database is configured."""
    settings = get_settings()
    return bool(settings.DATABASE_URL)
