"""
Context extractor node - loads config and PR files.

Responsible for:
1. Loading repository configuration
2. Checking auto-review settings
3. Filtering files by ignore patterns
"""

import structlog

from ...app.services.github import GitHubService
from ...core.config import create_config_service
from ...core.constants import get_language_or_none
from ..state import FileChange, GraphState

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """
    Extract context: load config and PR files.

    Resolution order for config:
    1. Redis cache
    2. .reviewer.yaml from GitHub
    3. Database stored config
    4. Default values

    Returns:
        dict with 'files' and 'repo_config'
    """
    ctx = state["context"]
    log.info("Context extractor started", pr=ctx.pr_number, repo=f"{ctx.owner}/{ctx.repo}")

    github = GitHubService(ctx.installation_id)

    # Load configuration
    config_service = await create_config_service(github)
    config = await config_service.get_config(ctx.owner, ctx.repo)

    log.info(
        "Config loaded",
        owner=ctx.owner,
        repo=ctx.repo,
        profile=config.reviews.profile,
        ignore_patterns=len(config.ignore),
        path_instructions=len(config.reviews.path_instructions),
    )

    # Check if should auto-review
    if not config.should_auto_review(
        title=ctx.title,
        author=ctx.author,
        base_branch=ctx.base_branch,
        is_draft=ctx.is_draft,
    ):
        log.info(
            "PR skipped by auto-review settings",
            pr=ctx.pr_number,
            title=ctx.title,
            author=ctx.author,
        )
        return {
            "files": [],
            "repo_config": config,
        }

    # Get PR files
    raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    # Filter and convert files
    files: list[FileChange] = []
    ignored_count = 0

    for f in raw_files:
        filename = f["filename"]

        # Apply ignore patterns from config
        if config.should_ignore(filename):
            log.debug("File ignored by config", file=filename)
            ignored_count += 1
            continue

        files.append(
            FileChange(
                filename=filename,
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch", ""),
                language=get_language_or_none(filename),
            )
        )

    log.info(
        "Context extracted",
        total_files=len(raw_files),
        filtered_files=len(files),
        ignored_files=ignored_count,
        pr=ctx.pr_number,
    )

    return {
        "files": files,
        "repo_config": config,
    }
