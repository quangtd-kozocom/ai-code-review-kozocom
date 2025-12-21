import structlog

from ...app.services.github import GitHubService
from ..state import GraphState

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Post review to GitHub."""
    ctx = state["context"]
    comments = state["final_comments"]
    summary = state["summary"]
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
            "body": _format_comment(c),
        }
        for c in comments
    ]

    # Determine review action
    has_critical = any(c.severity == "critical" for c in comments)
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
        log.error("Failed to publish review", error=str(e))
        return {"errors": [str(e)]}


def _format_comment(c) -> str:
    """Format a ReviewComment for GitHub."""
    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵", "suggestion": "💡"}
    body = f"{emoji.get(c.severity, '•')} **{c.severity.upper()}** ({c.category})\n\n{c.message}"
    if c.suggestion:
        body += f"\n\n**Suggestion:** {c.suggestion}"
    return body
