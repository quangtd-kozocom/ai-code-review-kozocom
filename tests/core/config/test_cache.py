"""Tests for config cache."""

import json
from unittest.mock import AsyncMock

import pytest

from src.core.config.cache import ConfigCache


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis client."""
    return AsyncMock()


@pytest.fixture
def cache(mock_redis: AsyncMock) -> ConfigCache:
    """Create ConfigCache with mock Redis."""
    return ConfigCache(mock_redis)


class TestConfigCache:
    """Test ConfigCache operations."""

    @pytest.mark.asyncio
    async def test_get_cache_miss(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return None on cache miss."""
        mock_redis.get.return_value = None

        result = await cache.get("owner", "repo")

        assert result is None
        mock_redis.get.assert_called_once_with("config:owner:repo")

    @pytest.mark.asyncio
    async def test_get_cache_hit(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return cached config on hit."""
        cached_data = {"language": "vi", "reviews": {"profile": "strict"}}
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await cache.get("owner", "repo")

        assert result is not None
        assert result["language"] == "vi"
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_handles_error(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return None on Redis error."""
        mock_redis.get.side_effect = Exception("Connection error")

        result = await cache.get("owner", "repo")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_success(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should set config in Redis."""
        config = {"language": "vi"}

        result = await cache.set("owner", "repo", config)

        assert result is True
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "config:owner:repo"
        assert json.loads(call_args[0][1]) == config

    @pytest.mark.asyncio
    async def test_set_custom_ttl(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should use custom TTL if provided."""
        config = {"language": "en"}

        await cache.set("owner", "repo", config, ttl=60)

        call_kwargs = mock_redis.set.call_args[1]
        assert call_kwargs["ex"] == 60

    @pytest.mark.asyncio
    async def test_set_handles_error(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return False on Redis error."""
        mock_redis.set.side_effect = Exception("Connection error")

        result = await cache.set("owner", "repo", {"language": "en"})

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should delete config from Redis."""
        result = await cache.delete("owner", "repo")

        assert result is True
        mock_redis.delete.assert_called_once_with("config:owner:repo")

    @pytest.mark.asyncio
    async def test_delete_handles_error(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return False on Redis error."""
        mock_redis.delete.side_effect = Exception("Connection error")

        result = await cache.delete("owner", "repo")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return True if key exists."""
        mock_redis.exists.return_value = 1

        result = await cache.exists("owner", "repo")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Should return False if key doesn't exist."""
        mock_redis.exists.return_value = 0

        result = await cache.exists("owner", "repo")

        assert result is False

    def test_key_format(self, cache: ConfigCache) -> None:
        """Should build correct cache key."""
        key = cache._key("myorg", "myrepo")
        assert key == "config:myorg:myrepo"
