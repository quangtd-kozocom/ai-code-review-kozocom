"""
Redis connection management.

Uses redis-py async client with hiredis for optimal performance.
Creates new connection per event loop to avoid 'Event loop is closed' errors.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis

from src.app.config import get_settings

log = structlog.get_logger()

# Track connections per event loop to avoid cross-loop issues
_connections: WeakValueDictionary[int, Redis] = WeakValueDictionary()


async def get_redis() -> Redis:
    """
    Get or create Redis connection for the current event loop.
    
    Creates a new connection if none exists for the current loop,
    avoiding 'Event loop is closed' errors in Celery workers.

    Returns:
        Async Redis client.

    Raises:
        RuntimeError: If REDIS_URL not configured.
    """
    from redis.asyncio import from_url
    
    settings = get_settings()

    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL not configured")
    
    # Get current event loop id
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        # No running loop - will be handled by caller
        raise RuntimeError("No running event loop")
    
    # Check if we have a valid connection for this loop
    redis = _connections.get(loop_id)
    
    if redis is not None:
        try:
            # Verify connection is still valid
            await redis.ping()
            return redis
        except Exception:
            # Connection is stale, create new one
            log.debug("Stale Redis connection, recreating")
            _connections.pop(loop_id, None)
    
    # Create new connection
    redis = from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    _connections[loop_id] = redis
    log.info("Redis connection created for loop", loop_id=loop_id)
    
    return redis


async def close_redis() -> None:
    """Close Redis connection for the current event loop."""
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        return
    
    redis = _connections.pop(loop_id, None)
    if redis:
        try:
            await redis.aclose()
            log.info("Redis connection closed", loop_id=loop_id)
        except Exception as e:
            log.warning("Error closing Redis", error=str(e))


def is_redis_configured() -> bool:
    """Check if Redis cache is configured."""
    settings = get_settings()
    return bool(settings.REDIS_URL)
