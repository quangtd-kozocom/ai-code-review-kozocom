"""Fix command handler - generates code fixes for breaking changes."""

import re

import structlog

from ...agents.models import FixResult
from ...core.llm import get_structured_llm
from ..context import CommandContext
from ..prompts import FIX_PROMPT_SIMPLE
from ..responses import (
    ERROR_CANNOT_FETCH_COMMENT,
    ERROR_CANNOT_GENERATE_FIX,
    ERROR_CANNOT_READ_FILE,
    ERROR_NO_PARENT_COMMENT,
    FIX_SUCCESS,
)
from .base import BaseCommandHandler, get_language_from_path

log = structlog.get_logger()

# Patterns to extract info - handles markdown backticks around file paths
RE_FILE = re.compile(r"`?([a-zA-Z0-9_/.-]+\.(?:php|py|js|ts|java|go|rb))`?", re.I)
# Support both English and Vietnamese recommendation headers
RE_RECOMMENDATION = re.compile(r"(?:Recommendation|Khuyến Nghị):\s*(.+?)(?:\n\n|\Z)", re.S | re.I)
# Pattern to extract entity info from breaking change comments
RE_ENTITY = re.compile(r"(?:constant|hằng số)\s+`?(\w+)`?", re.I)
RE_OLD_NEW = re.compile(r"(?:replaced|thay thế)\s+(?:by|bằng)\s+`?(\w+)`?", re.I)


class FixCommandHandler(BaseCommandHandler):
    async def execute(self, ctx: CommandContext) -> str:
        if not ctx.requires_parent_comment:
            return ERROR_NO_PARENT_COMMENT

        try:
            parent = await self.github.get_review_comment(
                ctx.owner, ctx.repo, ctx.in_reply_to_id
            )
            if not parent:
                return ERROR_CANNOT_FETCH_COMMENT

            file_path = parent.get("path", "")
            line = parent.get("line") or parent.get("original_line", 1)
            comment = parent.get("body", "")

            affected = self._parse_affected_files(comment, file_path)

            # Extract recommendation and breaking change context
            rec_match = RE_RECOMMENDATION.search(comment)
            recommendation = rec_match.group(1).strip() if rec_match else ""
            breaking_context = self._extract_breaking_context(comment, file_path)

            if affected:
                pr = await self.github.get_pr_details(ctx.owner, ctx.repo, ctx.pr_number)
                ref = pr.get("head", {}).get("sha", "HEAD")
                return await self._fix_multiple(
                    ctx.owner, ctx.repo, ref, affected, recommendation, breaking_context
                )

            return await self._fix_single(ctx, file_path, line, recommendation or comment)

        except Exception:
            log.exception("Fix failed")
            return ERROR_CANNOT_GENERATE_FIX

    def _extract_breaking_context(self, comment: str, source_file: str) -> dict[str, str]:
        """Extract breaking change context from comment."""
        entity = m.group(1) if (m := RE_ENTITY.search(comment)) else ""
        new_entity = m.group(1) if (m := RE_OLD_NEW.search(comment)) else ""
        return {
            "entity_name": entity,
            "new_entity": new_entity,
            "source_file": source_file,
            "change_detail": (
                f"{entity} was replaced by {new_entity}" if entity and new_entity else ""
            ),
        }

    def _parse_affected_files(self, comment: str, exclude: str) -> list[str]:
        """Extract file paths from comment, excluding source file."""
        paths = [m.group(1) for m in RE_FILE.finditer(comment)]
        return [p for p in dict.fromkeys(paths) if p != exclude]

    async def _fix_multiple(
        self,
        owner: str,
        repo: str,
        ref: str,
        paths: list[str],
        recommendation: str,
        breaking_context: dict[str, str],
    ) -> str:
        """Generate fixes for multiple affected files using breaking change context."""
        from ..prompts import FIX_PROMPT

        llm = get_structured_llm(FixResult)
        results = []

        for path in paths[:5]:
            content = await self.github.get_file_raw(owner, repo, path, ref, resolve_path=True)
            if not content:
                log.warning("file_not_found", path=path, ref=ref)
                continue

            # Use FIX_PROMPT with breaking change context if available
            if breaking_context.get("entity_name"):
                prompt = FIX_PROMPT.format(
                    entity_name=breaking_context["entity_name"],
                    change_detail=breaking_context.get("change_detail", recommendation),
                    source_file=breaking_context["source_file"],
                    file_path=path,
                    line=1,
                    break_reason=(
                        recommendation
                        or f"Uses {breaking_context['entity_name']} which no longer exists"
                    ),
                    language=get_language_from_path(path),
                    code_context=content[:3000],
                )
            else:
                prompt = FIX_PROMPT_SIMPLE.format(
                    issue_description=recommendation or "Fix the breaking change",
                    file_path=path,
                    line=1,
                    language=get_language_from_path(path),
                    code_context=content[:3000],
                )

            try:
                r: FixResult = await llm.ainvoke(prompt)
                # Format as proper diff with file path and explanation
                results.append(
                    f"### `{path}`\n\n"
                    f"**{r.explanation}**\n\n"
                    f"```diff\n{r.fixed_code}\n```"
                )
            except Exception:
                log.exception("Failed to generate fix", path=path)

        return "\n\n".join(results) if results else ERROR_CANNOT_GENERATE_FIX

    async def _fix_single(
        self, ctx: CommandContext, path: str, line: int, issue: str
    ) -> str:
        """Generate fix for a single location."""
        code = await self.github.get_file_content_at_pr(
            ctx.owner, ctx.repo, ctx.pr_number, path, line, 10
        )
        if not code:
            return ERROR_CANNOT_READ_FILE

        prompt = FIX_PROMPT_SIMPLE.format(
            issue_description=issue,
            file_path=path,
            line=line,
            language=get_language_from_path(path),
            code_context=code,
        )

        r: FixResult = await get_structured_llm(FixResult).ainvoke(prompt)
        return FIX_SUCCESS.format(fixed_code=r.fixed_code, explanation=r.explanation)
