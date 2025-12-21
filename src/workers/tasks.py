import structlog

from ..agents.graph import graph
from ..agents.state import PRContext
from .celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3)
def review_pr(self, owner: str, repo: str, pr_number: int, installation_id: int):
    """Run the review workflow for a PR."""
    import asyncio

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

        return result

    try:
        return asyncio.run(_run())
    except Exception as e:
        log.error("Review failed", error=str(e))
        raise self.retry(exc=e, countdown=60)
