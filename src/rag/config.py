"""RAG configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from ..core.constants import IGNORE_PATTERNS, LANGUAGE_MAP


class RAGSettings(BaseSettings):
    """RAG-related settings."""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "code-reviewer"

    # Embedding (uses OpenAI via OPENAI_API_KEY from main config)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1024

    # Chunking
    max_chunk_tokens: int = 500  # Max tokens per chunk

    # Retrieval
    top_k: int = 5  # Number of similar chunks to retrieve

    # Indexing
    batch_size: int = 100  # Vectors per upsert batch

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
