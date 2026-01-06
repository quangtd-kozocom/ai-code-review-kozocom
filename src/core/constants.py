"""Shared constants used across the application.

This module centralizes commonly used mappings and patterns to avoid duplication.
"""

from pathlib import Path

__all__ = [
    # LLM Configuration
    "DEFAULT_LLM_TEMPERATURE",
    "DEFAULT_LLM_MAX_TOKENS",
    # Database Configuration
    "DEFAULT_DB_POOL_SIZE",
    "DEFAULT_DB_MAX_OVERFLOW",
    # HTTP Configuration
    "DEFAULT_HTTP_TIMEOUT",
    # Slack Configuration
    "SLACK_MESSAGE_CHAR_LIMIT",
    # Celery Configuration
    "CELERY_TASK_TIME_LIMIT",
    "CELERY_TASK_SOFT_TIME_LIMIT",
    "CELERY_PR_RETRY_COUNTDOWN",
    "CELERY_COMMAND_RETRY_COUNTDOWN",
    # Chat Command Configuration
    "MAX_FILES_FOR_TEST_GENERATION",
    # Mappings and patterns
    "LANGUAGE_MAP",
    "SKIP_PATTERNS",
    "IGNORE_PATTERNS",
    # Functions
    "get_language_from_path",
    "get_language_or_none",
]

# =============================================================================
# LLM Configuration
# =============================================================================
DEFAULT_LLM_TEMPERATURE: float = 0.1
DEFAULT_LLM_MAX_TOKENS: int = 65536

# =============================================================================
# Database Configuration
# =============================================================================
DEFAULT_DB_POOL_SIZE: int = 5
DEFAULT_DB_MAX_OVERFLOW: int = 10

# =============================================================================
# HTTP Configuration
# =============================================================================
DEFAULT_HTTP_TIMEOUT: float = 30.0

# =============================================================================
# Slack Configuration
# =============================================================================
SLACK_MESSAGE_CHAR_LIMIT: int = 2000

# =============================================================================
# Celery Configuration
# =============================================================================
CELERY_TASK_TIME_LIMIT: int = 300  # seconds
CELERY_TASK_SOFT_TIME_LIMIT: int = 280  # seconds
CELERY_PR_RETRY_COUNTDOWN: int = 60  # seconds
CELERY_COMMAND_RETRY_COUNTDOWN: int = 30  # seconds

# =============================================================================
# Chat Command Configuration
# =============================================================================
MAX_FILES_FOR_TEST_GENERATION: int = 3

# File extension to programming language mapping
LANGUAGE_MAP: dict[str, str] = {
    # Python
    ".py": "python",
    # JavaScript/TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    # Frontend frameworks
    ".vue": "vue",
    ".svelte": "svelte",
    # JVM languages
    ".java": "java",
    ".kt": "kotlin",
    ".scala": "scala",
    # Systems programming
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".swift": "swift",
    # Scripting
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    # .NET
    ".cs": "csharp",
    # Data/Config
    ".sql": "sql",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    # Web
    ".html": "html",
    ".css": "css",
    # Documentation
    ".md": "markdown",
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

# File patterns to ignore during PR review (binary, generated, dependencies)
IGNORE_PATTERNS: tuple[str, ...] = (
    # Lock files
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    # Minified files
    "*.min.js",
    "*.min.css",
    "*.map",
    # Dependencies and build
    "node_modules/*",
    "vendor/*",
    "dist/*",
    ".git/*",
    # Binary assets
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
)


def get_language_from_path(file_path: str) -> str:
    """
    Detect programming language from file extension.

    Args:
        file_path: Path to the file (can be relative or absolute)

    Returns:
        Language name (lowercase) or "text" if unknown
    """
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "text")


def get_language_or_none(file_path: str) -> str | None:
    """
    Detect programming language from file extension.

    Args:
        file_path: Path to the file (can be relative or absolute)

    Returns:
        Language name (lowercase) or None if unknown
    """
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext)
