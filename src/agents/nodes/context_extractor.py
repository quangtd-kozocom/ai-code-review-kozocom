"""Context extractor node - loads repository config and PR file changes.

Refactored to use RAGEnricher service for file enrichment.
"""

import structlog

from ...app.services.github import GitHubService
from ...core.config import ReviewerConfig
from ...core.constants import get_language_or_none
from ..services.rag_enricher import RAGEnricher
from ..state import FileChange, GraphState, PRContext

log = structlog.get_logger()


def _convert_to_file_change(raw: dict) -> FileChange:
    """Convert a raw GitHub file dict to FileChange model."""
    return FileChange(
        filename=raw["filename"],
        status=raw["status"],
        additions=raw["additions"],
        deletions=raw["deletions"],
        patch=raw.get("patch", ""),
        language=get_language_or_none(raw["filename"]),
    )


def _filter_files(
    raw_files: list[dict],
    config: ReviewerConfig,
) -> tuple[list[FileChange], int]:
    """Filter and convert raw files, returning (files, ignored_count)."""
    files: list[FileChange] = []
    ignored = 0

    for raw in raw_files:
        if config.should_ignore(raw["filename"]):
            ignored += 1
            continue
        files.append(_convert_to_file_change(raw))

    return files, ignored


def _should_skip_review(config: ReviewerConfig, ctx: PRContext) -> bool:
    """Check if PR should be skipped based on auto-review settings."""
    return not config.should_auto_review(
        title=ctx.title,
        author=ctx.author,
        base_branch=ctx.base_branch,
        is_draft=ctx.is_draft,
    )


async def run(state: GraphState) -> dict:
    """Load repository config and extract PR file changes."""
    ctx = state["context"]
    log.info("context_extractor.started", pr=ctx.pr_number, repo=f"{ctx.owner}/{ctx.repo}")

    github = GitHubService(ctx.installation_id)

    try:
        # Load configuration
        from ...core.config import create_config_service

        config_service = await create_config_service(github)
        config = await config_service.get_config(ctx.owner, ctx.repo)

        log.info(
            "context_extractor.config_loaded",
            profile=config.reviews.profile,
            ignore_patterns=len(config.ignore),
            path_instructions=len(config.reviews.path_instructions),
        )

        # Check auto-review settings
        if _should_skip_review(config, ctx):
            log.info(
                "context_extractor.skipped",
                reason="auto_review_settings",
                pr=ctx.pr_number,
                author=ctx.author,
            )
            return {"files": [], "repo_config": config}

        # Fetch and filter files
        raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)
        files, ignored_count = _filter_files(raw_files, config)

        # Enrich files with RAG context using dedicated service
        enricher = RAGEnricher(github)
        try:
            files = await enricher.enrich_files(files, ctx)
        except Exception as e:
            log.warning("context_extractor.rag_enrichment_failed", error=str(e))
            # Continue with non-enriched files

        log.info(
            "context_extractor.completed",
            total=len(raw_files),
            included=len(files),
            ignored=ignored_count,
        )

        return {"files": files, "repo_config": config}

    finally:
        await github.close()
