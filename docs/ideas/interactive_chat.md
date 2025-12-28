# 💬 Interactive PR Chat

> Cho phép developer chat trực tiếp với AI bot trong PR comments

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Trung bình  
**Tham khảo:** CodeRabbit Agentic Chat, GitHub Copilot Chat

---

## 📋 Mô Tả

Developer có thể mention bot trong PR comments để:

1. Hỏi thêm về issues được phát hiện
2. Yêu cầu giải thích code
3. Ra lệnh generate tests/docs
4. Request re-review sau khi sửa

---

## 🎯 Mục Tiêu

- **Primary:** Tăng UX và interactivity với AI reviewer
- **Secondary:** Giảm issues bị ignore vì không rõ
- **Tertiary:** On-demand actions (tests, docs, etc.)

---

## 💡 Supported Commands

### Command Reference

| Command                    | Description                   | Example                                   |
| -------------------------- | ----------------------------- | ----------------------------------------- |
| `@reviewer explain`        | Giải thích chi tiết một issue | `@reviewer explain this security warning` |
| `@reviewer generate tests` | Tạo tests cho file/function   | `@reviewer generate tests for auth.py`    |
| `@reviewer fix`            | Apply suggested fix           | `@reviewer fix this issue`                |
| `@reviewer re-review`      | Review lại sau khi sửa        | `@reviewer re-review`                     |
| `@reviewer summarize`      | Tóm tắt tất cả changes        | `@reviewer summarize`                     |
| `@reviewer help`           | Hiện danh sách commands       | `@reviewer help`                          |

### Example Interactions

```markdown
Developer: @reviewer explain why this is a security issue?

Bot: 🔒 **SQL Injection Explained**

The code `f"SELECT * FROM users WHERE id = {user_id}"` is vulnerable because:

1. **Direct string interpolation**: User input goes directly into SQL
2. **Attacker input**: `user_id = "1 OR 1=1"` would return all users
3. **Data breach risk**: Could leak sensitive user data

**Fix**: Use parameterized queries:
\`cursor.execute("SELECT \* FROM users WHERE id = ?", (user_id,))\`

---

Developer: @reviewer generate tests for validate_email()

Bot: 🧪 **Generated Tests for validate_email()**

\`\`\`python
def test_validate_email_valid():
assert validate_email("user@example.com") == True

def test_validate_email_invalid_format():
assert validate_email("not-an-email") == False

def test_validate_email_empty():
assert validate_email("") == False
\`\`\`

_Copy these to your test file!_
```

---

## 🛠️ Technical Implementation

### 1. Issue Comment Webhook Handler

```python
# src/app/api/v1/webhooks.py

@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    # ... signature validation ...

    payload = await request.json()

    # Handle PR events (existing)
    if x_github_event == "pull_request":
        # ... existing logic ...
        pass

    # NEW: Handle issue/PR comment events
    elif x_github_event == "issue_comment":
        action = payload.get("action")
        comment = payload.get("comment", {})
        body = comment.get("body", "")

        # Check if comment mentions our bot
        if action == "created" and "@reviewer" in body.lower():
            issue = payload.get("issue", {})

            # Only handle PR comments (not regular issues)
            if "pull_request" in issue:
                from ...workers.tasks import handle_chat_command
                handle_chat_command.delay(
                    owner=payload["repository"]["owner"]["login"],
                    repo=payload["repository"]["name"],
                    pr_number=issue["number"],
                    comment_id=comment["id"],
                    comment_body=body,
                    author=comment["user"]["login"],
                    installation_id=payload["installation"]["id"],
                )
                return {"status": "queued", "type": "chat_command"}

    return {"status": "ignored", "event": x_github_event}
```

### 2. Chat Command Parser

```python
# src/chat/parser.py

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class ChatCommand:
    action: str
    target: Optional[str] = None
    context: Optional[str] = None
    raw: str = ""


COMMAND_PATTERNS = [
    (r"@reviewer\s+explain\s+(.*)", "explain"),
    (r"@reviewer\s+generate\s+tests?\s+(?:for\s+)?(.*)", "generate_tests"),
    (r"@reviewer\s+fix\s+(.*)", "fix"),
    (r"@reviewer\s+re-?review", "re_review"),
    (r"@reviewer\s+summarize", "summarize"),
    (r"@reviewer\s+help", "help"),
]


def parse_command(body: str) -> ChatCommand | None:
    """Parse @reviewer command from comment body."""
    body_lower = body.lower().strip()

    for pattern, action in COMMAND_PATTERNS:
        match = re.search(pattern, body_lower)
        if match:
            target = match.group(1).strip() if match.lastindex else None
            return ChatCommand(
                action=action,
                target=target,
                raw=body,
            )

    # Fallback: treat as general question
    if "@reviewer" in body_lower:
        return ChatCommand(
            action="question",
            context=body.replace("@reviewer", "").strip(),
            raw=body,
        )

    return None
```

