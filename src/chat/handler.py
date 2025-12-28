"""Handle @reviewer commands with clean architecture."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

import structlog
from httpx import HTTPStatusError

from ..app.services.github import GitHubService
from ..core.llm import get_llm
from .commands import CommandType
from .context import CommandContext
from .prompts import EXPLAIN_PROMPT, FIX_PROMPT, GENERATE_TESTS_PROMPT
from .responses import (
    ERROR_CANNOT_FETCH_COMMENT,
    ERROR_CANNOT_GENERATE_FIX,
    ERROR_CANNOT_READ_FILE,
    ERROR_NO_FILES_FOUND,
    ERROR_NO_MATCHING_FILES,
    ERROR_NO_PARENT_COMMENT,
    ERROR_UNKNOWN_COMMAND,
    EXPLAIN_SUCCESS,
    FIX_SUCCESS,
    HELP_MESSAGE,
    TESTS_SUCCESS,
)

log = structlog.get_logger()

# File extension to language mapping
LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}

# Patterns to skip for test generation
SKIP_PATTERNS: frozenset[str] = frozenset(
    {
        "test_",
        "_test.",
        ".test.",
        "tests/",
        "__init__",
        "config",
        "migration",
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".txt",
        ".lock",
        "package-lock",
        "yarn.lock",
    }
)


# ============== BASE HANDLER ==============


class BaseCommandHandler(ABC):
    """Abstract base class for command handlers."""

    def __init__(self, github: GitHubService):
        self.github = github
        self.llm = get_llm()

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> str:
        """Execute the command and return response text."""
        ...


# ============== CONCRETE HANDLERS ==============


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


class GenerateTestsCommandHandler(BaseCommandHandler):
    """Generate unit tests for PR changes."""

    MAX_FILES = 3  # Limit files to avoid token limits

    async def execute(self, ctx: CommandContext) -> str:
        try:
            pr_files = await self.github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)
            if not pr_files:
                return ERROR_NO_FILES_FOUND

            # Filter to testable files
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

            # Limit files and format diff
            testable_files = testable_files[: self.MAX_FILES]
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


class HelpCommandHandler(BaseCommandHandler):
    """Return help message."""

    async def execute(self, ctx: CommandContext) -> str:
        return HELP_MESSAGE


class UnknownCommandHandler(BaseCommandHandler):
    """Handle unknown commands."""

    async def execute(self, ctx: CommandContext) -> str:
        return ERROR_UNKNOWN_COMMAND


# ============== MAIN HANDLER (FACTORY) ==============


class CommandHandler:
    """
    Main command handler using strategy pattern.

    Routes commands to appropriate handler implementations.
    """

    _handlers: dict[CommandType, type[BaseCommandHandler]] = {
        CommandType.FIX: FixCommandHandler,
        CommandType.EXPLAIN: ExplainCommandHandler,
        CommandType.GENERATE_TESTS: GenerateTestsCommandHandler,
        CommandType.HELP: HelpCommandHandler,
        CommandType.UNKNOWN: UnknownCommandHandler,
    }

    def __init__(self, github: GitHubService):
        self.github = github

    async def handle(self, command_type: CommandType, ctx: CommandContext) -> str:
        """
        Handle a command and return response text.

        Args:
            command_type: Type of command to handle
            ctx: Unified command context

        Returns:
            Response text to post as reply
        """
        handler_cls = self._handlers.get(command_type, UnknownCommandHandler)
        handler = handler_cls(self.github)

        log.info(
            "Executing command",
            command=command_type,
            pr=ctx.pr_number,
            author=ctx.author,
        )

        return await handler.execute(ctx)
