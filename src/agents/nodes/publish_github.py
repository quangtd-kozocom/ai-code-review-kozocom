"""Publish to GitHub node - posts review comments immediately."""

import structlog

from ...app.services.github import create_github_service
from ..state import ReviewState, ReviewComment

log = structlog.get_logger()

# HTTP status codes
HTTP_UNPROCESSABLE_ENTITY = 422


def _format_issue_comment(comment: ReviewComment) -> str:
    """Format a ReviewComment as an issue comment (when inline fails)."""
    severity_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(comment.severity, "💬")

    lines = [
        f"{severity_emoji} **{comment.severity.upper()}** in `{comment.file}` (line {comment.line})",
        "",
        comment.message,
    ]

    if comment.affected_files:
        lines.extend(["", "**Affected files:**"])
        for af in comment.affected_files[:10]:  # Limit to 10
            lines.append(f"- `{af.get('path', 'unknown')}` line {af.get('line', '?')}: {af.get('reason', '')}")

    if comment.recommendation:
        lines.extend(["", f"**Recommendation:** {comment.recommendation}"])

    return "\n".join(lines)


async def run(state: ReviewState) -> dict:
    """Publish review comments to GitHub PR.

    Posts inline review comments when possible, falls back to issue
    comments when the line is not in the diff (422 error).
    """
    comments = state.get("file_comments", [])
    ctx = state.get("pr_context")

    if not ctx:
        log.warning("publish_github.skipped", reason="no pr_context")
        return {}

    if not comments:
        log.debug("publish_github.skipped", pr=ctx.pr_number, reason="no comments")
        return {}

    log.info(
        "publish_github.started",
        pr=ctx.pr_number,
        repo=f"{ctx.owner}/{ctx.repo}",
        comments_count=len(comments),
    )

    async with create_github_service(ctx.installation_id) as github:
        results = []
        inline_count = 0
        fallback_count = 0
        error_count = 0

        for i, comment in enumerate(comments, 1):
            log.debug(
                "publish_github.posting",
                comment_index=i,
                file=comment.file,
                line=comment.line,
                severity=comment.severity,
            )

            # Try inline review comment first
            try:
                result = await github.create_pr_review_comment(
                    owner=ctx.owner,
                    repo=ctx.repo,
                    pr_number=ctx.pr_number,
                    body=comment.message,
                    path=comment.file,
                    line=comment.line,
                )
                results.append({"status": "success", "type": "inline", "comment_id": result.get("id")})
                inline_count += 1
                log.info(
                    "publish_github.inline_posted",
                    comment_id=result.get("id"),
                    file=comment.file,
                    line=comment.line,
                )
                continue
            except Exception as e:
                # Check if it's a 422 (line not in diff) - fallback to issue comment
                if str(HTTP_UNPROCESSABLE_ENTITY) in str(e) or "Unprocessable" in str(e):
                    log.debug(
                        "publish_github.inline_failed_fallback",
                        file=comment.file,
                        line=comment.line,
                        reason="line not in diff",
                    )
                else:
                    # Other error - log and try fallback anyway
                    log.warning(
                        "publish_github.inline_failed",
                        file=comment.file,
                        error=str(e),
                    )

            # Fallback: post as issue comment
            try:
                body = _format_issue_comment(comment)
                comment_id = await github.create_pr_comment(
                    owner=ctx.owner,
                    repo=ctx.repo,
                    pr_number=ctx.pr_number,
                    body=body,
                )
                results.append({"status": "success", "type": "issue_comment", "comment_id": comment_id})
                fallback_count += 1
                log.info(
                    "publish_github.fallback_posted",
                    comment_id=comment_id,
                    file=comment.file,
                )
            except Exception as e2:
                error_count += 1
                log.error(
                    "publish_github.fallback_failed",
                    file=comment.file,
                    error=str(e2),
                )
                results.append({"status": "error", "error": str(e2)})

    existing_results = state.get("github_results", [])

    log.info(
        "publish_github.complete",
        pr=ctx.pr_number,
        inline=inline_count,
        fallback=fallback_count,
        failed=error_count,
        total=len(comments),
    )

    return {
        "github_results": [*existing_results, *results],
        "published_comments": comments,
        "all_comments": comments,
    }
