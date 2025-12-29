# 💬 Interactive PR Chat

> **(✅ IMPLEMENTED)** - Module đã được implement trong `src/chat/`

**Status:** ✅ Đã hoàn thành  
**Implementation:** `src/chat/` module

---

## 📋 Đã Implement

### Supported Commands

| Command             | Description                 | Handler                       |
| ------------------- | --------------------------- | ----------------------------- |
| `@reviewer fix`     | Generate code fix for issue | `FixCommandHandler`           |
| `@reviewer explain` | Explain issue in detail     | `ExplainCommandHandler`       |
| `@reviewer tests`   | Generate unit tests         | `GenerateTestsCommandHandler` |
| `@reviewer help`    | Show available commands     | `HelpCommandHandler`          |

### Architecture

```
src/chat/
├── __init__.py
├── commands.py      # CommandType enum
├── parser.py        # Parse @reviewer commands
├── handler.py       # Command handlers (Strategy pattern)
├── context.py       # CommandContext data class
├── prompts.py       # LLM prompts
├── responses.py     # Response templates
└── models.py        # Data models
```

---

## 🔜 Planned Extensions

Xem các file mới để biết thêm commands sẽ được thêm:

| Command                  | Status     | File                                               |
| ------------------------ | ---------- | -------------------------------------------------- |
| `@reviewer docstrings`   | 📋 Planned | [generate_docstrings.md](./generate_docstrings.md) |
| `@reviewer re-review`    | 📋 Planned | [re_review.md](./re_review.md)                     |
| `@reviewer summarize`    | 📋 Planned | [summarize_pr.md](./summarize_pr.md)               |
| `@reviewer pause/resume` | 📋 Planned | [pause_resume.md](./pause_resume.md)               |
| `@reviewer resolve`      | 📋 Planned | [resolve_comments.md](./resolve_comments.md)       |

---

## 📚 Technical Reference

### Command Parser (`parser.py`)

```python
@dataclass(slots=True, frozen=True)
class ParsedCommand:
    type: CommandType
    target: str | None = None
    raw: str = ""

def parse_command(body: str) -> ParsedCommand | None:
    """Parse @reviewer command from comment body."""
```

### Command Handler (`handler.py`)

```python
class CommandHandler:
    """Main handler using strategy pattern."""

    async def handle(
        self,
        command_type: CommandType,
        ctx: CommandContext
    ) -> str:
        """Route to appropriate handler."""
```

### Usage in Webhook

```python
# src/app/api/v1/webhooks.py

if x_github_event == "issue_comment":
    if "@reviewer" in body.lower():
        handle_chat_command.delay(...)
```

---

## 🔗 Related Documentation

- [CodeRabbit Commands](https://docs.coderabbit.ai/guides/commands)
- Original implementation task: `docs/code-rabbit-inspiration/autofix/`
