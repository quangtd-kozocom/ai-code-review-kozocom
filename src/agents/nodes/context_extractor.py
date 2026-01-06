"""Context extractor node - loads repository config and PR file changes."""

import re

import structlog

from ...app.services.github import GitHubService
from ...ast.models import FunctionInfo
from ...ast.parser import get_code_parser
from ...core.config import ReviewerConfig
from ...core.constants import get_language_or_none
from ...rag.config import get_rag_settings
from ...rag.retriever import get_retriever
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

    # Try to enrich files with RAG context (graceful degradation)
    try:
        files = await _enrich_files_with_rag(files, ctx, github)
    except Exception as e:
        log.warning("context_extractor.rag_enrichment_failed", error=str(e))

    log.info(
        "context_extractor.completed",
        total=len(raw_files),
        included=len(files),
        ignored=ignored_count,
    )

    return {"files": files, "repo_config": config}


async def _enrich_files_with_rag(
    files: list[FileChange],
    ctx: PRContext,
    github: GitHubService,
) -> list[FileChange]:
    """Enrich files with RAG context. Returns original files if RAG unavailable."""
    if not get_rag_settings().pinecone_api_key:
        log.debug("context_extractor.rag_not_configured")
        return files

    parser, retriever = get_code_parser(), get_retriever()
    pr_details = await github.get_pr_details(ctx.owner, ctx.repo, ctx.pr_number)
    head_sha = pr_details.get("head", {}).get("sha", "HEAD")
    enriched_count = 0

    for file in files:
        if file.status != "modified" or not parser.detect_language(file.filename):
            continue

        try:
            content = await github.get_file_raw(ctx.owner, ctx.repo, file.filename, head_sha)
            if not content:
                continue

            ast_info = parser.get_ast_info(file.filename, content)
            if not ast_info:
                continue

            changed_funcs = _identify_changed_entities(ast_info, file.patch)
            related = [
                result
                for func in changed_funcs[:3]
                for result in retriever.retrieve_for_function(
                    ctx.owner, ctx.repo, func.name, func.signature, file.filename
                )
            ]

            if related:
                enriched_count += 1
                log.debug("context_extractor.enriched_file", file=file.filename, count=len(related))

        except Exception as e:
            log.debug("context_extractor.file_enrichment_failed", file=file.filename, error=str(e))

    log.info("context_extractor.rag_enrichment_complete", enriched_count=enriched_count)
    return files


def _identify_changed_entities(ast_info, patch: str) -> list[FunctionInfo]:
    """Identify functions containing changed lines from diff."""
    changed_lines = set(_parse_diff_lines(patch))
    return [
        func
        for func in ast_info.functions
        if changed_lines & set(range(func.start_line, func.end_line + 1))
    ]


def _parse_diff_lines(patch: str) -> list[int]:
    """Extract new file line numbers from diff hunks."""
    return [
        line
        for match in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch)
        for line in range(int(match.group(1)), int(match.group(1)) + int(match.group(2) or 1))
    ]
