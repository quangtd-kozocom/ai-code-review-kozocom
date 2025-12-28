# 🔧 Autofix On-Demand Commands - Cách hoạt động

## 1. Tổng quan

Autofix là tính năng cho phép developer **tương tác trực tiếp** với AI Reviewer thông qua các commands trong PR comments. Thay vì chỉ nhận passive review, developer có thể yêu cầu AI:

- **Fix code** - Generate suggested fix cho issue
- **Explain** - Giải thích chi tiết về vấn đề
- **Generate tests** - Tạo unit tests cho code changes
- **Help** - Xem danh sách commands

```
┌─────────────────────────────────────────────────────────────────┐
│                     Autofix Flow Overview                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Developer                AI Reviewer               GitHub      │
│      │                         │                        │        │
│      │  "@reviewer fix this"   │                        │        │
│      │ ───────────────────────▶│                        │        │
│      │                         │ Parse command          │        │
│      │                         │ Get parent comment     │        │
│      │                         │ Fetch file content     │        │
│      │                         │ Generate fix (LLM)     │        │
│      │                         │                        │        │
│      │                         │  Post suggestion       │        │
│      │                         │───────────────────────▶│        │
│      │                         │                        │        │
│      │◀─────────────────────────────────────────────────│        │
│      │        Notification + Suggested fix             │        │
│      │                                                  │        │
│      │  Click "Commit suggestion"                       │        │
│      │ ────────────────────────────────────────────────▶│        │
│      │                                                  │        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Kiến trúc hệ thống

### 2.1. Module Structure

```
src/
├── chat/                          # ◀─── NEW: Chat module
│   ├── __init__.py               # Public exports
│   ├── commands.py               # CommandType StrEnum
│   ├── context.py                # CommandContext dataclass
│   ├── parser.py                 # Parse @reviewer commands
│   ├── prompts.py                # LLM prompt templates
│   ├── responses.py              # Response templates
│   ├── handler.py                # Strategy pattern handlers
│   └── models.py                 # Pydantic models (optional)
│
├── app/
│   ├── api/v1/
│   │   └── webhooks.py           # ◀─── UPDATED: Handle 3 event types
│   └── services/
│       └── github.py             # ◀─── UPDATED: +5 new methods
│
├── workers/
│   └── tasks.py                  # ◀─── UPDATED: handle_command task
│
└── agents/nodes/
    └── github_publisher.py       # ◀─── UPDATED: CTA in comments
```

### 2.2. Component Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          WEBHOOK LAYER                              │
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │  pull_request   │   │  issue_comment  │   │ review_comment   │  │
│  │    (review)     │   │   (commands)    │   │   (commands)     │  │
│  └────────┬────────┘   └────────┬────────┘   └────────┬─────────┘  │
│           │                     │                     │             │
│           │                     └──────────┬──────────┘             │
│           │                                │                        │
│           ▼                                ▼                        │
│   ┌──────────────┐                ┌──────────────┐                 │
│   │  review_pr   │                │handle_command│                 │
│   │    (task)    │                │    (task)    │                 │
│   └──────────────┘                └──────┬───────┘                 │
│                                          │                          │
└──────────────────────────────────────────┼──────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          CHAT MODULE                                │
│                                                                     │
│   ┌─────────────┐      ┌─────────────────┐      ┌───────────────┐  │
│   │   Parser    │─────▶│ CommandContext  │─────▶│   Handler     │  │
│   │             │      │                 │      │  (Strategy)   │  │
│   └─────────────┘      └─────────────────┘      └───────┬───────┘  │
│                                                         │           │
│                              ┌──────────────────────────┤           │
│                              │                          │           │
│                              ▼                          ▼           │
│                   ┌─────────────────┐        ┌─────────────────┐   │
│                   │  FixHandler     │        │ ExplainHandler  │   │
│                   │  TestsHandler   │        │ HelpHandler     │   │
│                   └────────┬────────┘        └────────┬────────┘   │
│                            │                          │             │
└────────────────────────────┼──────────────────────────┼─────────────┘
                             │                          │
                             ▼                          ▼
                    ┌──────────────────────────────────────┐
                    │            LLM (Gemini)              │
                    │         Generate response            │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │          GitHub Service              │
                    │     Post reply with suggestion       │
                    └──────────────────────────────────────┘
```

---

## 3. Luồng xử lý chi tiết

### 3.1. Command Detection Flow

```python
# Webhook receives event
event_type = "pull_request_review_comment"  # or "issue_comment"
comment_body = "@reviewer fix this"

# Pattern matching in webhooks.py
match event_type:
    case "pull_request_review_comment":
        if "@reviewer" in comment_body.lower():
            # Queue handle_command task
            handle_command.delay(
                owner="user",
                repo="repo",
                pr_number=123,
                comment_body=comment_body,
                in_reply_to_id=456,  # Parent comment ID
                ...
            )
```

