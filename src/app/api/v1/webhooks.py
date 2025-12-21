import hashlib
import hmac

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from ...config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = structlog.get_logger()


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    """Handle GitHub webhook events."""
    settings = get_settings()
    body = await request.body()

    # Validate signature
    if not _verify_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        log.warning("Invalid webhook signature", delivery=x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Handle pull_request events
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize", "reopened"):
            pr = payload["pull_request"]
            repo = payload["repository"]

            log.info(
                "PR event received",
                action=action,
                pr=pr["number"],
                repo=repo["full_name"],
            )

            # Queue review task
            from src.workers.tasks import review_pr

            review_pr.delay(
                owner=repo["owner"]["login"],
                repo=repo["name"],
                pr_number=pr["number"],
                installation_id=payload["installation"]["id"],
            )

            return {"status": "queued", "pr": pr["number"]}

    return {"status": "ignored", "event": x_github_event}


def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
