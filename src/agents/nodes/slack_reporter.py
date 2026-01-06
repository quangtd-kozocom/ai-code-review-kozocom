import structlog

from ...app.services.slack import SlackService
from ..state import GraphState

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Send notification to Slack."""
    ctx = state["context"]
    comments = state.get("final_comments", [])
    summary = state.get("summary", "")
    log.info("Slack reporter started", pr=ctx.pr_number)

    # Count by severity
    critical = sum(1 for c in comments if c.severity == "critical")
    warning = sum(1 for c in comments if c.severity == "warning")

    # Only notify if there are findings
    if not comments:
        log.debug("No findings, skipping Slack notification")
        return {}

    # Build PR URL
    pr_url = f"https://github.com/{ctx.owner}/{ctx.repo}/pull/{ctx.pr_number}"

    # Send notification
    slack = SlackService()
    await slack.send_review_notification(
        pr_number=ctx.pr_number,
        repo=f"{ctx.owner}/{ctx.repo}",
        pr_url=pr_url,
        summary=summary,
        critical_count=critical,
        warning_count=warning,
    )

    return {}
