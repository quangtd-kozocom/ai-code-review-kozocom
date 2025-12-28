"""Celery background tasks."""

import asyncio

import structlog

from ..agents.graph import graph
from ..agents.state import PRContext
from ..app.services.github import GitHubService
from ..chat.commands import CommandType
from ..chat.context import CommandContext
from ..chat.handler import CommandHandler
from ..chat.parser import parse_command
from .celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3)
def review_pr(self, owner: str, repo: str, pr_number: int, installation_id: int):
    """Run the review workflow for a PR."""

    async def _run():
        log.info("Starting review", owner=owner, repo=repo, pr=pr_number)

        initial_state = {
            "context": PRContext(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                title="",  # Will be fetched if needed
                author="",
                installation_id=installation_id,
            ),
            "files": [],
            "comments": [],
            "final_comments": [],
            "summary": "",
            "review_id": None,
            "errors": [],
        }

        result = await graph.ainvoke(initial_state)

        if result.get("errors"):
            log.error("Review completed with errors", errors=result["errors"])
        else:
            log.info("Review completed", review_id=result.get("review_id"))

        return {
            "status": "completed",
            "review_id": result.get("review_id"),
            "comment_count": len(result.get("final_comments", [])),
            "errors": result.get("errors", []),
        }

    try:
        return asyncio.run(_run())
    except Exception as e:
        log.exception("Review failed")
        raise self.retry(exc=e, countdown=60)


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
):
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
        log.exception("Command handling failed")
        raise self.retry(exc=e, countdown=30)


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
