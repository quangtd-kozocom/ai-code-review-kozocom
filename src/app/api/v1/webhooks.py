"""GitHub webhook handlers."""

import hashlib
import hmac
from enum import StrEnum

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from ...config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = structlog.get_logger()

MENTION_MARKER = "@reviewer"


class GitHubEvent(StrEnum):
    """Supported GitHub webhook events."""

    PULL_REQUEST = "pull_request"
    ISSUE_COMMENT = "issue_comment"
    REVIEW_COMMENT = "pull_request_review_comment"
    INSTALLATION = "installation"
    INSTALLATION_REPOS = "installation_repositories"


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    """
    Handle GitHub webhook events.

    Supports:
    - pull_request: Triggers PR review
    - issue_comment: Handles @reviewer commands in PR conversations
    - pull_request_review_comment: Handles @reviewer commands on code lines
    """
    settings = get_settings()
    body = await request.body()

    # Validate signature
    if not _verify_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        log.warning("Invalid webhook signature", delivery=x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    match x_github_event:
        case GitHubEvent.PULL_REQUEST:
            return _handle_pull_request(payload)

        case GitHubEvent.ISSUE_COMMENT:
            return _handle_issue_comment(payload)

        case GitHubEvent.REVIEW_COMMENT:
            return _handle_review_comment(payload)

        case GitHubEvent.INSTALLATION:
            return _handle_installation(payload)

        case GitHubEvent.INSTALLATION_REPOS:
            return _handle_installation_repos(payload)

        case _:
            return {"status": "ignored", "event": x_github_event}


def _handle_pull_request(payload: dict) -> dict:
    """Handle pull_request events - trigger PR review or RAG update."""
    action = payload.get("action")
    pr = payload["pull_request"]
    repo = payload["repository"]

    # Handle PR merge - trigger RAG incremental update
    if action == "closed" and pr.get("merged"):
        log.info(
            "PR merged - triggering RAG update",
            pr=pr["number"],
            repo=repo["full_name"],
        )

        from ....workers.tasks import update_rag_index

        update_rag_index.delay(
            owner=repo["owner"]["login"],
            repo=repo["name"],
            pr_number=pr["number"],
            installation_id=payload["installation"]["id"],
        )
        return {"status": "rag_update_queued", "pr": pr["number"]}

    # Handle PR opened/synchronized - trigger review
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    log.info(
        "PR event received",
        action=action,
        pr=pr["number"],
        repo=repo["full_name"],
    )

    from ....workers.tasks import review_pr

    review_pr.delay(
        owner=repo["owner"]["login"],
        repo=repo["name"],
        pr_number=pr["number"],
        installation_id=payload["installation"]["id"],
    )

    return {"status": "queued", "pr": pr["number"]}


def _handle_issue_comment(payload: dict) -> dict:
    """Handle issue_comment events - commands in PR conversation."""
    action = payload.get("action")
    issue = payload.get("issue", {})
    comment = payload.get("comment", {})
    comment_body = comment.get("body", "")

    # Only process new comments on PRs with mention
    if not (
        action == "created" and "pull_request" in issue and MENTION_MARKER in comment_body.lower()
    ):
        return {"status": "ignored", "reason": "not_a_command"}

    log.info(
        "Command received",
        pr=issue["number"],
        author=comment["user"]["login"],
    )

    from ....workers.tasks import handle_command

    handle_command.delay(
        owner=payload["repository"]["owner"]["login"],
        repo=payload["repository"]["name"],
        pr_number=issue["number"],
        comment_id=comment["id"],
        comment_body=comment_body,
        author=comment["user"]["login"],
        installation_id=payload["installation"]["id"],
        in_reply_to_id=None,  # issue_comment doesn't have in_reply_to
    )

    return {"status": "queued", "type": "command"}


def _handle_review_comment(payload: dict) -> dict:
    """Handle pull_request_review_comment events - commands on code lines."""
    action = payload.get("action")
    comment = payload.get("comment", {})
    pr = payload.get("pull_request", {})
    comment_body = comment.get("body", "")

    # Only process new comments with mention
    if not (action == "created" and MENTION_MARKER in comment_body.lower()):
        return {"status": "ignored", "reason": "not_a_command"}

    log.info(
        "Review comment command",
        pr=pr["number"],
        author=comment["user"]["login"],
    )

    from ....workers.tasks import handle_command

    handle_command.delay(
        owner=payload["repository"]["owner"]["login"],
        repo=payload["repository"]["name"],
        pr_number=pr["number"],
        comment_id=comment["id"],
        comment_body=comment_body,
        author=comment["user"]["login"],
        installation_id=payload["installation"]["id"],
        in_reply_to_id=comment.get("in_reply_to_id"),
    )

    return {"status": "queued", "type": "review_command"}


def _handle_installation(payload: dict) -> dict:
    """Handle installation events - trigger RAG indexing for all repos."""
    action = payload.get("action")

    if action != "created":
        return {"status": "ignored", "action": action}

    installation_id = payload["installation"]["id"]
    repositories = [r["full_name"] for r in payload.get("repositories", [])]

    log.info(
        "Installation created - triggering RAG indexing",
        installation_id=installation_id,
        repos_count=len(repositories),
    )

    from ....workers.tasks import index_installation

    index_installation.delay(
        installation_id=installation_id,
        repositories=repositories,
    )

    return {"status": "indexing_queued", "repos": len(repositories)}


def _handle_installation_repos(payload: dict) -> dict:
    """Handle installation_repositories events - repos added/removed."""
    action = payload.get("action")
    installation_id = payload["installation"]["id"]

    if action == "added":
        repositories = [r["full_name"] for r in payload.get("repositories_added", [])]

        log.info(
            "Repos added to installation - triggering RAG indexing",
            installation_id=installation_id,
            repos_count=len(repositories),
        )

        from ....workers.tasks import index_installation

        index_installation.delay(
            installation_id=installation_id,
            repositories=repositories,
        )
        return {"status": "indexing_queued", "repos": len(repositories)}

    return {"status": "ignored", "action": action}


def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
