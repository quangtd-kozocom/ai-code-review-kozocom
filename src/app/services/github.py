import time
from types import TracebackType

import httpx
import jwt
import structlog
from httpx import HTTPStatusError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...core.constants import DEFAULT_HTTP_TIMEOUT
from ..config import get_settings

__all__ = ["GitHubService"]

log = structlog.get_logger()

MAX_RETRIES = 3
RETRY_MIN_WAIT = 1
RETRY_MAX_WAIT = 10


def _is_retryable_status(response: httpx.Response) -> bool:
    """Check if response status code is retryable (5xx errors)."""
    return response.status_code >= 500


class GitHubService:
    """GitHub API client using App installation tokens.

    Supports async context manager for proper resource management:
        async with GitHubService(installation_id) as gh:
            files = await gh.get_pr_files(owner, repo, pr_number)

    Or manual lifecycle management:
        gh = GitHubService(installation_id)
        try:
            files = await gh.get_pr_files(owner, repo, pr_number)
        finally:
            await gh.close()
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self.settings = get_settings()
        self._token: str | None = None
        self._token_expires: float = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if (client := self._client) is None or client.is_closed:
            self._client = client = httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT)
        return client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "GitHubService":
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context manager and close resources."""
        await self.close()

    def _headers(self, token: str) -> dict[str, str]:
        """Build common request headers."""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic for transient failures."""
        client = await self._get_client()
        resp = await client.request(method, url, headers=headers, **kwargs)

        if _is_retryable_status(resp):
            log.warning("Retryable server error", status=resp.status_code, url=url)
            resp.raise_for_status()

        return resp

    async def _get_token(self) -> str:
        """Get or refresh installation access token."""
        if self._token and time.time() < self._token_expires:
            return self._token

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": self.settings.GITHUB_APP_ID,
        }
        jwt_token = jwt.encode(payload, self.settings.GITHUB_PRIVATE_KEY, algorithm="RS256")

        resp = await self._request(
            "POST",
            f"{self.BASE_URL}/app/installations/{self.installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        self._token = token = resp.json()["token"]
        self._token_expires = time.time() + 3500
        return token

    async def _api_get(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make authenticated GET request."""
        token = await self._get_token()
        resp = await self._request(
            "GET", f"{self.BASE_URL}{endpoint}", headers=self._headers(token), **kwargs
        )
        return resp

    async def _api_post(self, endpoint: str, json: dict) -> httpx.Response:
        """Make authenticated POST request."""
        token = await self._get_token()
        resp = await self._request(
            "POST", f"{self.BASE_URL}{endpoint}", headers=self._headers(token), json=json
        )
        return resp

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

    async def create_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> int:
        """Create an issue comment on a PR (not a review comment)."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()["id"]

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

    async def get_file_content_at_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        path: str,
        line: int,
        context_lines: int = 5,
    ) -> str | None:
        """Get file content around a specific line at PR head."""
        token = await self._get_token()

        try:
            pr_resp = await self._api_get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
            pr_resp.raise_for_status()
            ref = pr_resp.json()["head"]["sha"]

            file_resp = await self._request(
                "GET",
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
            log.error("Failed to get file content", path=path, status=e.response.status_code)
            return None
        except Exception:
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
        """Create a comment on an issue or PR."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
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
        """Reply to a review comment."""
        resp = await self._api_post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json={"body": body, "in_reply_to": comment_id},
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
        """Get raw file content from repository."""
        token = await self._get_token()

        resp = await self._request(
            "GET",
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
