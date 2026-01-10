"""Publish summary node - sends final summary to Slack/Jira."""

import structlog

from ...app.services.slack import SlackService
from ..constants import SEVERITY_CRITICAL
from ..state import ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Publish final review summary to Slack and Jira.

    Called once after all files are processed to send
    a consolidated summary.

    Args:
        state: Current workflow state with all results.

    Returns:
        State updates with slack_result and jira_result.
    """
    ctx = state.get("pr_context")
    all_comments = state.get("all_comments", [])
    all_breaking = state.get("all_breaking_changes", [])

    if not ctx:
        log.warning("publish_summary.skipped", reason="no pr_context")
        return {}

    log.info(
        "publish_summary.started",
        pr=ctx.pr_number,
        repo=f"{ctx.owner}/{ctx.repo}",
        total_comments=len(all_comments),
        total_breaking_changes=len(all_breaking),
    )

    results: dict = {
        "slack_result": None,
        "jira_result": None,
    }

    # Build summary message
    summary = _build_summary(ctx, all_breaking)

    # Post to Slack
    try:
        slack = SlackService()
        if slack.is_configured():
            log.debug("publish_summary.posting_to_slack")

            slack_result = await slack.post_review_summary(
                pr_url=f"https://github.com/{ctx.owner}/{ctx.repo}/pull/{ctx.pr_number}",
                pr_title=ctx.title,
                author=ctx.author,
                summary=summary,
                breaking_count=len(all_breaking),
                comment_count=len(all_comments),
            )
            results["slack_result"] = slack_result

            log.info(
                "publish_summary.slack_posted",
                status=slack_result.get("status"),
            )
        else:
            log.debug("publish_summary.slack_not_configured")
    except Exception as e:
        log.error(
            "publish_summary.slack_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        results["slack_result"] = {"status": "error", "error": str(e)}

    # TODO: Add Jira integration
    # try:
    #     jira = JiraService()
    #     if jira.is_configured():
    #         ...
    # except Exception as e:
    #     ...

    slack_status = "skipped"
    if results.get("slack_result"):
        slack_status = results["slack_result"].get("status", "unknown")

    log.info(
        "publish_summary.complete",
        pr=ctx.pr_number,
        slack_status=slack_status,
    )

    return results


def _build_summary(ctx, breaking: list) -> str:
    """Build a summary message for Slack."""
    if not breaking:
        return f"✅ No breaking changes detected in PR #{ctx.pr_number}"

    critical = sum(1 for b in breaking if b.severity == SEVERITY_CRITICAL)
    warning = len(breaking) - critical

    affected_files = set()
    for b in breaking:
        for c in b.affected_callers:
            affected_files.add(c.file_path)

    lines = [
        f"🔍 **Code Review Summary for PR #{ctx.pr_number}**",
        "",
        "**Breaking Changes Detected:**",
        f"- 🚨 Critical: {critical}",
        f"- ⚠️ Warning: {warning}",
        f"- 📁 Affected files: {len(affected_files)}",
        "",
        "**Top Issues:**",
    ]

    for b in breaking[:3]:
        lines.append(f"- `{b.entity_name}`: {b.change_detail}")

    if len(breaking) > 3:
        lines.append(f"- ... and {len(breaking) - 3} more")

    return "\n".join(lines)
