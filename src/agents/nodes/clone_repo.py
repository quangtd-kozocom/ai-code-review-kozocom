"""Clone repo node - shallow clone for local search.

Requires git to be installed.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

import structlog

from ...app.services.github import create_github_service
from ..constants import CLONE_BLOB_LIMIT, CLONE_DEPTH
from ..state import ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Clone repository for local search operations.

    Uses shallow clone with sparse checkout for efficiency:
    - --depth 1: Only latest commit
    - --filter=blob:limit=1m: Skip large files
    - --single-branch: Only the PR branch

    Args:
        state: Current workflow state with pr_context.

    Returns:
        State updates with repo_path.
    """
    if state.get("skip_review"):
        log.debug("clone_repo.skipped", reason="skip_review is True")
        return {}

    ctx = state["pr_context"]

    log.info(
        "clone_repo.started",
        owner=ctx.owner,
        repo=ctx.repo,
        branch=ctx.head_branch,
        depth=CLONE_DEPTH,
        blob_limit=CLONE_BLOB_LIMIT,
    )

    # Create temp directory with identifiable name
    repo_path = Path(tempfile.mkdtemp(prefix=f"review-{ctx.repo}-{ctx.pr_number}-"))

    log.debug("clone_repo.temp_dir_created", path=str(repo_path))

    try:
        # Get installation token for auth
        async with create_github_service(ctx.installation_id) as github:
            token = await github.get_installation_token()

        log.debug("clone_repo.token_obtained")

        # Clone with optimizations
        clone_url = f"https://x-access-token:{token}@github.com/{ctx.owner}/{ctx.repo}.git"

        clone_cmd = [
            "git", "clone",
            "--depth", str(CLONE_DEPTH),
            f"--filter=blob:limit={CLONE_BLOB_LIMIT}",
            "--single-branch",
            "--branch", ctx.head_branch,
            clone_url,
            str(repo_path),
        ]

        log.debug(
            "clone_repo.executing",
            command="git clone --depth 1 --filter=blob:limit=1m --single-branch ...",
        )

        process = await asyncio.create_subprocess_exec(
            *clone_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            log.error(
                "clone_repo.failed",
                error=error_msg,
                return_code=process.returncode,
            )
            raise RuntimeError(f"Git clone failed: {error_msg}")

        # Get repo size for logging
        total_size = sum(f.stat().st_size for f in repo_path.rglob("*") if f.is_file())
        file_count = sum(1 for f in repo_path.rglob("*") if f.is_file())

        log.info(
            "clone_repo.complete",
            path=str(repo_path),
            size_mb=round(total_size / 1024 / 1024, 2),
            file_count=file_count,
        )

        return {"repo_path": str(repo_path)}

    except Exception as e:
        # Cleanup on failure
        log.error(
            "clone_repo.error",
            error=str(e),
            path=str(repo_path),
            cleaning_up=True,
        )
        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)
            log.info("clone_repo.cleanup_on_error", path=str(repo_path))
        raise


async def cleanup_repo(repo_path: str | None) -> None:
    """Remove cloned repository.

    Should be called after workflow completes or on error.

    Args:
        repo_path: Path to the cloned repository.
    """
    if not repo_path:
        log.debug("cleanup_repo.skipped", reason="no repo_path provided")
        return

    path = Path(repo_path)
    if path.exists():
        log.info(
            "cleanup_repo.removing",
            path=repo_path,
            exists=True,
        )
        shutil.rmtree(path, ignore_errors=True)

        # Verify deletion
        if path.exists():
            log.warning("cleanup_repo.failed", path=repo_path, still_exists=True)
        else:
            log.info("cleanup_repo.success", path=repo_path)
    else:
        log.debug("cleanup_repo.skipped", path=repo_path, reason="path does not exist")
