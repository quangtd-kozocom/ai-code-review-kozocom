"""Extract diff node - fetches PR files from GitHub."""

from fnmatch import fnmatch

import structlog

from ...analysis.diff_extractor import DiffExtractor
from ...app.services.github import create_github_service
from ..constants import CODE_EXTENSIONS
from ..state import FileDiff, ReviewState

log = structlog.get_logger()


def _should_review_file(file_path: str, include_patterns: list[str], exclude_patterns: list[str]) -> bool:
    """Check if file should be reviewed based on config patterns."""
    # Check exclude first
    for pattern in exclude_patterns:
        if fnmatch(file_path, pattern):
            return False

    # If include patterns exist, file must match one
    if include_patterns:
        return any(fnmatch(file_path, p) for p in include_patterns)

    return True


async def run(state: ReviewState) -> dict:
    """Extract and parse PR diff from GitHub.

    Fetches all changed files in the PR with their content
    for both base and head branches.

    Args:
        state: Current workflow state with pr_context.

    Returns:
        State updates with file_diffs.
    """
    ctx = state["pr_context"]
    config = state.get("config")

    log.info(
        "extract_diff.started",
        owner=ctx.owner,
        repo=ctx.repo,
        pr=ctx.pr_number,
        base_branch=ctx.base_branch,
        head_branch=ctx.head_branch,
    )

    async with create_github_service(ctx.installation_id) as github:
        extractor = DiffExtractor(github)

        diffs = await extractor.extract(
            ctx.owner,
            ctx.repo,
            ctx.pr_number,
            ctx.base_branch,
            ctx.head_branch,
        )

        # Convert to our FileDiff dataclass
        file_diffs = [
            FileDiff(
                file_path=d.file_path,
                status=d.status.value,
                base_content=d.base_content,
                head_content=d.head_content,
                patch=d.patch,
                language=d.language,
            )
            for d in diffs
        ]

    total_files = len(file_diffs)

    # Filter out non-code files
    file_diffs = [
        f for f in file_diffs
        if any(f.file_path.endswith(ext) for ext in CODE_EXTENSIONS)
    ]

    code_files = len(file_diffs)

    # Apply config patterns if available
    if config:
        include_patterns = config.include_patterns or []
        exclude_patterns = config.exclude_patterns or []
        file_diffs = [
            f for f in file_diffs
            if _should_review_file(f.file_path, include_patterns, exclude_patterns)
        ]
        log.info(
            "extract_diff.config_filter",
            before=code_files,
            after=len(file_diffs),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )

    if not file_diffs:
        log.info(
            "extract_diff.no_code_files",
            total_files=total_files,
            filtered_out=total_files,
        )
        return {
            "file_diffs": [],
            "skip_review": True,
            "skip_reason": "No code files to review",
        }

    log.info(
        "extract_diff.complete",
        total_files=total_files,
        code_files=len(file_diffs),
        filtered_out=total_files - len(file_diffs),
        files=[f.file_path for f in file_diffs],
    )

    return {
        "file_diffs": file_diffs,
        "pending_files": file_diffs.copy(),
        "skip_review": False,
    }
