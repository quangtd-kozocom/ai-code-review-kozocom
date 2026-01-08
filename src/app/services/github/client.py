"""Base GitHub client with authentication and HTTP request handling.

Provides core functionality for GitHub API access using App installation tokens.
Uses async context manager pattern for proper resource management.
"""

import time
from contextlib import asynccontextmanager
from typing import Self

import httpx
import jwt
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ....core.constants import DEFAULT_HTTP_TIMEOUT
from ...config import get_settings

log = structlog.get_logger()

MAX_RETRIES = 3
RETRY_MIN_WAIT = 1
RETRY_MAX_WAIT = 10


def _is_retryable_status(response: httpx.Response) -> bool:
    """Check if response status code is retryable (5xx errors)."""
    return response.status_code >= 500


class GitHubClient:
    """Base GitHub API client using App installation tokens.

    Handles authentication, token refresh, and HTTP requests with retry logic.

    Usage with async context manager:
        async with GitHubClient(installation_id) as client:
            resp = await client._api_get("/repos/owner/repo")

    Or use the factory function:
        async with create_github_client(installation_id) as client:
            ...
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, installation_id: int) -> None:
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

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *_) -> None:
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

    async def get_installation_token(self) -> str:
        """Get installation access token (public wrapper)."""
        return await self._get_token()

    async def _api_get(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make authenticated GET request."""
        token = await self._get_token()
        return await self._request(
            "GET", f"{self.BASE_URL}{endpoint}", headers=self._headers(token), **kwargs
        )

    async def _api_post(self, endpoint: str, json: dict) -> httpx.Response:
        """Make authenticated POST request."""
        token = await self._get_token()
        return await self._request(
            "POST", f"{self.BASE_URL}{endpoint}", headers=self._headers(token), json=json
        )


@asynccontextmanager
async def create_github_client(installation_id: int):
    """Async context manager factory for GitHubClient.

    Usage:
        async with create_github_client(installation_id) as client:
            token = await client.get_installation_token()
    """
    client = GitHubClient(installation_id)
    try:
        yield client
    finally:
        await client.close()
