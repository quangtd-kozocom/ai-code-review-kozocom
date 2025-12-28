# 🎯 TASK: Implement On-Demand Commands

> Task document for AI agent implementation

**Priority:** High  
**Complexity:** Medium  
**Estimated Time:** 3-4 hours

---

## 📋 Overview

Implement tính năng cho phép developer sử dụng `@reviewer` commands trong PR comments để AI thực hiện các tác vụ on-demand.

### Commands to Implement

| Command                    | Description                  |
| -------------------------- | ---------------------------- |
| `@reviewer fix this`       | Generate fix cho issue       |
| `@reviewer generate tests` | Generate unit tests cho PR   |
| `@reviewer explain`        | Giải thích chi tiết về issue |
| `@reviewer help`           | Hiện help message            |

---

## 📁 Current Project Structure

```
src/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       ├── webhooks.py      ← UPDATE THIS
│   │       └── health.py
│   └── services/
│       ├── __init__.py
│       ├── github.py            ← UPDATE THIS
│       └── slack.py
│
├── agents/
│   ├── __init__.py
│   ├── graph.py
│   ├── state.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── context_extractor.py
│   │   ├── security_agent.py
│   │   ├── style_agent.py
│   │   ├── logic_agent.py
│   │   ├── aggregator.py
│   │   ├── github_publisher.py  ← UPDATE THIS
│   │   └── slack_reporter.py
│   └── prompts/
│       ├── __init__.py
│       ├── security.py
│       ├── style.py
│       └── logic.py
│
├── core/
│   ├── __init__.py
│   ├── logging.py
│   └── llm.py
│
└── workers/
    ├── __init__.py
    ├── celery_app.py
    └── tasks.py                 ← UPDATE THIS
```

---

## 🎯 Tasks

### Task 1: Create Chat Module

**Create:** `src/chat/__init__.py`

```python
"""Chat module for handling @reviewer commands."""

from .commands import CommandType
from .context import CommandContext
from .handler import CommandHandler
from .parser import ParsedCommand, parse_command

__all__ = [
    "CommandType",
    "CommandContext",
    "CommandHandler",
    "ParsedCommand",
    "parse_command",
]
```

**Create:** `src/chat/commands.py`

```python
"""Command type definitions using modern Python enums."""

from enum import StrEnum, auto


class CommandType(StrEnum):
    """Supported @reviewer command types."""

    FIX = "fix"
    GENERATE_TESTS = "generate_tests"
    EXPLAIN = "explain"
    HELP = "help"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "CommandType":
        """Safely convert string to CommandType."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN
```

**Create:** `src/chat/context.py`

```python
"""Unified command context for all handlers."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CommandContext:
    """Immutable context passed to all command handlers."""

    owner: str
    repo: str
    pr_number: int
    comment_id: int
    author: str
    target: str | None = None
    in_reply_to_id: int | None = None

    @property
    def requires_parent_comment(self) -> bool:
        """Check if this context has a parent review comment."""
        return self.in_reply_to_id is not None
```

---

### Task 2: Create Command Parser

**Create:** `src/chat/parser.py`