### 3. Chat Handler

```python
# src/chat/handler.py

from ..core.llm import get_llm
from ..app.services.github import GitHubService
from .parser import ChatCommand


class ChatHandler:
    def __init__(self, github: GitHubService):
        self.github = github
        self.llm = get_llm()

    async def handle(self, command: ChatCommand, pr_context: dict) -> str:
        """Handle a chat command and return response."""

        handlers = {
            "explain": self._handle_explain,
            "generate_tests": self._handle_generate_tests,
            "fix": self._handle_fix,
            "re_review": self._handle_re_review,
            "summarize": self._handle_summarize,
            "help": self._handle_help,
            "question": self._handle_question,
        }

        handler = handlers.get(command.action, self._handle_unknown)
        return await handler(command, pr_context)

    async def _handle_explain(self, cmd: ChatCommand, ctx: dict) -> str:
        """Explain an issue in detail."""
        prompt = f"""
        The developer asked for an explanation about: {cmd.target}

        PR Context:
        - Title: {ctx['title']}
        - Files changed: {ctx['files']}

        Previous review comments:
        {ctx.get('review_comments', 'None')}

        Provide a clear, educational explanation. Include:
        1. Why this is an issue
        2. What could go wrong
        3. How to fix it
        4. Example of correct code if relevant
        """

        response = await self.llm.ainvoke(prompt)
        return self._format_response("🔍 Explanation", response.content)

    async def _handle_generate_tests(self, cmd: ChatCommand, ctx: dict) -> str:
        """Generate tests for specified file/function."""
        # Similar to test_generator.py but for specific target
        prompt = f"""
        Generate pytest unit tests for: {cmd.target}

        From this PR's code changes:
        {ctx.get('diff', '')}

        Include happy path, edge cases, and error cases.
        """

        response = await self.llm.ainvoke(prompt)
        return self._format_response("🧪 Generated Tests", response.content)

    async def _handle_help(self, cmd: ChatCommand, ctx: dict) -> str:
        """Show available commands."""
        return """## 🤖 AI Reviewer Commands

| Command | Description |
|---------|-------------|
| `@reviewer explain <issue>` | Get detailed explanation of an issue |
| `@reviewer generate tests for <file>` | Generate unit tests |
| `@reviewer fix <issue>` | Apply suggested fix |
| `@reviewer re-review` | Review again after changes |
| `@reviewer summarize` | Summarize all PR changes |
| `@reviewer help` | Show this help message |

**Tips:**
- Reply to a specific review comment for context
- Be specific about what you want explained or generated
"""

    def _format_response(self, title: str, content: str) -> str:
        return f"## {title}\n\n{content}"
```

### 4. Chat Task

```python
# src/workers/tasks.py

@celery_app.task
def handle_chat_command(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
):
    """Handle @reviewer chat command."""
    import asyncio
    asyncio.run(_async_handle_chat(
        owner, repo, pr_number, comment_id,
        comment_body, author, installation_id
    ))


async def _async_handle_chat(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
):
    from ..chat.parser import parse_command
    from ..chat.handler import ChatHandler

    # Parse command
    command = parse_command(comment_body)
    if not command:
        return

    github = GitHubService(installation_id)

    # Get PR context
    pr_details = await github.get_pr_details(owner, repo, pr_number)
    pr_files = await github.get_pr_files(owner, repo, pr_number)

    pr_context = {
        "title": pr_details["title"],
        "files": [f["filename"] for f in pr_files],
        "diff": "\n".join(f.get("patch", "") for f in pr_files[:3]),  # Limit
    }

    # Handle command
    handler = ChatHandler(github)
    response = await handler.handle(command, pr_context)

    # Reply to the comment
    await github.create_pr_comment(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        body=f"@{author}\n\n{response}",
    )
```

---

## 🔐 Security Considerations

1. **Rate limiting:** Limit commands per user per PR
2. **Permission check:** Verify user has access to PR
3. **Prompt injection:** Sanitize user input in prompts
4. **Context leakage:** Don't expose secrets from code

---

## ✅ Acceptance Criteria

1. [ ] Bot responds to @reviewer mentions in PR comments
2. [ ] Supports explain, generate tests, help commands
3. [ ] Response posted as reply to original comment
4. [ ] Context-aware (knows about PR files and review)
5. [ ] Rate limited to prevent abuse

---

## 📊 Metrics

| Metric               | Target       |
| -------------------- | ------------ |
| Response time        | < 15 seconds |
| Command success rate | > 95%        |
| User satisfaction    | > 4/5        |
| Commands per PR      | 2-5 average  |

---

## 🔮 Future Enhancements

1. **Threaded conversations:** Multi-turn discussions
2. **Slash commands:** `/reviewer` in addition to @mention
3. **DM support:** Chat via Slack DM
4. **Proactive suggestions:** Bot initiates based on patterns
5. **Action buttons:** GitHub reaction-based commands
