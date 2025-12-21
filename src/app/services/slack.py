import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import get_settings

log = structlog.get_logger()


class SlackService:
    """Slack notification service."""

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        if self.settings.SLACK_BOT_TOKEN:
            self.client = WebClient(token=self.settings.SLACK_BOT_TOKEN)

    def send_review_notification(
        self,
        pr_number: int,
        repo: str,
        pr_url: str,
        summary: str,
        critical_count: int = 0,
        warning_count: int = 0,
    ) -> bool:
        """Send a review notification to Slack."""
        if not self.client:
            log.debug("Slack not configured, skipping notification")
            return False

        # Build message blocks
        emoji = "🔴" if critical_count > 0 else "🟢"
        blocks = [
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
                    "text": summary[:2000],  # Slack has character limits
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
            self.client.chat_postMessage(
                channel=self.settings.SLACK_CHANNEL,
                blocks=blocks,
                text=f"AI Review for {repo} #{pr_number}",
            )
            log.info("Slack notification sent", pr=pr_number, repo=repo)
            return True
        except SlackApiError as e:
            log.error("Slack notification failed", error=str(e))
            return False
