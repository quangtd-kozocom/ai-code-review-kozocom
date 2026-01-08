"""PR-related GitHub operations."""

import structlog

from .client import GitHubClient

log = structlog.get_logger()


class PRService(GitHubClient):
    """Pull Request related GitHub operations.

    Handles fetching PR details, files, and creating reviews.
    """

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Fetch files changed in a PR."""
        resp = await self._api_get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        resp.raise_for_status()
        return resp.json()

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch PR details including title and author."""
        resp = await self._api_get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        return resp.json()

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        comments: list[dict],
        event: str = "COMMENT",
    ) -> int:
        """Create a PR review with comments."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json={"body": body, "event": event, "comments": comments},
        )
        resp.raise_for_status()
        return resp.json()["id"]