```python
"""Parse @reviewer commands from PR comments."""

import re
from dataclasses import dataclass

from .commands import CommandType

# Pre-compiled regex patterns for performance
_PATTERNS: dict[CommandType, re.Pattern[str]] = {
    CommandType.FIX: re.compile(r"@reviewer\s+fix(?:\s+this)?", re.IGNORECASE),
    CommandType.EXPLAIN: re.compile(r"@reviewer\s+explain(?:\s+this)?", re.IGNORECASE),
    CommandType.HELP: re.compile(r"@reviewer\s+help", re.IGNORECASE),
    CommandType.GENERATE_TESTS: re.compile(
        r"@reviewer\s+(?:generate\s+)?tests?(?:\s+for\s+(.+))?", re.IGNORECASE
    ),
}

# Validation constants
MAX_COMMENT_LENGTH = 10_000
MENTION_MARKER = "@reviewer"


@dataclass(slots=True, frozen=True)
class ParsedCommand:
    """Immutable parsed @reviewer command."""

    type: CommandType
    target: str | None = None
    raw: str = ""


def parse_command(body: str) -> ParsedCommand | None:
    """
    Parse @reviewer command from comment body.

    Args:
        body: Comment body text

    Returns:
        ParsedCommand if valid @reviewer command found, None otherwise

    Examples:
        >>> parse_command("@reviewer fix this")
        ParsedCommand(type=<CommandType.FIX: 'fix'>, target=None, raw='@reviewer fix this')

        >>> parse_command("@reviewer generate tests for auth.py")
        ParsedCommand(type=<CommandType.GENERATE_TESTS: 'generate_tests'>, target='auth.py', ...)
    """
    # Input validation
    if not _is_valid_input(body):
        return None

    # Check for mention marker first (fast path)
    if MENTION_MARKER not in body.lower():
        return None

    # Match commands in priority order
    return _match_command(body)


def _is_valid_input(body: str) -> bool:
    """Validate input before processing."""
    if not body or not isinstance(body, str):
        return False
    if len(body) > MAX_COMMENT_LENGTH:
        return False
    return True


def _match_command(body: str) -> ParsedCommand:
    """Match body against known command patterns."""
    # Order matters: more specific patterns first
    for cmd_type in (
        CommandType.FIX,
        CommandType.EXPLAIN,
        CommandType.HELP,
        CommandType.GENERATE_TESTS,
    ):
        pattern = _PATTERNS[cmd_type]
        if match := pattern.search(body):
            target = None
            # Extract target for generate_tests command
            if cmd_type == CommandType.GENERATE_TESTS and match.lastindex:
                target = match.group(1).strip() if match.group(1) else None
            return ParsedCommand(type=cmd_type, target=target, raw=body)

    return ParsedCommand(type=CommandType.UNKNOWN, raw=body)
```

---

### Task 3: Create Command Handler

**Create:** `src/chat/prompts.py`

```python
"""LLM prompt templates for command handlers."""

FIX_PROMPT = """\
You are an expert code fixer.

## Issue from Code Review:
{issue_description}

## File: {file_path}
## Line: {line}

## Code Context (lines around the issue):
```

{code_context}

````

## Task:
Generate a MINIMAL fix for this issue. Only fix the problematic line(s).

## Rules:
1. Keep the SAME indentation as the original code
2. Only output the fixed code, nothing else
3. Be concise - minimal changes only
4. Ensure the fix is syntactically correct

## Output Format (JSON only, no markdown):
{{"fixed_code": "the corrected code line(s)", "explanation": "brief 1-sentence explanation"}}
"""

EXPLAIN_PROMPT = """\
You are a senior software engineer explaining a code issue to a junior developer.

## Issue from Code Review:
{issue_description}

## File: {file_path}
## Line: {line}

## Code Context:
```{language}
{code_context}
````

## Task:

Explain this issue in detail. Be educational and helpful.

## Include:

1. **What is the problem?** - Explain the issue clearly
2. **Why is it a problem?** - What could go wrong?
3. **How to fix it?** - Step by step guidance
4. **Example** - Show correct code if helpful

## Format your response in Markdown.

"""

GENERATE_TESTS_PROMPT = """\
You are an expert test engineer.

## PR Changes:

{pr_diff}

## Target: {target}

## Task:

Generate comprehensive unit tests for the code changes.

## Testing Framework: pytest (for Python), jest (for JS/TS)

## Requirements:

1. Cover happy path scenarios
2. Cover edge cases (null, empty, boundary values)
3. Cover error scenarios
4. Use descriptive test names
5. Include docstrings explaining each test

## Output Format:

```python
import pytest

def test_...:
    \"\"\"Test description.\"\"\"
    ...
```

"""

````

**Create:** `src/chat/responses.py`

```python
"""Response templates for command handlers."""

# Success responses
FIX_SUCCESS = """\
## 🔧 Suggested Fix

```suggestion
{fixed_code}
````

**Giải thích:** {explanation}

---

_Click "Commit suggestion" để apply fix này._
"""

