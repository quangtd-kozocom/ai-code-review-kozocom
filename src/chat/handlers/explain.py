"""Explain command handler - provides detailed explanations for code issues."""

from pathlib import Path

import structlog

from ..context import CommandContext
from ..prompts import EXPLAIN_PROMPT
from ..responses import (
    ERROR_CANNOT_FETCH_COMMENT,
    ERROR_NO_PARENT_COMMENT,
    EXPLAIN_SUCCESS,
)
from .base import LANGUAGE_MAP, BaseCommandHandler

log = structlog.get_logger()


class ExplainCommandHandler(BaseCommandHandler):
    """Explain a code issue in detail."""

    async def execute(self, ctx: CommandContext) -> str:
        if not ctx.requires_parent_comment:
            return ERROR_NO_PARENT_COMMENT

        try:
            parent = await self.github.get_review_comment(ctx.owner, ctx.repo, ctx.in_reply_to_id)
            if not parent:
                return ERROR_CANNOT_FETCH_COMMENT

            file_path = parent.get("path", "")
            line = parent.get("line") or parent.get("original_line", 0)
            issue_description = parent.get("body", "")
            language = self._detect_language(file_path)

            code_context = await self.github.get_file_content_at_pr(
                ctx.owner, ctx.repo, ctx.pr_number, file_path, line, context_lines=10
            )

            prompt = EXPLAIN_PROMPT.format(
                issue_description=issue_description,
                file_path=file_path,
                line=line,
                language=language,
                code_context=code_context or "N/A",
            )
            response = await self.llm.ainvoke(prompt)

            return EXPLAIN_SUCCESS.format(content=response.content)

        except Exception as e:
            log.exception("Explain generation failed")
            return f"❌ Lỗi: {e}"

    @staticmethod
    def _detect_language(filename: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(filename).suffix.lower()
        return LANGUAGE_MAP.get(ext, "text")
