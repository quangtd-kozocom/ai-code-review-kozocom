# 🛠️ Implementation Guide - Auto-Fix Feature

## 📋 Prerequisites

Đảm bảo đã có:

- ✅ MVP Phase 1 hoạt động (webhook, agents, publish)
- ✅ GitHub App với quyền `issue_comment` (read/write)
- ✅ Celery + Redis setup

---

## 🚀 Step-by-Step Implementation

### Step 1: Update GitHub App Permissions

Thêm quyền cho GitHub App:

```yaml
# Required permissions:
- Pull requests: Read & Write
- Issues: Read & Write # NEW - for issue_comment events
- Contents: Read
```

Subscribe to webhook events:

```yaml
- Pull request
- Issue comment # NEW
```

---

### Step 2: Update Webhook Handler

```python
# src/app/api/v1/webhooks.py

@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    settings = get_settings()
    body = await request.body()

    # Validate signature (existing)
    if not _verify_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # ========== EXISTING: Handle pull_request events ==========
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize", "reopened"):
            from ...workers.tasks import review_pr
            review_pr.delay(
                owner=payload["repository"]["owner"]["login"],
                repo=payload["repository"]["name"],
                pr_number=payload["pull_request"]["number"],
                installation_id=payload["installation"]["id"],
            )
            return {"status": "queued", "type": "review"}

    # ========== NEW: Handle issue_comment events ==========
    elif x_github_event == "issue_comment":
        action = payload.get("action")

        # Only handle new comments on PRs
        if action == "created" and "pull_request" in payload.get("issue", {}):
            comment_body = payload["comment"]["body"]

            # Check if comment mentions our bot
            if "@reviewer" in comment_body.lower():
                from ...workers.tasks import handle_command
                handle_command.delay(
                    owner=payload["repository"]["owner"]["login"],
                    repo=payload["repository"]["name"],
                    pr_number=payload["issue"]["number"],
                    comment_id=payload["comment"]["id"],
                    comment_body=comment_body,
                    author=payload["comment"]["user"]["login"],
                    installation_id=payload["installation"]["id"],
                )
                return {"status": "queued", "type": "command"}

    return {"status": "ignored", "event": x_github_event}
```

---

### Step 3: Create Command Parser

```python
# src/chat/__init__.py
from .parser import parse_command
from .handler import CommandHandler

# src/chat/parser.py
import re
from dataclasses import dataclass
from typing import Literal

CommandType = Literal["fix", "generate_tests", "explain", "re_review", "help", "unknown"]


@dataclass
class ParsedCommand:
    """Parsed @reviewer command."""
    type: CommandType
    target: str | None = None  # e.g., file name, function name
    raw: str = ""


def parse_command(body: str) -> ParsedCommand | None:
    """Parse @reviewer command from comment body."""
    body_lower = body.lower().strip()

    # Check if mentions our bot
    if "@reviewer" not in body_lower:
        return None

    # Pattern matching for commands
    patterns = [
        (r"@reviewer\s+fix\s*(this)?", "fix"),
        (r"@reviewer\s+generate\s+tests?\s*(?:for\s+)?(.+)?", "generate_tests"),
        (r"@reviewer\s+explain\s*(this)?", "explain"),
        (r"@reviewer\s+re-?review", "re_review"),
        (r"@reviewer\s+help", "help"),
    ]

    for pattern, cmd_type in patterns:
        match = re.search(pattern, body_lower)
        if match:
            target = match.group(1) if match.lastindex else None
            return ParsedCommand(
                type=cmd_type,
                target=target.strip() if target else None,
                raw=body,
            )

    # Default to unknown if @reviewer mentioned but no valid command
    return ParsedCommand(type="unknown", raw=body)
```

---

### Step 4: Create Command Handler

```python
# src/chat/handler.py
import structlog
from ..core.llm import get_llm
from ..app.services.github import GitHubService
from .parser import ParsedCommand

log = structlog.get_logger()


class CommandHandler:
    """Handle @reviewer commands."""

    def __init__(self, github: GitHubService):
        self.github = github
        self.llm = get_llm()

    async def handle(
        self,
        command: ParsedCommand,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
    ) -> str:
        """Handle command and return response."""

        handlers = {
            "fix": self._handle_fix,
            "generate_tests": self._handle_generate_tests,
            "explain": self._handle_explain,
            "re_review": self._handle_re_review,
            "help": self._handle_help,
            "unknown": self._handle_unknown,
        }

        handler = handlers.get(command.type, self._handle_unknown)
        return await handler(command, owner, repo, pr_number, comment_id)

    async def _handle_fix(
        self,
        command: ParsedCommand,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
    ) -> str:
        """Generate fix for the issue in parent comment."""

        # 1. Get the comment thread context
        parent_comment = await self.github.get_review_comment_thread(
            owner, repo, comment_id
        )

        if not parent_comment:
            return "❌ Không tìm thấy review comment. Vui lòng reply trực tiếp vào một review comment."

        # 2. Get file content around the issue
        file_path = parent_comment.get("path")
        line = parent_comment.get("line") or parent_comment.get("original_line")

        file_content = await self.github.get_file_content(
            owner, repo, pr_number, file_path, line, context_lines=10
        )

        # 3. Generate fix using LLM
        issue_description = parent_comment.get("body", "")

        prompt = f"""You are an expert code fixer.

## Issue from Review:
{issue_description}

## File: {file_path}
## Line: {line}

## Code Context:
```

