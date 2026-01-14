# src/agents/nodes/finalize_review.py
"""Finalize review - save to DB and notify via Slack."""

import asyncio
from datetime import datetime
import structlog

from ...app.services.slack import SlackService
from ...core.database import get_session, is_db_configured
from ...core.repositories import ReviewRepository
from ..constants import SEVERITY_CRITICAL
from ..state import BreakingChange, ReviewComment, ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Finalize review: save to DB and send notifications."""
    ctx = state.get("pr_context")
    if not ctx:
        return {}

    all_comments = state.get("all_comments", [])
    all_breaking = state.get("all_breaking_changes", [])
    file_diffs = state.get("file_diffs", [])
    skip_review = state.get("skip_review", False)

    log.info("finalize_review.started", pr=ctx.pr_number, breaking=len(all_breaking), comments=len(all_comments))

    # Run DB save and Slack notify in parallel
    db_task = _save_to_db(ctx, all_breaking, all_comments, file_diffs, skip_review, state.get("skip_reason"))
    slack_task = _notify_slack(ctx, all_breaking, all_comments)

    db_result, slack_result = await asyncio.gather(db_task, slack_task, return_exceptions=True)

    if isinstance(db_result, Exception):
        log.error("finalize_review.db_failed", error=str(db_result))
        db_result = {"status": "error", "error": str(db_result)}
    if isinstance(slack_result, Exception):
        log.error("finalize_review.slack_failed", error=str(slack_result))
        slack_result = {"status": "error", "error": str(slack_result)}

    log.info("finalize_review.complete", pr=ctx.pr_number, db=db_result.get("status"), slack=slack_result.get("status"))
    return {"db_result": db_result, "slack_result": slack_result}


async def _save_to_db(ctx, breaking: list[BreakingChange], comments: list[ReviewComment], file_diffs: list, skip: bool, skip_reason: str | None) -> dict:
    """Save review results to database."""
    if not is_db_configured():
        return {"status": "skipped", "reason": "Database not configured"}

    async with get_session() as session:
        repo = ReviewRepository(session)
        
        # Get or create repository
        repository = await repo.get_or_create_repo(ctx.owner, ctx.repo, ctx.installation_id)
        
        # Check existing
        if await repo.get_review_by_pr(repository.id, ctx.pr_number):
            return {"status": "skipped", "reason": "Review already exists"}

        # Count severities
        critical = sum(1 for bc in breaking if bc.severity == SEVERITY_CRITICAL)

        # Create review
        review = await repo.create_review({
            "repository_id": repository.id,
            "pr_number": ctx.pr_number,
            "pr_title": ctx.title,
            "pr_author": ctx.author,
            "base_branch": ctx.base_branch,
            "head_branch": ctx.head_branch,
            "status": "skipped" if skip else "completed",
            "skip_reason": skip_reason,
            "total_files": len(file_diffs),
            "total_changes": len(breaking),
            "total_comments": len(comments),
            "count_critical": critical,
            "count_warning": len(breaking) - critical,
            "completed_at": datetime.now() if not skip else None,
        })

        # Add breaking changes
        for bc in breaking:
            callers = [{"file_path": c.file_path, "line_number": c.line, "call_text": c.call_text, "break_reason": c.break_reason} for c in bc.affected_callers]
            await repo.add_breaking_change(review.id, {
                "file_path": bc.file_path,
                "line_number": bc.line,
                "entity_type": bc.entity_type,
                "entity_name": bc.entity_name,
                "class_name": bc.class_name,
                "change_type": bc.change_type,
                "change_detail": bc.change_detail,
                "old_definition": bc.old_definition,
                "new_definition": bc.new_definition,
                "severity": bc.severity,
                "recommendation": bc.recommendation,
            }, callers)

        # Add comments
        for c in comments:
            await repo.add_comment(review.id, {
                "file_path": c.file,
                "line_number": c.line,
                "severity": c.severity,
                "message": c.message,
                "recommendation": c.recommendation,
                "affected_files": c.affected_files,
            })

        # Update repo last_review_at
        repository.last_review_at = datetime.now()

        log.info("finalize_review.db_saved", review_id=review.id)
        return {"status": "success", "review_id": review.id}


async def _notify_slack(ctx, breaking: list[BreakingChange], comments: list[ReviewComment]) -> dict:
    """Send summary to Slack."""
    slack = SlackService()
    if not slack.is_configured():
        return {"status": "skipped", "reason": "Slack not configured"}

    summary = _build_summary(ctx, breaking)
    return await slack.post_review_summary(
        pr_url=f"https://github.com/{ctx.owner}/{ctx.repo}/pull/{ctx.pr_number}",
        pr_title=ctx.title,
        author=ctx.author,
        summary=summary,
        breaking_count=len(breaking),
        comment_count=len(comments),
    )


def _build_summary(ctx, breaking: list[BreakingChange]) -> str:
    """Build summary message for Slack notification."""
    if not breaking:
        return ":white_check_mark: *Review Passed:* No breaking changes detected."

    critical = sum(1 for b in breaking if b.severity == SEVERITY_CRITICAL)
    warning = len(breaking) - critical
    affected_files = {c.file_path for b in breaking for c in b.affected_callers}

    # Stats line with spacing
    stats_parts = []
    if critical > 0:
        stats_parts.append(f":red_circle: *{critical}* Critical")
    if warning > 0:
        stats_parts.append(f":warning: *{warning}* Warnings")
    stats_parts.append(f":file_folder: *{len(affected_files)}* Affected Files")
    
    stats_line = "  |  ".join(stats_parts)

    # Top Issues with detailed blockquotes
    issues_list = []
    for b in breaking[:3]:
        icon = ":no_entry:" if b.severity == SEVERITY_CRITICAL else ":warning:"
        # Format: Icon & Name \n > Detail
        item = f"*{icon} {b.entity_name}*\n> {b.change_detail}"
        issues_list.append(item)

    parts = [
        stats_line,
        "",
        "*Top Issues Identified:*",
        *issues_list
    ]

    if len(breaking) > 3:
        parts.append(f"\n_:information_source: And {len(breaking) - 3} more issues..._")

    return "\n".join(parts)