EXPLAIN_SUCCESS = """\

## 🔍 Giải Thích Chi Tiết

{content}

---

_Nếu vẫn chưa rõ, hãy hỏi thêm!_
"""

TESTS_SUCCESS = """\

## 🧪 Generated Unit Tests

**Files analyzed:** {files_list}

{content}

---

_Copy tests này vào test file của bạn. Adjust imports nếu cần._
"""

HELP_MESSAGE = """\

## 🤖 AI Reviewer Commands

| Command                    | Mô tả                        |
| -------------------------- | ---------------------------- |
| `@reviewer fix this`       | Tạo suggested fix cho issue  |
| `@reviewer explain`        | Giải thích chi tiết về issue |
| `@reviewer generate tests` | Tạo unit tests cho PR        |
| `@reviewer help`           | Hiện help này                |

### Cách sử dụng

**Fix & Explain:** Reply trực tiếp vào review comment

```
@reviewer fix this
```

**Generate Tests:** Comment ở bất kỳ đâu trong PR

```
@reviewer generate tests
@reviewer generate tests for auth.py
```

"""

# Error responses

ERROR_NO_PARENT_COMMENT = """\
❌ **Không tìm thấy review comment**

Vui lòng reply trực tiếp vào một review comment \
(comment trên code, không phải conversation comment).
"""

ERROR_CANNOT_FETCH_COMMENT = "❌ Không thể lấy thông tin review comment."
ERROR_CANNOT_READ_FILE = "❌ Không thể đọc nội dung file."
ERROR_CANNOT_GENERATE_FIX = "❌ Không thể generate fix. Vui lòng thử lại hoặc sửa thủ công."
ERROR_NO_FILES_FOUND = "❌ Không tìm thấy files changed trong PR."
ERROR_NO_MATCHING_FILES = "❌ Không tìm thấy file phù hợp{target_info}"
ERROR_UNKNOWN_COMMAND = """\
❓ **Không hiểu command**

Thử `@reviewer help` để xem danh sách commands.
"""

````

**Create:** `src/chat/handler.py`

```python
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
SKIP_PATTERNS: frozenset[str] = frozenset({
    "test_", "_test.", ".test.", "tests/",
    "__init__", "config", "migration",
    ".json", ".yaml", ".yml", ".md", ".txt",
    ".lock", "package-lock", "yarn.lock",
})


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
            parent = await self.github.get_review_comment(
                ctx.owner, ctx.repo, ctx.in_reply_to_id
            )
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
            parent = await self.github.get_review_comment(
                ctx.owner, ctx.repo, ctx.in_reply_to_id
            )
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
            pr_files = await self.github.get_pr_files(
                ctx.owner, ctx.repo, ctx.pr_number
            )
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
````

---

### Task 3.1: Create Models for Type Safety (Optional but Recommended)

**Create:** `src/chat/models.py`

```python
"""Pydantic models for type-safe GitHub API responses."""

from pydantic import BaseModel, Field


class ReviewComment(BaseModel):
    """GitHub review comment structure."""

    id: int
    path: str
    line: int | None = None
    original_line: int | None = None
    body: str = ""

    @property
    def effective_line(self) -> int:
        """Get the effective line number."""
        return self.line or self.original_line or 0


class FixResult(BaseModel):
    """LLM fix generation result."""

    fixed_code: str
    explanation: str = ""


class FileChange(BaseModel):
    """PR file change."""

    filename: str
    patch: str = ""
    status: str = ""
```

---

### Task 4: Update GitHub Service

**Update:** `src/app/services/github.py`

Add these methods to the `GitHubService` class with retry logic and proper error handling:

```python
# Add imports at the top of file
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from httpx import HTTPStatusError


# Add to existing GitHubService class

# Retry decorator for transient errors
_retry_on_transient = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)


