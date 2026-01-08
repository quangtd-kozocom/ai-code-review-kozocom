"""Protocol definitions for dependency injection.

This module defines protocols (structural subtyping) for core interfaces,
enabling easier testing and swappable implementations.

Python 3.13+ compatible using modern type syntax.
"""

from typing import Protocol, runtime_checkable

from src.ast.models import CodeChunk, RelatedCode

# =============================================================================
# Vector Store Protocol
# =============================================================================


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Protocol for vector store operations."""

    def upsert(self, vectors: list[dict], namespace: str) -> None:
        """Upsert vectors to index."""
        ...

    def query(
        self,
        vector: list[float],
        namespace: str,
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list:
        """Query similar vectors."""
        ...

    def fetch_by_metadata(
        self,
        namespace: str,
        filter: dict,
        limit: int = 10,
    ) -> list:
        """Fetch vectors by metadata filter (no vector required)."""
        ...

    def delete_by_file(self, namespace: str, file_path: str) -> None:
        """Delete all vectors for a specific file."""
        ...

    def delete_namespace(self, namespace: str) -> None:
        """Delete entire namespace."""
        ...


# =============================================================================
# Parser Protocol
# =============================================================================


@runtime_checkable
class CodeParserProtocol(Protocol):
    """Protocol for code parsing operations."""

    def parse_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Parse a file and return code chunks."""
        ...

    def detect_language(self, file_path: str) -> str | None:
        """Detect language from file extension."""
        ...


# =============================================================================
# Embedder Protocol
# =============================================================================


@runtime_checkable
class EmbedderProtocol(Protocol):
    """Protocol for embedding generation."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...


# =============================================================================
# Language Plugin Protocol
# =============================================================================


@runtime_checkable
class LanguagePluginProtocol(Protocol):
    """Protocol for language-specific parsing."""

    @property
    def name(self) -> str:
        """Language name."""
        ...

    @property
    def extensions(self) -> tuple[str, ...]:
        """File extensions."""
        ...

    def parse_imports(self, content: str) -> list[str]:
        """Extract imported modules."""
        ...

    def parse_calls(self, content: str) -> list[str]:
        """Extract function calls."""
        ...

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns."""
        ...


# =============================================================================
# Retriever Protocol
# =============================================================================


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Protocol for RAG retrieval operations."""

    def retrieve(
        self,
        owner: str,
        repo: str,
        file_path: str,
        function_name: str,
    ) -> list[RelatedCode]:
        """Retrieve related code for a function."""
        ...

    def retrieve_for_function(
        self,
        owner: str,
        repo: str,
        function_name: str,
        signature: str | None = None,
        current_file: str | None = None,
        function_content: str | None = None,
    ) -> list[RelatedCode]:
        """Retrieve context for a specific function."""
        ...


# =============================================================================
# GitHub Service Protocol
# =============================================================================


@runtime_checkable
class GitHubClientProtocol(Protocol):
    """Protocol for GitHub API operations."""

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Fetch files changed in a PR."""
        ...

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch PR details."""
        ...

    async def get_file_raw(self, owner: str, repo: str, path: str, ref: str = "HEAD") -> str | None:
        """Get raw file content."""
        ...

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        comments: list[dict],
        event: str = "COMMENT",
    ) -> int:
        """Create a PR review."""
        ...

    async def close(self) -> None:
        """Close the client and release resources."""
        ...
