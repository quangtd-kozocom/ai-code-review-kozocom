"""RAG configuration.

Simplified configuration after removing Pinecone/embedding dependencies.
Now focused on AST-based analysis settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from ..core.constants import IGNORE_PATTERNS, LANGUAGE_MAP


class RAGSettings(BaseSettings):
    """RAG-related settings (simplified for AST-based approach)."""

    # Chunking
    max_chunk_tokens: int = 500  # Max tokens per chunk

    # Analysis limits
    max_changed_functions: int = 5  # Max functions per file to analyze
    max_callee_results: int = 5  # Max callees to retrieve per function
    max_caller_depth: int = 2  # Max depth for caller traversal
    max_sibling_results: int = 2  # Max sibling functions

    # Feature flags
    enable_sibling_detection: bool = True  # Find functions calling same dependencies
    enable_transitive_callees: bool = True  # Follow callee chain one level deeper

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


# Derive include_extensions from LANGUAGE_MAP keys
INCLUDE_EXTENSIONS: frozenset[str] = frozenset(LANGUAGE_MAP.keys())

# Extend IGNORE_PATTERNS with RAG-specific patterns
RAG_EXCLUDE_PATTERNS: tuple[str, ...] = IGNORE_PATTERNS + (
    # Additional patterns for RAG indexing
    ".venv/*",
    "venv/*",
    "__pycache__/*",
    "build/*",
    ".env*",
    "*.pyc",
    "*.pyo",
)


@lru_cache
def get_rag_settings() -> RAGSettings:
    """Factory function to get RAG settings (cached)."""
    return RAGSettings()