@_retry_on_transient
async def get_review_comment(
    self,
    owner: str,
    repo: str,
    comment_id: int,
) -> dict | None:
    """
    Get a single review comment by ID.

    Args:
        owner: Repository owner
        repo: Repository name
        comment_id: Review comment ID

    Returns:
        Comment data dict or None if not found
    """
    token = await self._get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/comments/{comment_id}",
            headers=self._headers(token),
        )

        if resp.status_code == 404:
            log.warning("Review comment not found", comment_id=comment_id)
            return None

        resp.raise_for_status()
        return resp.json()


@_retry_on_transient
async def get_file_content_at_pr(
    self,
    owner: str,
    repo: str,
    pr_number: int,
    path: str,
    line: int,
    context_lines: int = 5,
) -> str | None:
    """
    Get file content around a specific line at PR head.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        path: File path in the repository
        line: Target line number
        context_lines: Number of lines before/after to include

    Returns:
        Formatted code context with line numbers, or None on error
    """
    token = await self._get_token()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get PR to find head SHA
            pr_resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self._headers(token),
            )
            pr_resp.raise_for_status()
            ref = pr_resp.json()["head"]["sha"]

            # Get file content at that ref
            file_resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                headers={
                    **self._headers(token),
                    "Accept": "application/vnd.github.raw+json",
                },
                params={"ref": ref},
            )
            file_resp.raise_for_status()

            return self._format_code_context(file_resp.text, line, context_lines)

    except HTTPStatusError as e:
        log.error(
            "Failed to get file content",
            path=path,
            status=e.response.status_code,
        )
        return None
    except Exception as e:
        log.exception("Unexpected error getting file content", path=path)
        return None


def _format_code_context(self, content: str, line: int, context_lines: int) -> str:
    """Format code with line numbers, highlighting target line."""
    lines = content.split("\n")
    start = max(0, line - context_lines - 1)
    end = min(len(lines), line + context_lines)

    result = []
    for i, code_line in enumerate(lines[start:end], start=start + 1):
        marker = ">>> " if i == line else "    "
        result.append(f"{marker}{i}: {code_line}")

    return "\n".join(result)


@_retry_on_transient
async def create_issue_comment(
    self,
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
) -> int:
    """
    Create a comment on an issue or PR.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue/PR number
        body: Comment body text

    Returns:
        Created comment ID
    """
    token = await self._get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments",
            headers=self._headers(token),
            json={"body": body},
        )
        resp.raise_for_status()
        comment_id = resp.json()["id"]
        log.info("Issue comment created", comment_id=comment_id)
        return comment_id


@_retry_on_transient
async def create_review_comment_reply(
    self,
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    body: str,
) -> int:
    """
    Reply to a review comment.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        comment_id: Parent comment ID to reply to
        body: Reply body text

    Returns:
        Created reply comment ID
    """
    token = await self._get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            headers=self._headers(token),
            json={
                "body": body,
                "in_reply_to": comment_id,
            },
        )
        resp.raise_for_status()
        reply_id = resp.json()["id"]
        log.info("Review comment reply created", reply_id=reply_id)
        return reply_id