### 3.2. Command Parsing Flow

```python
# parser.py
body = "@reviewer fix this"

# Step 1: Validate input
if not body or len(body) > MAX_COMMENT_LENGTH:
    return None

# Step 2: Check mention marker
if "@reviewer" not in body.lower():
    return None

# Step 3: Match against patterns (pre-compiled regex)
for cmd_type, pattern in _PATTERNS.items():
    if match := pattern.search(body):
        return ParsedCommand(type=cmd_type, ...)

# Result
ParsedCommand(type=CommandType.FIX, target=None, raw="@reviewer fix this")
```

### 3.3. Handler Execution Flow

```python
# handler.py - Strategy Pattern
class CommandHandler:
    _handlers = {
        CommandType.FIX: FixCommandHandler,
        CommandType.EXPLAIN: ExplainCommandHandler,
        CommandType.GENERATE_TESTS: GenerateTestsCommandHandler,
        CommandType.HELP: HelpCommandHandler,
        CommandType.UNKNOWN: UnknownCommandHandler,
    }

    async def handle(self, command_type, ctx):
        handler_cls = self._handlers[command_type]
        handler = handler_cls(self.github)
        return await handler.execute(ctx)
```

### 3.4. Fix Command Flow (Detail)

````
┌─────────────────────────────────────────────────────────────────┐
│                    Fix Command Execution                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Validate Context                                             │
│     │                                                            │
│     │  ctx.requires_parent_comment?                              │
│     │  ├── No  → Return error: "Reply to review comment"         │
│     │  └── Yes → Continue                                        │
│     ▼                                                            │
│  2. Fetch Parent Comment                                         │
│     │                                                            │
│     │  github.get_review_comment(in_reply_to_id)                 │
│     │  └── Returns: {path, line, body (issue description)}       │
│     ▼                                                            │
│  3. Fetch Code Context                                           │
│     │                                                            │
│     │  github.get_file_content_at_pr(file, line, context=5)      │
│     │  └── Returns:                                              │
│     │      "    10: def process(data):\n"                        │
│     │      ">>> 11:     result = data.split(',')\n"  ← Issue     │
│     │      "    12:     return result\n"                         │
│     ▼                                                            │
│  4. Generate Fix (LLM)                                           │
│     │                                                            │
│     │  Prompt: FIX_PROMPT.format(                                │
│     │      issue_description=parent.body,                        │
│     │      file_path=parent.path,                                │
│     │      line=parent.line,                                     │
│     │      code_context=context                                  │
│     │  )                                                         │
│     │                                                            │
│     │  LLM Response:                                             │
│     │  {"fixed_code": "result = data.split(',') if data else []",│
│     │   "explanation": "Added null check"}                       │
│     ▼                                                            │
│  5. Format Response                                              │
│     │                                                            │
│     │  ```suggestion                                             │
│     │  result = data.split(',') if data else []                  │
│     │  ```                                                       │
│     │                                                            │
│     │  **Giải thích:** Added null check                          │
│     ▼                                                            │
│  6. Post Reply                                                   │
│     │                                                            │
│     │  github.create_review_comment_reply(                       │
│     │      pr_number=123,                                        │
│     │      comment_id=in_reply_to_id,                            │
│     │      body=formatted_response                               │
│     │  )                                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
````

---

## 4. Các Commands chi tiết

### 4.1. `@reviewer fix this`

**Mục đích:** Generate code fix cho issue được highlight trong review comment.

**Điều kiện:**

- Must reply to a **review comment** (comment on code line)
- Parent comment contains issue description

**Output:** GitHub suggestion block (có thể commit trực tiếp)

````markdown
## 🔧 Suggested Fix

```suggestion
fixed_code_here
```
````

**Giải thích:** Brief explanation

---

_Click "Commit suggestion" để apply fix này._

````

---

### 4.2. `@reviewer explain`

**Mục đích:** Giải thích chi tiết về issue cho developer hiểu rõ hơn.

**Điều kiện:**
- Must reply to a **review comment**

**Output:** Educational explanation with:
1. What is the problem?
2. Why is it a problem?
3. How to fix it?
4. Example code

---

### 4.3. `@reviewer generate tests`

**Mục đích:** Generate unit tests cho code changes trong PR.

**Điều kiện:**
- Can be used anywhere in PR (issue comment or review comment)
- Optional target: `@reviewer generate tests for auth.py`

**Output:** pytest/jest test file

```python
## 🧪 Generated Unit Tests

**Files analyzed:** auth.py, utils.py

```python
import pytest

def test_login_success():
    """Should authenticate valid user."""
    ...
````

````

---

### 4.4. `@reviewer help`

**Mục đích:** Hiển thị danh sách commands có sẵn.

**Output:** Command reference table

---

## 5. Design Patterns sử dụng

### 5.1. Strategy Pattern

