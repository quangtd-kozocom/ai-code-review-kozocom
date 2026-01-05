"""
Redis connection management.

Uses redis-py async client with hiredis for optimal performance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis

from .app.config import get_settings

log = structlog.get_logger()

# Global connection
_redis: Redis | None = None


async def get_redis() -> Redis:
    """
    Get or create Redis connection.

    Returns:
        Async Redis client.

    Raises:
        RuntimeError: If UPSTASH_REDIS_URL not configured.
    """
    global _redis

    if _redis is None:
        from redis.asyncio import from_url

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
        await _redis.aclose()
        _redis = None
        log.info("Redis connection closed")


def is_redis_configured() -> bool:
    """Check if Redis cache is configured."""
    settings = get_settings()
    return bool(settings.UPSTASH_REDIS_URL)
