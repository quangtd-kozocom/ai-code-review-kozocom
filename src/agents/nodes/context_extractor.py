import fnmatch

import structlog

from ...app.services.github import GitHubService
from ...core.constants import IGNORE_PATTERNS, get_language_or_none
from ..state import FileChange, GraphState

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Fetch PR files and extract relevant changes."""
    ctx = state["context"]
    log.info("Context extractor started", pr=ctx.pr_number, repo=f"{ctx.owner}/{ctx.repo}")

    github = GitHubService(ctx.installation_id)

    raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    files = []
    for f in raw_files:
        if _should_ignore(f["filename"]):
            log.debug("Ignoring file", filename=f["filename"])
            continue

        files.append(
            FileChange(
                filename=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch", ""),
                language=get_language_or_none(f["filename"]),
            )
        )

    log.info("Extracted files", count=len(files), pr=ctx.pr_number)
    return {"files": files}


def _should_ignore(filename: str) -> bool:
    """Check if file should be ignored based on patterns."""
    return any(fnmatch.fnmatch(filename, p) for p in IGNORE_PATTERNS)
