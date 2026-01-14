"""Protocol definitions for dependency injection.

This module defines protocols (structural subtyping) for core interfaces,
enabling easier testing and swappable implementations.

Python 3.14+ compatible using modern type syntax.
"""

from typing import Protocol, runtime_checkable

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

    async def get_file_raw(
        self, owner: str, repo: str, path: str, ref: str = "HEAD", *, resolve_path: bool = False
    ) -> str | None:
        """Get raw file content. Set resolve_path=True to auto-resolve partial filenames."""
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


# =============================================================================
# Analysis Protocol
# =============================================================================


@runtime_checkable
class AnalyzerProtocol(Protocol):
    """Protocol for code analysis operations."""

    def extract_functions(self, file_path: str, content: str) -> list:
        """Extract function definitions from a file."""
        ...

    def find_call_sites(self, file_path: str, content: str, target_function: str) -> list:
        """Find all call sites for a function."""
        ...

    def compare_functions(self, old_content: str, new_content: str, file_path: str) -> dict:
        """Compare function definitions between versions."""
        ...


# =============================================================================
# Notification Protocol
# =============================================================================


@runtime_checkable
class NotifierProtocol(Protocol):
    """Protocol for notification services."""

    async def send_notification(
        self,
        channel: str,
        message: str,
        metadata: dict | None = None,
    ) -> bool:
        """Send a notification."""
        ...


# =============================================================================
# Cache Protocol
# =============================================================================


@runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for cache operations."""

    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Set value in cache."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...
