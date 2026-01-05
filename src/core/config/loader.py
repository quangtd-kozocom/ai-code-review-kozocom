"""
Load configuration from GitHub repository.

Fetches and parses .reviewer.yaml from repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
import yaml

if TYPE_CHECKING:
    from ...app.services.github import GitHubService

log = structlog.get_logger()

CONFIG_FILENAME = ".reviewer.yaml"
CONFIG_FILENAME_ALT = ".reviewer.yml"


class ConfigLoader:
    """
    Load .reviewer.yaml from GitHub repository.
    """

    def __init__(self, github: GitHubService) -> None:
        """
        Initialize loader with GitHub service.

        Args:
            github: GitHubService instance for API calls.
        """
        self.github = github

    async def load(
        self,
        owner: str,
        repo: str,
        ref: str = "HEAD",
    ) -> dict[str, Any] | None:
        """
        Load and parse .reviewer.yaml from repository.

        Tries .reviewer.yaml first, then .reviewer.yml as fallback.

        Args:
            owner: Repository owner.
            repo: Repository name.
            ref: Git reference (branch/commit/tag).

        Returns:
            Parsed config dict, or None if file doesn't exist.
        """
        # Try primary filename
        content = await self._try_load_file(owner, repo, CONFIG_FILENAME, ref)

        # Try alternative filename
        if content is None:
            content = await self._try_load_file(owner, repo, CONFIG_FILENAME_ALT, ref)

        if content is None:
            log.debug(
                "No config file found",
                owner=owner,
                repo=repo,
                tried=[CONFIG_FILENAME, CONFIG_FILENAME_ALT],
            )
            return None

        # Parse YAML
        try:
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                log.warning(
                    "Config file is not a valid dict",
                    owner=owner,
                    repo=repo,
                )
                return None

            log.info(
                "Config loaded from repository",
                owner=owner,
                repo=repo,
            )
            return data

        except yaml.YAMLError as e:
            log.warning(
                "Invalid YAML in config file",
                owner=owner,
                repo=repo,
                error=str(e),
            )
            return None

    async def _try_load_file(
        self,
        owner: str,
        repo: str,
        filename: str,
        ref: str,
    ) -> str | None:
        """
        Try to load a specific config file.

        Args:
            owner: Repository owner.
            repo: Repository name.
            filename: Config filename to try.
            ref: Git reference.

        Returns:
            File content as string, or None if not found.
        """
        try:
            content = await self.github.get_file_raw(owner, repo, filename, ref)
            return content
        except Exception as e:
            log.debug(
                "Failed to load config file",
                owner=owner,
                repo=repo,
                filename=filename,
                error=str(e),
            )
            return None
