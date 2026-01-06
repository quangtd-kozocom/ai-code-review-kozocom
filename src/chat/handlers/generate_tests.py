"""Generate tests command handler - creates unit tests for PR changes."""

from pathlib import Path

import structlog

from ...core.constants import MAX_FILES_FOR_TEST_GENERATION
from ..context import CommandContext
from ..prompts import GENERATE_TESTS_PROMPT
from ..responses import ERROR_NO_FILES_FOUND, ERROR_NO_MATCHING_FILES, TESTS_SUCCESS
from .base import LANGUAGE_MAP, SKIP_PATTERNS, BaseCommandHandler

log = structlog.get_logger()


class GenerateTestsCommandHandler(BaseCommandHandler):
    """Generate unit tests for PR changes."""

    async def execute(self, ctx: CommandContext) -> str:
        try:
            pr_files = await self.github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)
            if not pr_files:
                return ERROR_NO_FILES_FOUND

            testable_files = [
                {
                    "filename": f.get("filename", ""),
                    "patch": f.get("patch", ""),
                    "language": self._detect_language(f.get("filename", "")),
                }
                for f in pr_files
                if self._is_testable(f.get("filename", ""), ctx.target)
            ]

            if not testable_files:
                target_info = f" matching '{ctx.target}'" if ctx.target else ""
                return ERROR_NO_MATCHING_FILES.format(target_info=target_info)

            testable_files = testable_files[:MAX_FILES_FOR_TEST_GENERATION]
            pr_diff = self._format_diff(testable_files)

            prompt = GENERATE_TESTS_PROMPT.format(
                pr_diff=pr_diff,
                target=ctx.target or "all changed files",
            )
            response = await self.llm.ainvoke(prompt)

            files_list = ", ".join(f["filename"] for f in testable_files)
            return TESTS_SUCCESS.format(files_list=files_list, content=response.content)

        except Exception as e:
            log.exception("Test generation failed")
            return f"❌ Lỗi khi generate tests: {e}"

    @staticmethod
    def _is_testable(filename: str, target: str | None) -> bool:
        """Check if file should be included for test generation."""
        filename_lower = filename.lower()

        # Skip non-testable files
        if any(p in filename_lower for p in SKIP_PATTERNS):
            return False

        # Filter by target if specified
        if target and target.lower() not in filename_lower:
            return False

        return True

    @staticmethod
    def _detect_language(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return LANGUAGE_MAP.get(ext, "text")

    @staticmethod
    def _format_diff(files: list[dict]) -> str:
        """Format file diffs for prompt."""
        parts = []
        for f in files:
            parts.append(f"\n### {f['filename']}\n```{f['language']}\n{f['patch']}\n```\n")
        return "".join(parts)
