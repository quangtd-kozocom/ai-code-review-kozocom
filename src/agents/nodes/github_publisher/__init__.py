"""GitHub publisher node - posts review comments to GitHub PRs."""

from ....app.services.github import GitHubService
from ....core.config import ReviewerConfig
from ....core.i18n import Language
from ...state import PRContext, ReviewComment, ReviewState
from .models import PublishResult
from .publisher import GitHubReviewPublisher

__all__ = ["run", "GitHubReviewPublisher", "PublishResult"]


async def run(state: ReviewState) -> dict:
    """
    Post review to GitHub with diff-aware validation.

    This is the main entry point for the LangGraph node.
    """
    ctx = state["pr_context"]
    comments = state.get("comments", [])
    summary = state.get("summary", "")

    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    language: Language = config.language if config.language in ("en", "vi", "ja") else "en"

    github = GitHubService(ctx.installation_id)
    publisher = GitHubReviewPublisher(github, ctx, language)

    result = await publisher.publish(summary, comments)

    return {
        "review_id": result.review_id,
        "errors": result.errors if result.errors else None,
    }
