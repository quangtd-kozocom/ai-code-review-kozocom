# src/agents/nodes/finalize_review.py
"""Finalize review - save to DB and notify via Slack."""

import asyncio
import httpx
import structlog

from ...app.config import get_settings
from ...app.services.slack import SlackService
from ..constants import SEVERITY_CRITICAL
from ..state import BreakingChange, ReviewComment, ReviewState

log = structlog.get_logger()
settings = get_settings()


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

    # Handle exceptions
    if isinstance(db_result, Exception):
        log.error("finalize_review.db_failed", error=str(db_result))
        db_result = {"status": "error", "error": str(db_result)}
    if isinstance(slack_result, Exception):
        log.error("finalize_review.slack_failed", error=str(slack_result))
        slack_result = {"status": "error", "error": str(slack_result)}

    log.info("finalize_review.complete", pr=ctx.pr_number, db=db_result.get("status"), slack=slack_result.get("status"))

    return {"db_result": db_result, "slack_result": slack_result}


async def _save_to_db(ctx, breaking: list[BreakingChange], comments: list[ReviewComment], file_diffs: list, skip: bool, skip_reason: str | None) -> dict:
    """Save review results to database via API."""
    if not settings.API_BASE_URL:
        return {"status": "skipped", "reason": "API_BASE_URL not configured"}

    payload = {
        "owner": ctx.owner,
        "repo": ctx.repo,
        "pr_number": ctx.pr_number,
        "installation_id": ctx.installation_id,
        "pr_title": ctx.title,
        "pr_author": ctx.author,
        "base_branch": ctx.base_branch,
        "head_branch": ctx.head_branch,
        "status": "skipped" if skip else "completed",
        "skip_reason": skip_reason,
        "total_files": len(file_diffs),
        "breaking_changes": [_serialize_breaking(bc) for bc in breaking],
        "comments": [_serialize_comment(c) for c in comments],
    }

    client = httpx.AsyncClient(timeout=30)
    try:
        resp = await client.post(f"{settings.API_BASE_URL}/reviews/ingest", json=payload)
        resp.raise_for_status()
        review_id = resp.json().get("review_id")
        log.info("finalize_review.db_saved", review_id=review_id)
        return {"status": "success", "review_id": review_id}
    finally:
        await client.aclose()


async def _notify_slack(ctx, breaking: list[BreakingChange], comments: list[ReviewComment]) -> dict:
    """Send summary to Slack."""
    slack = SlackService()
    if not slack.is_configured():
        return {"status": "skipped", "reason": "Slack not configured"}

    summary = _build_summary(ctx, breaking)
    result = await slack.post_review_summary(
        pr_url=f"https://github.com/{ctx.owner}/{ctx.repo}/pull/{ctx.pr_number}",
        pr_title=ctx.title,
        author=ctx.author,
        summary=summary,
        breaking_count=len(breaking),
        comment_count=len(comments),
    )
    return result


def _build_summary(ctx, breaking: list[BreakingChange]) -> str:
    """Build summary message."""
    if not breaking:
        return f"✅ No breaking changes detected in PR #{ctx.pr_number}"

    critical = sum(1 for b in breaking if b.severity == SEVERITY_CRITICAL)
    affected = {c.file_path for b in breaking for c in b.affected_callers}

    return "\n".join([
        f"🔍 **Code Review Summary for PR #{ctx.pr_number}**",
        "",
        f"- 🚨 Critical: {critical}",
        f"- ⚠️ Warning: {len(breaking) - critical}",
        f"- 📁 Affected files: {len(affected)}",
        "",
        "**Top Issues:**",
        *[f"- `{b.entity_name}`: {b.change_detail}" for b in breaking[:3]],
        *([] if len(breaking) <= 3 else [f"- ... and {len(breaking) - 3} more"]),
    ])


def _serialize_breaking(bc: BreakingChange) -> dict:
    """Serialize BreakingChange for API."""
    return {
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
        "affected_callers": [
            {"file_path": c.file_path, "line_number": c.line, "call_text": c.call_text, "break_reason": c.break_reason}
            for c in bc.affected_callers
        ],
    }


def _serialize_comment(c: ReviewComment) -> dict:
    """Serialize ReviewComment for API."""
    return {
        "file_path": c.file,
        "line_number": c.line,
        "severity": c.severity,
        "message": c.message,
        "recommendation": c.recommendation,
        "affected_files": c.affected_files,
    }