{file_content}

````

## Task:
Generate a MINIMAL fix for the issue. Only output the fixed line(s).

## Rules:
1. Fix ONLY the problematic code
2. Keep same indentation as original
3. Be concise

## Output (JSON):
{{"fixed_code": "the corrected code line(s)", "explanation": "brief explanation"}}
"""

        response = await self.llm.ainvoke(prompt)
        fix_data = self._parse_fix_response(response.content)

        if not fix_data:
            return "❌ Không thể generate fix. Vui lòng thử lại hoặc sửa thủ công."

        # 4. Format as GitHub suggestion
        return f"""## 🔧 Suggested Fix

```suggestion
{fix_data['fixed_code']}
````

**Giải thích:** {fix_data['explanation']}

---

_Click "Commit suggestion" để apply fix này._
"""

    async def _handle_help(self, *args) -> str:
        """Return help message."""
        return """## 🤖 AI Reviewer Commands

| Command                    | Description                 |
| -------------------------- | --------------------------- |
| `@reviewer fix this`       | Tạo suggested fix cho issue |
| `@reviewer generate tests` | Tạo unit tests cho PR       |
| `@reviewer explain`        | Giải thích chi tiết issue   |
| `@reviewer re-review`      | Review lại PR               |
| `@reviewer help`           | Hiện help này               |

**Tip:** Reply trực tiếp vào review comment để có context tốt hơn.
"""

    async def _handle_unknown(self, command: ParsedCommand, *args) -> str:
        """Handle unknown command."""
        return f"""❓ Không hiểu command: `{command.raw}`

Thử `@reviewer help` để xem danh sách commands.
"""

    def _parse_fix_response(self, content: str) -> dict | None:
        """Parse JSON from LLM response."""
        import json
        try:
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        return None

````

---

### Step 5: Add Celery Task

```python
# src/workers/tasks.py

@celery_app.task
def handle_command(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
):
    """Handle @reviewer command from PR comment."""
    import asyncio
    asyncio.run(_async_handle_command(
        owner, repo, pr_number, comment_id,
        comment_body, author, installation_id
    ))


async def _async_handle_command(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
):
    from ..chat.parser import parse_command
    from ..chat.handler import CommandHandler

    log.info(
        "Handling command",
        pr=pr_number,
        author=author,
        comment=comment_body[:50],
    )

    # Parse command
    command = parse_command(comment_body)
    if not command:
        return

    # Handle command
    github = GitHubService(installation_id)
    handler = CommandHandler(github)

    response = await handler.handle(
        command, owner, repo, pr_number, comment_id
    )

    # Reply to the comment
    await github.create_issue_comment(
        owner=owner,
        repo=repo,
        issue_number=pr_number,  # PR number = issue number
        body=f"@{author}\n\n{response}",
    )

    log.info("Command handled", command=command.type, pr=pr_number)
````

---

### Step 6: Update GitHub Service

```python
# src/app/services/github.py

class GitHubService:
    # ... existing methods ...

    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> int:
        """Create a comment on an issue/PR."""
        token = await self._get_token()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={"body": body},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        path: str,
        line: int,
        context_lines: int = 10,
    ) -> str:
        """Get file content around a specific line."""
        token = await self._get_token()

        # Get PR to find head ref
        pr = await self.get_pr_details(owner, repo, pr_number)
        ref = pr["head"]["sha"]

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.raw+json",
                },
                params={"ref": ref},
            )
            resp.raise_for_status()

            # Get content and extract lines around target
            content = resp.text
            lines = content.split("\n")

            start = max(0, line - context_lines - 1)
            end = min(len(lines), line + context_lines)

            return "\n".join(lines[start:end])
```

---

### Step 7: Update Review Comments (Add CTA)

```python
# src/agents/nodes/github_publisher.py

def _format_comment(c: ReviewComment) -> str:
    """Format comment with CTA for on-demand fix."""
    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵", "suggestion": "💡"}

    body = f"{emoji.get(c.severity, '•')} **{c.severity.upper()}** ({c.category})\n\n"
    body += f"{c.message}\n\n"

    if c.suggestion:
        body += f"**💡 Gợi ý:** {c.suggestion}\n\n"

    # Add CTA for on-demand fix (only for critical/warning)
    if c.severity in ("critical", "warning"):
        body += "---\n"
        body += "*💬 Reply `@reviewer fix this` để tạo suggested fix.*"

    return body
```

---

## ✅ Testing Checklist

- [ ] Webhook nhận `issue_comment` events
- [ ] Command parser nhận dạng đúng commands
- [ ] `@reviewer help` trả về help message
- [ ] `@reviewer fix this` generate fix với suggestion syntax
- [ ] Fix có thể commit từ GitHub UI
- [ ] Error handling cho các edge cases

---

## 📊 Files Summary

| File                  | Action | Description                |
| --------------------- | ------ | -------------------------- |
| `webhooks.py`         | UPDATE | Thêm issue_comment handler |
| `chat/__init__.py`    | CREATE | Module init                |
| `chat/parser.py`      | CREATE | Command parser             |
| `chat/handler.py`     | CREATE | Command handlers           |
| `tasks.py`            | UPDATE | Thêm handle_command task   |
| `github.py`           | UPDATE | Thêm comment methods       |
| `github_publisher.py` | UPDATE | Thêm CTA trong comments    |
