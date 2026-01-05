"""
Configuration module.

Provides repository-level configuration for AI reviewer behavior.

Usage:
    from src.core.config import ConfigService, ReviewerConfig
    from src.core.config import create_config_service

    # Create service
    service = await create_config_service(github)

    # Get config for repo
    config = await service.get_config("owner", "repo")

    # Use config
    if not config.should_ignore(filename):
        threshold = config.get_threshold()
        instructions = config.get_path_instructions(filename)
"""

from .cache import ConfigCache
from .loader import ConfigLoader
from .models import ConfigCreate, ConfigModel, ConfigRead, ConfigUpdate
from .repository import ConfigRepository
from .schemas import (
    AutoReviewConfig,
    ChatConfig,
    PathInstruction,
    ReviewerConfig,
    ReviewProfile,
    ReviewsConfig,
)
from .service import ConfigService, create_config_service

__all__ = [
    # Schemas (Pydantic)
    "ReviewerConfig",
    "ReviewProfile",
    "PathInstruction",
    "ReviewsConfig",
    "AutoReviewConfig",
    "ChatConfig",
    # Models (SQLModel)
    "ConfigModel",
    "ConfigCreate",
    "ConfigUpdate",
    "ConfigRead",
    # Services
    "ConfigService",
    "ConfigCache",
    "ConfigRepository",
    "ConfigLoader",
    # Factory
    "create_config_service",
]