def _headers(self, token: str) -> dict[str, str]:
    """Build common request headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
```

---

### Task 5: Update Webhook Handler

**Update:** `src/app/api/v1/webhooks.py`

Refactored with pattern matching and better organization:

```python
"""GitHub webhook handlers."""

import hashlib
import hmac
from enum import StrEnum

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from ...config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = structlog.get_logger()

# Mention marker to detect commands
MENTION_MARKER = "@reviewer"


class GitHubEvent(StrEnum):
    """Supported GitHub webhook events."""

    PULL_REQUEST = "pull_request"
    ISSUE_COMMENT = "issue_comment"
    REVIEW_COMMENT = "pull_request_review_comment"


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

    # Route to appropriate handler using pattern matching
    match x_github_event:
        case GitHubEvent.PULL_REQUEST:
            return _handle_pull_request(payload)

        case GitHubEvent.ISSUE_COMMENT:
            return _handle_issue_comment(payload)

        case GitHubEvent.REVIEW_COMMENT:
            return _handle_review_comment(payload)

        case _:
            return {"status": "ignored", "event": x_github_event}


def _handle_pull_request(payload: dict) -> dict:
    """Handle pull_request events - trigger PR review."""
    action = payload.get("action")

    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    pr = payload["pull_request"]
    repo = payload["repository"]

    log.info(
        "PR event received",
        action=action,
        pr=pr["number"],
        repo=repo["full_name"],
    )

    from src.workers.tasks import review_pr

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
        action == "created"
        and "pull_request" in issue
        and MENTION_MARKER in comment_body.lower()
    ):
        return {"status": "ignored", "reason": "not_a_command"}

    log.info(
        "Command received",
        pr=issue["number"],
        author=comment["user"]["login"],
    )

    from src.workers.tasks import handle_command

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

    from src.workers.tasks import handle_command

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


def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

### Task 6: Add Celery Task

**Update:** `src/workers/tasks.py`

Refactored to use `CommandContext` for clean dependency passing:

```python
"""Celery background tasks."""

import asyncio

import structlog

from ..agents.graph import graph
from ..agents.state import PRContext
from ..chat.commands import CommandType
from ..chat.context import CommandContext
from ..chat.handler import CommandHandler
from ..chat.parser import parse_command
from ..app.services.github import GitHubService
from .celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3)
def review_pr(self, owner: str, repo: str, pr_number: int, installation_id: int):
    """Run the review workflow for a PR."""

    async def _run():
        log.info("Starting review", owner=owner, repo=repo, pr=pr_number)

        initial_state = {
            "context": PRContext(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                title="",
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

        return {
            "status": "completed",
            "review_id": result.get("review_id"),
            "comment_count": len(result.get("final_comments", [])),
            "errors": result.get("errors", []),
        }

    try:
        return asyncio.run(_run())
    except Exception as e:
        log.exception("Review failed")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def handle_command(
    self,
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
    in_reply_to_id: int | None = None,
):
    """
    Handle @reviewer command from PR comment.

    This task:
    1. Parses the command from the comment body
    2. Creates a CommandContext with all necessary info
    3. Dispatches to the appropriate handler
    4. Posts the response as a reply
    """
    try:
        asyncio.run(
            _process_command(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                comment_id=comment_id,
                comment_body=comment_body,
                author=author,
                installation_id=installation_id,
                in_reply_to_id=in_reply_to_id,
            )
        )
    except Exception as e:
        log.exception("Command handling failed")
        raise self.retry(exc=e, countdown=30)


async def _process_command(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
    in_reply_to_id: int | None,
) -> None:
    """Async implementation of command processing."""
    log.info("Processing command", pr=pr_number, author=author)

    # 1. Parse command
    parsed = parse_command(comment_body)
    if not parsed:
        log.debug("No valid command found", body=comment_body[:100])
        return

    # 2. Create unified context
    ctx = CommandContext(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        comment_id=comment_id,
        author=author,
        target=parsed.target,
        in_reply_to_id=in_reply_to_id,
    )

    # 3. Execute command
    github = GitHubService(installation_id)
    handler = CommandHandler(github)
    response = await handler.handle(command_type=parsed.type, ctx=ctx)

    # 4. Post response
    formatted_response = f"@{author}\n\n{response}"

    if in_reply_to_id:
        await github.create_review_comment_reply(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            comment_id=in_reply_to_id,
            body=formatted_response,
        )
    else:
        await github.create_issue_comment(
            owner=owner,
            repo=repo,
            issue_number=pr_number,
            body=formatted_response,
        )

    log.info("Command completed", command=parsed.type.value, pr=pr_number)
```

---

### Task 7: Update Review Comments (Add CTA)

**Update:** `src/agents/nodes/github_publisher.py`

Refactored with Enum for severity and cleaner formatting:

```python
"""GitHub publisher node with CTA for on-demand commands."""

from enum import StrEnum

import structlog

from ...app.services.github import GitHubService
from ..state import GraphState, ReviewComment

log = structlog.get_logger()


class Severity(StrEnum):
    """Review comment severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


# Emoji mapping for severity levels
SEVERITY_EMOJI: dict[str, str] = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
    Severity.SUGGESTION: "💡",
}

