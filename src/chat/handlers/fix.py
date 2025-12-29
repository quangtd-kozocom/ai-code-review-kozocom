"""Fix command handler - generates code fixes for review comments.

Uses LangChain structured output for reliable fix generation.
"""

import structlog
from httpx import HTTPStatusError

from ...agents.models import FixResult
from ...core.llm import get_structured_llm
from ..context import CommandContext
from ..prompts import FIX_PROMPT
from ..responses import (
    ERROR_CANNOT_FETCH_COMMENT,
    ERROR_CANNOT_GENERATE_FIX,
    ERROR_CANNOT_READ_FILE,
    ERROR_NO_PARENT_COMMENT,
    FIX_SUCCESS,
)
from .base import BaseCommandHandler

log = structlog.get_logger()


class FixCommandHandler(BaseCommandHandler):
    """Generate code fix for a review comment issue."""

    async def execute(self, ctx: CommandContext) -> str:
        """
        Execute the fix command.

        Fetches the parent review comment, gets code context,
        and uses LLM to generate a fix suggestion.

        Args:
            ctx: Command context with PR and comment details.

        Returns:
            Response message with the fix or error.
        """
        if not ctx.requires_parent_comment:
            return ERROR_NO_PARENT_COMMENT

        try:
            # Fetch parent comment details
            parent = await self.github.get_review_comment(ctx.owner, ctx.repo, ctx.in_reply_to_id)
            if not parent:
                return ERROR_CANNOT_FETCH_COMMENT

            file_path = parent.get("path", "")
            line = parent.get("line") or parent.get("original_line", 0)
            issue_description = parent.get("body", "")

            # Get code context around the issue
            code_context = await self.github.get_file_content_at_pr(
                ctx.owner, ctx.repo, ctx.pr_number, file_path, line, context_lines=5
            )
            if not code_context:
                return ERROR_CANNOT_READ_FILE

            # Generate fix using structured LLM
            prompt = FIX_PROMPT.format(
                issue_description=issue_description,
                file_path=file_path,
                line=line,
                code_context=code_context,
            )

            structured_llm = get_structured_llm(FixResult)
            result: FixResult = await structured_llm.ainvoke(prompt)

            return FIX_SUCCESS.format(
                fixed_code=result.fixed_code,
                explanation=result.explanation,
            )

        except HTTPStatusError as e:
            log.error("GitHub API error", status=e.response.status_code)
            return f"❌ GitHub API error: {e.response.status_code}"
        except Exception:
            log.exception("Fix generation failed")
            return ERROR_CANNOT_GENERATE_FIX
