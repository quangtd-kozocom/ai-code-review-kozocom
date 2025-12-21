import structlog

from ...app.services.github import GitHubService
from ..state import GraphState

log = structlog.get_logger()

ACKNOWLEDGE_MESSAGE = """🤖 **AI Code Review Started**

I'm analyzing your pull request. This may take a moment...

**What I'll check:**
- 🔒 Security vulnerabilities
- 🎨 Code style & best practices  
- 🧠 Logic & potential bugs

I'll post my review shortly. Thanks for your patience! ⏳
"""


async def run(state: GraphState) -> dict:
    """Post initial acknowledgment comment to PR."""
    ctx = state["context"]
    log.info("Acknowledger started", pr=ctx.pr_number)

    github = GitHubService(ctx.installation_id)

    try:
        comment_id = await github.create_pr_comment(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            body=ACKNOWLEDGE_MESSAGE,
        )
        log.info("Acknowledgment posted", comment_id=comment_id, pr=ctx.pr_number)
        return {"acknowledge_comment_id": comment_id}
    except Exception as e:
        # Don't fail the whole workflow if acknowledgment fails
        log.warning("Failed to post acknowledgment", error=str(e), pr=ctx.pr_number)
        return {"acknowledge_comment_id": None}
