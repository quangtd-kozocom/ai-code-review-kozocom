"""Tests for config service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config.cache import ConfigCache
from src.core.config.repository import ConfigRepository
from src.core.config.schemas import ReviewerConfig, ReviewProfile
from src.core.config.service import ConfigService


@pytest.fixture
def mock_github() -> MagicMock:
    """Create mock GitHub service."""
    return MagicMock()


@pytest.fixture
def mock_cache() -> AsyncMock:
    """Create mock cache."""
    return AsyncMock(spec=ConfigCache)


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Create mock repository."""
    return AsyncMock(spec=ConfigRepository)


@pytest.fixture
def service(
    mock_github: MagicMock,
    mock_cache: AsyncMock,
    mock_repository: AsyncMock,
) -> ConfigService:
    """Create ConfigService with mocks."""
    return ConfigService(mock_github, mock_cache, mock_repository)


class TestConfigService:
    """Test ConfigService."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
    ) -> None:
        """Should return cached config without loading."""
        mock_cache.get.return_value = {"language": "vi"}

        result = await service.get_config("owner", "repo")

        assert result.language == "vi"
        mock_cache.get.assert_called_once_with("owner", "repo")

    @pytest.mark.asyncio
    async def test_load_from_github(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
    ) -> None:
        """Should load from GitHub when cache miss."""
        mock_cache.get.return_value = None

        # Mock loader
        service.loader.load = AsyncMock(return_value={"language": "ja"})

        result = await service.get_config("owner", "repo")

        assert result.language == "ja"
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_database(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
        mock_repository: AsyncMock,
    ) -> None:
        """Should fallback to database when no YAML."""
        mock_cache.get.return_value = None
        service.loader.load = AsyncMock(return_value=None)

        # Mock DB response
        db_config = MagicMock()
        db_config.config_data = {"language": "ko"}
        mock_repository.get.return_value = db_config

        result = await service.get_config("owner", "repo")

        assert result.language == "ko"

    @pytest.mark.asyncio
    async def test_fallback_to_defaults(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
        mock_repository: AsyncMock,
    ) -> None:
        """Should use defaults when nothing found."""
        mock_cache.get.return_value = None
        service.loader.load = AsyncMock(return_value=None)
        mock_repository.get.return_value = None

        result = await service.get_config("owner", "repo")

        assert result.language == "en"  # default

    @pytest.mark.asyncio
    async def test_cache_error_continues(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
    ) -> None:
        """Should continue if cache read fails."""
        mock_cache.get.side_effect = Exception("Redis error")
        service.loader.load = AsyncMock(return_value={"language": "de"})

        result = await service.get_config("owner", "repo")

        assert result.language == "de"

    @pytest.mark.asyncio
    async def test_save_config(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
        mock_repository: AsyncMock,
    ) -> None:
        """Should save config to database and invalidate cache."""
        config = ReviewerConfig(language="fr")
        mock_repository.upsert.return_value = MagicMock()

        await service.save_config("owner", "repo", config, created_by="user1")

        mock_repository.upsert.assert_called_once()
        mock_cache.delete.assert_called_once_with("owner", "repo")

    @pytest.mark.asyncio
    async def test_delete_config(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
        mock_repository: AsyncMock,
    ) -> None:
        """Should delete config from database and cache."""
        mock_repository.delete.return_value = True

        result = await service.delete_config("owner", "repo")

        assert result is True
        mock_repository.delete.assert_called_once_with("owner", "repo")
        mock_cache.delete.assert_called_once_with("owner", "repo")

    @pytest.mark.asyncio
    async def test_invalidate_cache(
        self,
        service: ConfigService,
        mock_cache: AsyncMock,
    ) -> None:
        """Should invalidate cache."""
        await service.invalidate_cache("owner", "repo")

        mock_cache.delete.assert_called_once_with("owner", "repo")


class TestConfigServiceWithoutDependencies:
    """Test ConfigService with missing dependencies."""

    @pytest.mark.asyncio
    async def test_no_cache(self, mock_github: MagicMock) -> None:
        """Should work without cache."""
        service = ConfigService(mock_github, cache=None, repository=None)
        service.loader.load = AsyncMock(return_value={"language": "pt"})

        result = await service.get_config("owner", "repo")

        assert result.language == "pt"

    @pytest.mark.asyncio
    async def test_no_repository(self, mock_github: MagicMock) -> None:
        """Should work without repository."""
        service = ConfigService(mock_github, cache=None, repository=None)
        service.loader.load = AsyncMock(return_value=None)

        result = await service.get_config("owner", "repo")

        # Falls back to defaults
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_save_without_repository(self, mock_github: MagicMock) -> None:
        """Should return None when saving without repository."""
        service = ConfigService(mock_github, cache=None, repository=None)
        config = ReviewerConfig()

        result = await service.save_config("owner", "repo", config)

        assert result is None
