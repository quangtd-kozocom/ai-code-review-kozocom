"""Application services module.

Provides service classes for external integrations:
- GitHub: API client for GitHub operations
- Slack: Notification service (if applicable)

GitHub services are now modular:
- GitHubClient: Base client with auth and HTTP handling
- PRService: Pull request operations
- FileService: File content operations
- CommentService: Comment and review operations
- GitHubService: Combined service for backward compatibility
"""

from .github import (
    CommentService,
    FileService,
    GitHubClient,
    GitHubService,
    PRService,
    create_github_client,
    create_github_service,
)

__all__ = [
    "GitHubClient",
    "GitHubService",
    "PRService",
    "FileService",
    "CommentService",
    "create_github_client",
    "create_github_service",
]
