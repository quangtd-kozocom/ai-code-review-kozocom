"""File content operations for GitHub."""

import structlog
from httpx import HTTPStatusError

from .client import GitHubClient

log = structlog.get_logger()


class FileService(GitHubClient):
    """File content related GitHub operations.

    Handles fetching raw file content and content at specific refs.
    """

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
            # Get PR head SHA
            pr_resp = await self._api_get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
            pr_resp.raise_for_status()
            ref = pr_resp.json()["head"]["sha"]

            # Get file content
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
