"""Slack reporter node - sends review notifications to Slack."""

from collections import Counter

import structlog

from ...app.services.slack import SlackService
from ..state import GraphState, ReviewComment

log = structlog.get_logger()


def _build_pr_url(owner: str, repo: str, pr_number: int) -> str:
    return f"https://github.com/{owner}/{repo}/pull/{pr_number}"


def _count_severities(comments: list[ReviewComment]) -> dict[str, int]:
    counts = Counter(c.severity for c in comments)
    return {
        "critical": counts.get("critical", 0),
        "warning": counts.get("warning", 0),
    }


async def run(state: GraphState) -> dict:
    """Send review notification to Slack."""
    ctx = state["context"]
    comments = state.get("final_comments", [])
    summary = state.get("summary", "")

    log.info("slack_reporter.started", pr=ctx.pr_number)

    if not comments:
        log.debug("slack_reporter.skipped", reason="no_findings")
        return {}

    counts = _count_severities(comments)
    slack = SlackService()

    await slack.send_review_notification(
        pr_number=ctx.pr_number,
        repo=f"{ctx.owner}/{ctx.repo}",
        pr_url=_build_pr_url(ctx.owner, ctx.repo, ctx.pr_number),
        summary=summary,
        critical_count=counts["critical"],
        warning_count=counts["warning"],
    )

    log.info("slack_reporter.sent", pr=ctx.pr_number)
    return {}
