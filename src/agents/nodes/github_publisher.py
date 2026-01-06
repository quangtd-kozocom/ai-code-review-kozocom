"""GitHub publisher node with CTA for on-demand commands."""

from enum import StrEnum

import structlog

from ...app.services.github import GitHubService
from ...core.config import ReviewerConfig
from ...core.i18n import Language, get_message
from ..state import GraphState, ReviewComment

log = structlog.get_logger()


class Severity(StrEnum):
    """Review comment severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


# Emoji mapping for severity levels
SEVERITY_EMOJI: dict[str, str] = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
    Severity.SUGGESTION: "💡",
}


async def run(state: GraphState) -> dict:
    """Post review to GitHub."""
    ctx = state["context"]
    comments = state["final_comments"]
    summary = state["summary"]

    # Get language from config
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    language: Language = config.language if config.language in ("en", "vi", "ja") else "en"

    log.info("GitHub publisher started", pr=ctx.pr_number, comments=len(comments))

    if not comments:
        log.info("No comments to publish", pr=ctx.pr_number)
        return {"review_id": None}

    github = GitHubService(ctx.installation_id)

    # Format comments for GitHub API
    review_comments = [
        {
            "path": c.file,
            "line": c.line,
            "body": format_comment(c, language),
        }
        for c in comments
    ]

    # Determine review action based on severity
    has_critical = any(c.severity == Severity.CRITICAL for c in comments)
    event = "REQUEST_CHANGES" if has_critical else "COMMENT"

    try:
        review_id = await github.create_review(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            body=summary,
            comments=review_comments,
            event=event,
        )
        log.info("Review published", review_id=review_id, pr=ctx.pr_number)
        return {"review_id": review_id}

    except Exception as e:
        log.exception("Failed to publish review")
        return {"errors": [str(e)]}


def format_comment(comment: ReviewComment, language: Language = "en") -> str:
    """
    Format a ReviewComment for GitHub.

    Args:
        comment: The review comment to format
        language: Language code for localized text

    Returns:
        Formatted markdown string
    """
    emoji = SEVERITY_EMOJI.get(comment.severity, "•")
    severity_upper = comment.severity.upper()

    # Build comment body
    parts = [
        f"{emoji} **{severity_upper}** ({comment.category})",
        "",
        comment.message,
    ]

    # Add suggestion if present (localized)
    if comment.suggestion:
        suggestion_prefix = get_message("suggestion_prefix", language)
        parts.extend(["", f"{suggestion_prefix} {comment.suggestion}"])

    return "\n".join(parts)