```python
# Base handler interface
class BaseCommandHandler(ABC):
    @abstractmethod
    async def execute(self, ctx: CommandContext) -> str:
        ...

# Concrete strategies
class FixCommandHandler(BaseCommandHandler):
    async def execute(self, ctx):
        # Fix-specific logic
        ...

class ExplainCommandHandler(BaseCommandHandler):
    async def execute(self, ctx):
        # Explain-specific logic
        ...

# Context (router)
class CommandHandler:
    def __init__(self, github):
        self.github = github

    async def handle(self, command_type, ctx):
        handler = self._handlers[command_type](self.github)
        return await handler.execute(ctx)
````

**Lợi ích:**

- ✅ Easy to add new commands
- ✅ Each handler is independent
- ✅ Open/Closed principle

### 5.2. Command Pattern

```python
@dataclass(slots=True, frozen=True)
class CommandContext:
    """Unified context for all handlers."""
    owner: str
    repo: str
    pr_number: int
    comment_id: int
    author: str
    target: str | None = None
    in_reply_to_id: int | None = None

    @property
    def requires_parent_comment(self) -> bool:
        return self.in_reply_to_id is not None
```

**Lợi ích:**

- ✅ All handlers receive same context
- ✅ Immutable (frozen dataclass)
- ✅ Type-safe with slots

### 5.3. Template Method

````python
# Prompts separated from logic
# prompts.py
FIX_PROMPT = """\
You are an expert code fixer.
...
"""

# responses.py
FIX_SUCCESS = """\
## 🔧 Suggested Fix

```suggestion
{fixed_code}
````

"""

````

**Lợi ích:**
- ✅ Easy to modify prompts without touching handler code
- ✅ Consistent response formatting
- ✅ i18n ready

---

## 6. Error Handling

### 6.1. Input Validation

```python
def parse_command(body: str) -> ParsedCommand | None:
    # Validate type
    if not body or not isinstance(body, str):
        return None

    # Validate length (prevent abuse)
    if len(body) > MAX_COMMENT_LENGTH:
        return None

    # Continue processing...
````

### 6.2. Context Validation

```python
async def execute(self, ctx: CommandContext) -> str:
    if not ctx.requires_parent_comment:
        return ERROR_NO_PARENT_COMMENT

    # Continue...
```

### 6.3. API Error Handling

```python
try:
    parent = await self.github.get_review_comment(...)
except HTTPStatusError as e:
    log.error("GitHub API error", status=e.response.status_code)
    return f"❌ GitHub API error: {e.response.status_code}"
```

### 6.4. Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def get_review_comment(self, ...):
    # API call with automatic retry
```

---

## 7. Performance Considerations

### 7.1. Pre-compiled Regex

```python
# Compile once at module load
_PATTERNS: dict[CommandType, re.Pattern[str]] = {
    CommandType.FIX: re.compile(r"@reviewer\s+fix(?:\s+this)?", re.IGNORECASE),
    # ...
}
```

### 7.2. Async All The Way

- All GitHub API calls are `async`
- All handlers are `async def execute()`
- No blocking I/O

### 7.3. Memory Efficient

```python
@dataclass(slots=True, frozen=True)
class CommandContext:
    # slots=True reduces memory footprint
    # frozen=True allows caching
```

---

## 8. Sequence Diagram

```
┌────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐     ┌──────┐
│Developer│    │ GitHub  │     │ Webhook  │     │ Celery  │     │ LLM  │
└────┬───┘     └────┬────┘     └────┬─────┘     └────┬────┘     └──┬───┘
     │              │               │                │              │
     │ Comment:     │               │                │              │
     │ "@reviewer   │               │                │              │
     │  fix this"   │               │                │              │
     │──────────────▶               │                │              │
     │              │               │                │              │
     │              │ Webhook POST  │                │              │
     │              │──────────────▶│                │              │
     │              │               │                │              │
     │              │               │ handle_command │              │
     │              │               │ .delay()       │              │
     │              │               │───────────────▶│              │
     │              │               │                │              │
     │              │               │                │ Parse cmd    │
     │              │               │                │ Get context  │
     │              │               │                │              │
     │              │ GET comment   │                │              │
     │              │◀──────────────────────────────│              │
     │              │──────────────────────────────▶│              │
     │              │               │                │              │
     │              │ GET file      │                │              │
     │              │◀──────────────────────────────│              │
     │              │──────────────────────────────▶│              │
     │              │               │                │              │
     │              │               │                │ Generate fix │
     │              │               │                │─────────────▶│
     │              │               │                │◀─────────────│
     │              │               │                │              │
     │              │ POST reply    │                │              │
     │              │◀──────────────────────────────│              │
     │              │               │                │              │
     │ Notification │               │                │              │
     │◀─────────────│               │                │              │
     │              │               │                │              │
```

---

**Tiếp theo:** [02-setup-guide.md](./02-setup-guide.md) - Hướng dẫn cài đặt và cấu hình
