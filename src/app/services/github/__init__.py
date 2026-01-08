"""GitHub services module.

Provides modular GitHub API access with separate concerns:
- GitHubClient: Base client with auth and HTTP handling
- PRService: Pull request operations
- FileService: File content operations
- CommentService: Comment and review operations
- GitHubService: Combined service using multiple inheritance

Usage:
    async with create_github_service(installation_id) as github:
        files = await github.get_pr_files(owner, repo, pr_number)
        content = await github.get_file_raw(owner, repo, path)
"""

from contextlib import asynccontextmanager

from .client import GitHubClient, create_github_client
from .comments import CommentService
from .files import FileService
from .pr import PRService

__all__ = [
    "GitHubClient",
    "PRService",
    "FileService",
    "CommentService",
    "GitHubService",
    "create_github_client",
    "create_github_service",
]


class GitHubService(PRService, FileService, CommentService):
    """Combined GitHub service using multiple inheritance.

    Inherits all operations from:
    - PRService: get_pr_files, get_pr_details, create_review
    - FileService: get_file_raw, get_file_content_at_pr
    - CommentService: create_pr_comment, create_issue_comment, etc.

    All share the same GitHubClient base (auth, token, HTTP client).
    """

    pass


@asynccontextmanager
async def create_github_service(installation_id: int):
    """Async context manager factory for GitHubService.

    Usage:
        async with create_github_service(installation_id) as github:
            files = await github.get_pr_files(owner, repo, pr_number)
    """
    service = GitHubService(installation_id)
    try:
        yield service
    finally:
        await service.close()
