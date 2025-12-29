"""Base command handler and shared constants.

Constants are imported from core.constants for centralized management.
"""

from abc import ABC, abstractmethod

from ...app.services.github import GitHubService
from ...core.constants import (
    LANGUAGE_MAP,
    SKIP_PATTERNS,
    get_language_from_path,
)
from ...core.llm import get_llm
from ..context import CommandContext

# Re-export for backward compatibility (other modules import from here)
__all__ = [
    "LANGUAGE_MAP",
    "SKIP_PATTERNS",
    "get_language_from_path",
    "BaseCommandHandler",
]


class BaseCommandHandler(ABC):
    """Abstract base class for command handlers."""

    def __init__(self, github: GitHubService):
        self.github = github
        self.llm = get_llm()

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> str:
        """Execute the command and return response text."""
        ...
