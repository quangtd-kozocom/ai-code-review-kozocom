"""Fix command handler - generates code fixes for review comments."""

import json

import structlog
from httpx import HTTPStatusError

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

            # Generate fix using LLM
            prompt = FIX_PROMPT.format(
                issue_description=issue_description,
                file_path=file_path,
                line=line,
                code_context=code_context,
            )
            response = await self.llm.ainvoke(prompt)
            fix_data = self._parse_json_response(response.content)

            if not fix_data or "fixed_code" not in fix_data:
                log.warning("Failed to parse fix response", response=response.content[:200])
                return ERROR_CANNOT_GENERATE_FIX

            return FIX_SUCCESS.format(
                fixed_code=fix_data["fixed_code"],
                explanation=fix_data.get("explanation", ""),
            )

        except HTTPStatusError as e:
            log.error("GitHub API error", status=e.response.status_code)
            return f"❌ GitHub API error: {e.response.status_code}"
        except Exception as e:
            log.exception("Fix generation failed")
            return f"❌ Lỗi khi generate fix: {e}"

    @staticmethod
    def _parse_json_response(content: str) -> dict | None:
        """Extract and parse JSON from LLM response."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        return None