# CTA template for actionable issues
CTA_TEMPLATE = """\

---
💬 **Commands:**
- `@reviewer fix this` - Generate fix
- `@reviewer explain` - Giải thích chi tiết
"""


async def run(state: GraphState) -> dict:
    """Post review to GitHub."""
    ctx = state["context"]
    comments = state["final_comments"]
    summary = state["summary"]

    log.info("GitHub publisher started", pr=ctx.pr_number, comments=len(comments))

    if not comments:
        log.info("No comments to publish", pr=ctx.pr_number)
        return {"review_id": None}

    github = GitHubService(ctx.installation_id)

    # Format comments for GitHub API
    review_comments = [
        {
            "path": c.file,
            "line": c.line,
            "body": format_comment(c),
        }
        for c in comments
    ]

    # Determine review action based on severity
    has_critical = any(c.severity == Severity.CRITICAL for c in comments)
    event = "REQUEST_CHANGES" if has_critical else "COMMENT"

    try:
        review_id = await github.create_review(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            body=summary,
            comments=review_comments,
            event=event,
        )
        log.info("Review published", review_id=review_id, pr=ctx.pr_number)
        return {"review_id": review_id}

    except Exception as e:
        log.exception("Failed to publish review")
        return {"errors": [str(e)]}


def format_comment(comment: ReviewComment) -> str:
    """
    Format a ReviewComment for GitHub with CTA.

    Args:
        comment: The review comment to format

    Returns:
        Formatted markdown string
    """
    emoji = SEVERITY_EMOJI.get(comment.severity, "•")
    severity_upper = comment.severity.upper()

    # Build comment body
    parts = [
        f"{emoji} **{severity_upper}** ({comment.category})",
        "",
        comment.message,
    ]

    # Add suggestion if present
    if comment.suggestion:
        parts.extend(["", f"**💡 Gợi ý:** {comment.suggestion}"])

    # Add CTA for actionable issues
    if comment.severity in (Severity.CRITICAL, Severity.WARNING):
        parts.append(CTA_TEMPLATE)

    return "\n".join(parts)
```

---

## ✅ Verification Checklist

### Chat Module

- [x] `src/chat/__init__.py` - exports all public APIs
- [x] `src/chat/commands.py` - `CommandType` enum with 5 values
- [x] `src/chat/context.py` - `CommandContext` dataclass
- [x] `src/chat/parser.py` - parses 4 commands with input validation
- [x] `src/chat/prompts.py` - LLM prompt templates
- [x] `src/chat/responses.py` - response templates
- [x] `src/chat/handler.py` - strategy pattern with 5 handlers
- [x] `src/chat/models.py` (optional) - Pydantic models

### GitHub Service

- [x] `get_review_comment` - with retry logic
- [x] `get_file_content_at_pr` - with `_format_code_context` helper
- [x] `create_issue_comment` - with logging
- [x] `create_review_comment_reply` - with logging
- [x] `_headers` helper method

### Webhooks & Tasks

- [x] `webhooks.py` - pattern matching for 3 event types
- [x] `tasks.py` - uses `CommandContext` for clean passing

### Review Publisher

- [x] `github_publisher.py` - `Severity` enum + CTA template

---

## 🧪 Testing

### Unit Tests

```python
# tests/unit/test_chat_parser.py

import pytest
from src.chat.commands import CommandType
from src.chat.parser import parse_command, MAX_COMMENT_LENGTH


