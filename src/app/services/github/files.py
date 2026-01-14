"""File content operations for GitHub."""

import structlog
from httpx import HTTPStatusError

from .client import GitHubClient

log = structlog.get_logger()


class FileService(GitHubClient):
    """File content related GitHub operations.

    Handles fetching raw file content and content at specific refs.
    """

    _tree_cache: dict[str, list[str]]

    def __init__(self, installation_id: int) -> None:
        super().__init__(installation_id)
        self._tree_cache = {}

    async def get_file_raw(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "HEAD",
        *,
        resolve_path: bool = False,
    ) -> str | None:
        """Get raw file content from repository.

        Args:
            resolve_path: If True and direct path fails, search repo tree for matching filename.
        """
        token = await self._get_token()

        resp = await self._request(
            "GET",
            f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
            headers={**self._headers(token), "Accept": "application/vnd.github.raw+json"},
            params={"ref": ref},
        )

        if resp.status_code == 404:
            if resolve_path and "/" not in path:
                resolved = await self._resolve_path(owner, repo, path, ref)
                if resolved:
                    return await self.get_file_raw(owner, repo, resolved, ref)
            log.debug("file_not_found", path=path, ref=ref)
            return None

        resp.raise_for_status()
        return resp.text

    async def _resolve_path(
        self, owner: str, repo: str, filename: str, ref: str
    ) -> str | None:
        """Resolve filename to full path by searching repo tree."""
        cache_key = f"{owner}/{repo}:{ref}"
        if cache_key not in self._tree_cache:
            token = await self._get_token()
            resp = await self._request(
                "GET",
                f"{self.BASE_URL}/repos/{owner}/{repo}/git/trees/{ref}",
                headers=self._headers(token),
                params={"recursive": "1"},
            )
            if resp.status_code != 200:
                return None
            self._tree_cache[cache_key] = [
                item["path"] for item in resp.json().get("tree", []) if item["type"] == "blob"
            ]

        for path in self._tree_cache[cache_key]:
            if path.endswith(f"/{filename}") or path == filename:
                log.debug("path_resolved", filename=filename, resolved=path)
                return path
        return None

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
                headers={**self._headers(token), "Accept": "application/vnd.github.raw+json"},
                params={"ref": ref},
            )
            file_resp.raise_for_status()
            return self._format_code_context(file_resp.text, line, context_lines)

        except HTTPStatusError as e:
            log.error("file_fetch_failed", path=path, status=e.response.status_code)
            return None
        except Exception:
            log.exception("file_fetch_error", path=path)
            return None

    def _format_code_context(self, content: str, line: int, context_lines: int) -> str:
        """Format code with line numbers, highlighting target line."""
        lines = content.split("\n")
        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)

        return "\n".join(
            f"{'>>> ' if i == line else '    '}{i}: {code_line}"
            for i, code_line in enumerate(lines[start:end], start=start + 1)
        )
