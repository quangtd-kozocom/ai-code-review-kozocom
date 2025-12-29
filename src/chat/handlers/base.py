"""Base command handler and shared constants."""

from abc import ABC, abstractmethod

from ...app.services.github import GitHubService
from ...core.llm import get_llm
from ..context import CommandContext

# File extension to language mapping
LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}

# Patterns to skip for test generation
SKIP_PATTERNS: frozenset[str] = frozenset(
    {
        "test_",
        "_test.",
        ".test.",
        "tests/",
        "__init__",
        "config",
        "migration",
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".txt",
        ".lock",
        "package-lock",
        "yarn.lock",
    }
)


class BaseCommandHandler(ABC):
    """Abstract base class for command handlers."""

    def __init__(self, github: GitHubService):
        self.github = github
        self.llm = get_llm()

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> str:
        """Execute the command and return response text."""
        ...