class TestParseCommand:
    """Tests for command parser."""

    def test_parse_fix_command(self):
        """Should parse 'fix this' command."""
        result = parse_command("@reviewer fix this")
        assert result is not None
        assert result.type == CommandType.FIX
        assert result.target is None

    def test_parse_fix_command_without_this(self):
        """Should parse 'fix' without 'this'."""
        result = parse_command("@reviewer fix")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_parse_explain_command(self):
        """Should parse 'explain' command."""
        result = parse_command("@reviewer explain")
        assert result is not None
        assert result.type == CommandType.EXPLAIN

    def test_parse_generate_tests(self):
        """Should parse 'generate tests' without target."""
        result = parse_command("@reviewer generate tests")
        assert result is not None
        assert result.type == CommandType.GENERATE_TESTS
        assert result.target is None

    def test_parse_generate_tests_with_target(self):
        """Should parse 'generate tests' with target file."""
        result = parse_command("@reviewer generate tests for auth.py")
        assert result is not None
        assert result.type == CommandType.GENERATE_TESTS
        assert result.target == "auth.py"

    def test_parse_help(self):
        """Should parse 'help' command."""
        result = parse_command("@reviewer help")
        assert result is not None
        assert result.type == CommandType.HELP

    def test_parse_unknown(self):
        """Should return UNKNOWN for unrecognized commands."""
        result = parse_command("@reviewer something else")
        assert result is not None
        assert result.type == CommandType.UNKNOWN

    def test_no_mention_returns_none(self):
        """Should return None if no @reviewer mention."""
        result = parse_command("just a comment")
        assert result is None

    def test_case_insensitive(self):
        """Should handle case-insensitive mentions."""
        result = parse_command("@REVIEWER FIX THIS")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_empty_string_returns_none(self):
        """Should return None for empty string."""
        result = parse_command("")
        assert result is None

    def test_too_long_comment_returns_none(self):
        """Should return None for comments exceeding max length."""
        long_body = "a" * (MAX_COMMENT_LENGTH + 1)
        result = parse_command(long_body)
        assert result is None


# tests/unit/test_command_context.py

from src.chat.context import CommandContext


class TestCommandContext:
    """Tests for CommandContext dataclass."""

    def test_requires_parent_comment_true(self):
        """Should return True when in_reply_to_id is set."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
            in_reply_to_id=456,
        )
        assert ctx.requires_parent_comment is True

    def test_requires_parent_comment_false(self):
        """Should return False when in_reply_to_id is None."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
        )
        assert ctx.requires_parent_comment is False

    def test_immutable(self):
        """Context should be immutable (frozen dataclass)."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
        )
        with pytest.raises(AttributeError):
            ctx.owner = "modified"
```

---

## 📋 Summary

| File                                   | Action | Description                            |
| -------------------------------------- | ------ | -------------------------------------- |
| `src/chat/__init__.py`                 | CREATE | Module exports                         |
| `src/chat/commands.py`                 | CREATE | `CommandType` enum                     |
| `src/chat/context.py`                  | CREATE | `CommandContext` dataclass (immutable) |
| `src/chat/parser.py`                   | CREATE | Parse 4 commands with validation       |
| `src/chat/prompts.py`                  | CREATE | LLM prompt templates                   |
| `src/chat/responses.py`                | CREATE | Response templates                     |
| `src/chat/handler.py`                  | CREATE | Strategy pattern handlers              |
| `src/chat/models.py`                   | CREATE | Pydantic models (optional)             |
| `src/app/services/github.py`           | UPDATE | +5 methods with retry logic            |
| `src/app/api/v1/webhooks.py`           | UPDATE | Pattern matching, 3 event handlers     |
| `src/workers/tasks.py`                 | UPDATE | `handle_command` with `CommandContext` |
| `src/agents/nodes/github_publisher.py` | UPDATE | `Severity` enum + CTA template         |

---

## 🎯 Modern Python Features Used

| Feature                   | Python Version | Usage                               |
| ------------------------- | -------------- | ----------------------------------- |
| `StrEnum`                 | 3.11+          | `CommandType`, `Severity`           |
| `dataclass(slots=True)`   | 3.10+          | Memory-efficient immutable contexts |
| `match` statement         | 3.10+          | Webhook event routing               |
| `X \| None` syntax        | 3.10+          | Type hints                          |
| Walrus operator `:=`      | 3.8+           | Pattern matching in parser          |
| `frozenset`               | 3.x            | Immutable skip patterns             |
| `@staticmethod`           | 3.x            | Helper methods in handlers          |
| `ABC` + `@abstractmethod` | 3.x            | Handler interface                   |

---

**Total new files:** 8  
**Total new code:** ~800 lines  
**Estimated time:** 4-5 hours
