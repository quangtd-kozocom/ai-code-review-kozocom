import structlog
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from ...core.constants import SLACK_MESSAGE_CHAR_LIMIT
from ..config import Settings, get_settings

__all__ = ["SlackService"]

log = structlog.get_logger()


class SlackService:
    """Async Slack notification service."""

    def __init__(self) -> None:
        self.settings: Settings = get_settings()
        self.client: AsyncWebClient | None = None
        if self.settings.SLACK_BOT_TOKEN:
            self.client = AsyncWebClient(token=self.settings.SLACK_BOT_TOKEN)

    def is_configured(self) -> bool:
        """Check if Slack is configured."""
        return self.client is not None

    async def send_review_notification(
        self,
        pr_number: int,
        repo: str,
        pr_url: str,
        summary: str,
        critical_count: int = 0,
        warning_count: int = 0,
    ) -> bool:
        """Send a review notification to Slack.

        Args:
            pr_number: The pull request number.
            repo: The repository name (owner/repo format).
            pr_url: The URL to the pull request.
            summary: The review summary text.
            critical_count: Number of critical issues found.
            warning_count: Number of warning issues found.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        if not self.client:
            log.debug("Slack not configured, skipping notification")
            return False

        # Build message blocks
        emoji = "🔴" if critical_count > 0 else "🟢"
        blocks: list[dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} AI Review: {repo} #{pr_number}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary[:SLACK_MESSAGE_CHAR_LIMIT],  # Slack has character limits
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🔴 Critical: {critical_count} | 🟡 Warning: {warning_count}",
                    }
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View PR"},
                        "url": pr_url,
                    }
                ],
            },
        ]

        try:
            await self.client.chat_postMessage(
                channel=self.settings.SLACK_CHANNEL,
                blocks=blocks,
                text=f"AI Review for {repo} #{pr_number}",
            )
            log.info("Slack notification sent", pr=pr_number, repo=repo)
            return True
        except SlackApiError as e:
            log.error(
                "Slack notification failed",
                error=str(e),
                response=e.response.data if e.response else None,
                pr=pr_number,
                repo=repo,
            )
            return False

    async def post_review_summary(
        self,
        pr_url: str,
        pr_title: str,
        author: str,
        summary: str,
        breaking_count: int = 0,
        comment_count: int = 0,
    ) -> dict:
        """Post a review summary to Slack.

        Args:
            pr_url: URL to the pull request.
            pr_title: Title of the PR.
            author: PR author username.
            summary: Review summary text.
            breaking_count: Number of breaking changes found.
            comment_count: Total number of comments posted.

        Returns:
            Result dict with status and optional error.
        """
        if not self.client:
            return {"status": "skipped", "reason": "Slack not configured"}

        # Determine status styling
        if breaking_count > 0:
            status_emoji = ":red_circle:"
            status_label = "Breaking Changes Found"
        else:
            status_emoji = ":white_check_mark:"
            status_label = "Review Passed"

        blocks: list[dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} AI Code Review Complete",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{pr_url}|{pr_title}>*\n:bust_in_silhouette: *Author:* {author}",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔗 View PR", "emoji": True},
                    "url": pr_url,
                    "style": "primary",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary[:SLACK_MESSAGE_CHAR_LIMIT],
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"{status_emoji} *Status:* {status_label}"},
                    {"type": "mrkdwn", "text": f":speech_balloon: *{comment_count}* Comments"},
                    {"type": "mrkdwn", "text": ":robot_face: _AI Code Reviewer_"},
                ],
            },
        ]

        try:
            await self.client.chat_postMessage(
                channel=self.settings.SLACK_CHANNEL,
                blocks=blocks,
                text=f"Code Review: {pr_title}",
            )
            log.info("Slack review summary posted", pr_url=pr_url)
            return {"status": "success"}
        except SlackApiError as e:
            log.error("Slack review summary failed", error=str(e))
            return {"status": "error", "error": str(e)}
