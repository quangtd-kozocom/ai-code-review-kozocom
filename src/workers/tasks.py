"""Celery background tasks.

Note on async handling:
    Celery workers are synchronous by default. We use `asyncio.run()` to execute
    async code within sync task functions. While this creates a new event loop per
    task invocation, this is the standard and recommended pattern for Celery + async.
    Alternatives like shared event loops add complexity and potential thread-safety
    issues without significant performance benefits for I/O-bound tasks.
"""

import asyncio
from typing import Any

import structlog

from ..agents import PRContext, run_review
from ..app.services.github import GitHubService
from ..chat.context import CommandContext
from ..chat.handler import CommandHandler
from ..chat.parser import parse_command
from ..core.constants import CELERY_COMMAND_RETRY_COUNTDOWN, CELERY_PR_RETRY_COUNTDOWN
from .celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3)
def review_pr(self, owner: str, repo: str, pr_number: int, installation_id: int) -> dict[str, Any]:
    """Run the review workflow for a PR."""
    try:
        return asyncio.run(_run_review(owner, repo, pr_number, installation_id))
    except Exception as e:
        log.exception("Review failed", owner=owner, repo=repo, pr=pr_number)
        raise self.retry(exc=e, countdown=CELERY_PR_RETRY_COUNTDOWN)


async def _run_review(
    owner: str, repo: str, pr_number: int, installation_id: int
) -> dict[str, Any]:
    """Async implementation of PR review workflow."""
    log.info("Starting review", owner=owner, repo=repo, pr=pr_number)

    # Get config (from cache or DB, auto-creates if not exists)
    from ..core.services import get_config_service
    config_service = await get_config_service()
    config = await config_service.get_config(owner, repo, installation_id)

    # Check if review is enabled
    if not config.enabled:
        log.info("review.skipped", reason="disabled", owner=owner, repo=repo)
        return {"status": "skipped", "reason": "disabled"}

    # Check auto_review flag
    if not config.auto_review:
        log.info("review.skipped", reason="manual_only", owner=owner, repo=repo)
        return {"status": "skipped", "reason": "manual_only"}

    # Fetch PR details to populate title and author
    github = GitHubService(installation_id)
    pr_details = await github.get_pr_details(owner, repo, pr_number)

    initial_state = {
        "pr_context": PRContext(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title=pr_details.get("title", ""),
            author=pr_details.get("user", {}).get("login", ""),
            installation_id=installation_id,
            base_branch=pr_details.get("base", {}).get("ref", "main"),
            head_branch=pr_details.get("head", {}).get("ref", ""),
            is_draft=pr_details.get("draft", False),
        ),
        "config": config,  # Pass config to workflow
        "file_diffs": [],
        "all_breaking_changes": [],
        "all_comments": [],
        "published_comments": [],
        "errors": [],
    }

    result = await run_review(initial_state)

    if result.get("errors"):
        log.error("Review completed with errors", errors=result["errors"])
    else:
        log.info(
            "Review completed",
            breaking_changes=len(result.get("all_breaking_changes", [])),
            comments=len(result.get("all_comments", [])),
        )

    return {
        "status": "completed",
        "breaking_changes": len(result.get("all_breaking_changes", [])),
        "comment_count": len(result.get("all_comments", [])),
        "errors": result.get("errors", []),
    }


@celery_app.task(bind=True, max_retries=3)
def handle_command(
    self,
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
    in_reply_to_id: int | None = None,
) -> None:
    """
    Handle @reviewer command from PR comment.

    This task:
    1. Parses the command from the comment body
    2. Creates a CommandContext with all necessary info
    3. Dispatches to the appropriate handler
    4. Posts the response as a reply
    """
    try:
        asyncio.run(
            _process_command(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                comment_id=comment_id,
                comment_body=comment_body,
                author=author,
                installation_id=installation_id,
                in_reply_to_id=in_reply_to_id,
            )
        )
    except Exception as e:
        log.exception(
            "Command handling failed",
            owner=owner,
            repo=repo,
            pr=pr_number,
            comment_id=comment_id,
        )
        raise self.retry(exc=e, countdown=CELERY_COMMAND_RETRY_COUNTDOWN)


async def _process_command(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
    in_reply_to_id: int | None,
) -> None:
    """Async implementation of command processing."""
    log.info("Processing command", pr=pr_number, author=author)

    # 1. Parse command
    parsed = parse_command(comment_body)
    if not parsed:
        log.debug("No valid command found", body=comment_body[:100])
        return

    # 2. Create unified context
    ctx = CommandContext(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        comment_id=comment_id,
        author=author,
        target=parsed.target,
        in_reply_to_id=in_reply_to_id,
    )

    # 3. Execute command
    github = GitHubService(installation_id)
    handler = CommandHandler(github)
    response = await handler.handle(command_type=parsed.type, ctx=ctx)

    # 4. Post response
    formatted_response = f"@{author}\n\n{response}"

    if in_reply_to_id:
        await github.create_review_comment_reply(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            comment_id=in_reply_to_id,
            body=formatted_response,
        )
    else:
        await github.create_issue_comment(
            owner=owner,
            repo=repo,
            issue_number=pr_number,
            body=formatted_response,
        )

    log.info("Command completed", command=parsed.type.value, pr=pr_number)
