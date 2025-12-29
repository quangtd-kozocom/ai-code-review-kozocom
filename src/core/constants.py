"""Shared constants used across the application.

This module centralizes commonly used mappings and patterns to avoid duplication.
"""

from pathlib import Path

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
