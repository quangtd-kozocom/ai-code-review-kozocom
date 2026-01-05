import time

import httpx
import jwt
import structlog
from httpx import HTTPStatusError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

log = structlog.get_logger()

# Retry decorator for transient errors
_retry_on_transient = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)


class GitHubService:
    """GitHub API client using App installation tokens."""

    BASE_URL = "https://api.github.com"

    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self.settings = get_settings()
        self._token: str | None = None
        self._token_expires: float = 0

    def _headers(self, token: str) -> dict[str, str]:
        """Build common request headers."""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

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
                headers=self._headers(token),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch PR details including title and author."""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self._headers(token),
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
                headers=self._headers(token),
                json={"body": body, "event": event, "comments": comments},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def create_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> int:
        """Create an issue comment on a PR (not a review comment)."""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments",
                headers=self._headers(token),
                json={"body": body},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    # ============== NEW METHODS FOR ON-DEMAND COMMANDS ==============

    async def get_review_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
    ) -> dict | None:
        """
        Get a single review comment by ID.

        Args:
            owner: Repository owner
            repo: Repository name
            comment_id: Review comment ID

        Returns:
            Comment data dict or None if not found
        """
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/comments/{comment_id}",
                headers=self._headers(token),
            )

            if resp.status_code == 404:
                log.warning("Review comment not found", comment_id=comment_id)
                return None

            resp.raise_for_status()
            return resp.json()

    async def get_file_content_at_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        path: str,
        line: int,
        context_lines: int = 5,
    ) -> str | None:
        """
        Get file content around a specific line at PR head.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            path: File path in the repository
            line: Target line number
            context_lines: Number of lines before/after to include

        Returns:
            Formatted code context with line numbers, or None on error
        """
        token = await self._get_token()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get PR to find head SHA
                pr_resp = await client.get(
                    f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                    headers=self._headers(token),
                )
                pr_resp.raise_for_status()
                ref = pr_resp.json()["head"]["sha"]

                # Get file content at that ref
                file_resp = await client.get(
                    f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                    headers={
                        **self._headers(token),
                        "Accept": "application/vnd.github.raw+json",
                    },
                    params={"ref": ref},
                )
                file_resp.raise_for_status()

                return self._format_code_context(file_resp.text, line, context_lines)

        except HTTPStatusError as e:
            log.error(
                "Failed to get file content",
                path=path,
                status=e.response.status_code,
            )
            return None
        except Exception as _e:
            log.exception("Unexpected error getting file content", path=path)
            return None

    def _format_code_context(self, content: str, line: int, context_lines: int) -> str:
        """Format code with line numbers, highlighting target line."""
        lines = content.split("\n")
        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)

        result = []
        for i, code_line in enumerate(lines[start:end], start=start + 1):
            marker = ">>> " if i == line else "    "
            result.append(f"{marker}{i}: {code_line}")

        return "\n".join(result)

    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> int:
        """
        Create a comment on an issue or PR.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue/PR number
            body: Comment body text

        Returns:
            Created comment ID
        """
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                headers=self._headers(token),
                json={"body": body},
            )
            resp.raise_for_status()
            comment_id = resp.json()["id"]
            log.info("Issue comment created", comment_id=comment_id)
            return comment_id

    async def create_review_comment_reply(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
        body: str,
    ) -> int:
        """
        Reply to a review comment.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            comment_id: Parent comment ID to reply to
            body: Reply body text

        Returns:
            Created reply comment ID
        """
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                headers=self._headers(token),
                json={
                    "body": body,
                    "in_reply_to": comment_id,
                },
            )
            resp.raise_for_status()
            reply_id = resp.json()["id"]
            log.info("Review comment reply created", reply_id=reply_id)
            return reply_id

    async def get_file_raw(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "HEAD",
    ) -> str | None:
        """
        Get raw file content from repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in the repository
            ref: Git reference (branch/commit/tag), defaults to HEAD

        Returns:
            File content as string, or None if not found
        """
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                headers={
                    **self._headers(token),
                    "Accept": "application/vnd.github.raw+json",
                },
                params={"ref": ref},
            )

            if resp.status_code == 404:
                log.debug("File not found", path=path, ref=ref)
                return None

            resp.raise_for_status()
            return resp.text
