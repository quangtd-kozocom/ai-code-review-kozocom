"""Comment and review operations for GitHub."""

import structlog

from .client import GitHubClient

log = structlog.get_logger()


class CommentService(GitHubClient):
    """Comment and review related GitHub operations.

    Handles creating issue comments, review comments, and replies.
    """

    async def create_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> int:
        """Create an issue comment on a PR (not a review comment)."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> int:
        """Create a comment on an issue or PR."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        comment_id = resp.json()["id"]
        log.info("Issue comment created", comment_id=comment_id)
        return comment_id

    async def get_review_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
    ) -> dict | None:
        """Get a single review comment by ID."""
        resp = await self._api_get(f"/repos/{owner}/{repo}/pulls/comments/{comment_id}")

        if resp.status_code == 404:
            log.warning("Review comment not found", comment_id=comment_id)
            return None

        resp.raise_for_status()
        return resp.json()

    async def create_review_comment_reply(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
        body: str,
    ) -> int:
        """Reply to a review comment."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json={"body": body, "in_reply_to": comment_id},
        )
        resp.raise_for_status()
        reply_id = resp.json()["id"]
        log.info("Review comment reply created", reply_id=reply_id)
        return reply_id
