import time

import httpx
import jwt
import structlog

from ..config import get_settings

log = structlog.get_logger()


class GitHubService:
    """GitHub API client using App installation tokens."""

    BASE_URL = "https://api.github.com"

    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self.settings = get_settings()
        self._token: str | None = None
        self._token_expires: float = 0

    async def _get_token(self) -> str:
        """Get or refresh installation access token."""
        if self._token and time.time() < self._token_expires:
            return self._token

        # Create JWT
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": self.settings.GITHUB_APP_ID,
        }
        jwt_token = jwt.encode(payload, self.settings.GITHUB_PRIVATE_KEY, algorithm="RS256")

        # Exchange for installation token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["token"]
            self._token_expires = time.time() + 3500  # ~1 hour
            return self._token

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Fetch files changed in a PR."""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch PR details including title and author."""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
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
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={"body": body, "event": event, "comments": comments},
            )
            resp.raise_for_status()
            return resp.json()["id"]
