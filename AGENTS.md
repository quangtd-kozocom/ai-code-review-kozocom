# 🤖 AGENTS.md - AI Code Generation Guidelines

> Compact reference for AI coding assistants. Minimal context, maximum clarity.

---

## 📁 Project Structure

```
src/
├── app/              # FastAPI (API layer)
│   ├── api/v1/       # Endpoints (webhooks.py, health.py)
│   ├── services/     # External integrations (github.py, slack.py)
│   ├── config.py     # Pydantic Settings
│   └── main.py       # App entrypoint
├── agents/           # LangGraph (AI layer - PR Review)
│   ├── nodes/        # Agent implementations
│   │   ├── acknowledger.py      # Send initial "processing" notification
│   │   ├── context_extractor.py # Extract file changes from PR
│   │   ├── security_agent.py    # Security analysis
│   │   ├── logic_agent.py       # Logic/bugs analysis
│   │   ├── style_agent.py       # Code style analysis
│   │   ├── aggregator.py        # Merge & dedupe comments
│   │   ├── github_publisher.py  # Post review to GitHub
│   │   └── slack_reporter.py    # Send Slack notification
│   ├── prompts/      # LLM prompts (security.py, logic.py, style.py)
│   ├── models.py     # LLM structured output models
│   ├── graph.py      # Workflow definition
│   └── state.py      # GraphState schema
├── chat/             # On-Demand Commands (AI layer)
│   ├── handlers/     # Command handlers
│   │   ├── base.py           # Base handler abstract class
│   │   ├── fix.py            # @reviewer fix - Generate code fixes
│   │   ├── explain.py        # @reviewer explain - Explain issues
│   │   ├── generate_tests.py # @reviewer tests - Generate unit tests
│   │   └── simple.py         # Simple text response handler
│   ├── commands.py   # Command enum (fix, explain, tests, help)
│   ├── context.py    # CommandContext dataclass
│   ├── handler.py    # Main command dispatcher
│   ├── models.py     # GitHub API models (ReviewComment, FileChange)
│   ├── parser.py     # Parse @reviewer commands from comments
│   ├── prompts.py    # LLM prompts for chat commands
│   └── responses.py  # Response templates
├── core/             # Shared utilities
│   ├── constants.py  # LANGUAGE_MAP, SKIP_PATTERNS, IGNORE_PATTERNS
│   ├── llm.py        # LLM client (get_llm)
│   └── logging.py    # structlog setup
└── workers/          # Celery (async layer)
    ├── celery_app.py
    └── tasks.py      # PR review & command tasks
```

---

## 🎯 Coding Standards

### Python

- **Version:** 3.13+
- **Style:** Ruff (line-length=100)
- **Types:** Use type hints everywhere
- **Imports:** stdlib → third-party → local (auto-sorted by ruff)

### Naming

```python
# Files: snake_case
context_extractor.py

# Classes: PascalCase
class ReviewComment(BaseModel):

# Functions/vars: snake_case
async def run(state: GraphState) -> dict:

# Constants: UPPER_SNAKE
MAX_PER_FILE = 10
```

### Patterns

**Service Class:**

```python
class GitHubService:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        # implementation
```

**Agent Node (PR Review):**

```python
from ..state import GraphState, ReviewComment
from ..models import AgentFindings
from ...core.llm import get_llm

async def run(state: GraphState) -> dict:
    """One-line description."""
    llm = get_llm().with_structured_output(AgentFindings)
    # 1. Get dependencies
    # 2. Process each file with structured output
    # 3. Return partial state update
    return {"comments": comments}
```

**Command Handler (On-Demand):**

```python
from .base import BaseHandler
from .context import CommandContext
from ..agents.models import FixResult
from ..core.llm import get_llm

class FixHandler(BaseHandler):
    """Handle @reviewer fix commands."""

    async def handle(self, ctx: CommandContext) -> str:
        llm = get_llm().with_structured_output(FixResult)
        # 1. Build prompt with context
        # 2. Call LLM with structured output
        # 3. Format response
        return formatted_response
```

**Pydantic Model (LLM Structured Output):**

```python
from pydantic import BaseModel, Field
from typing import Literal

class AgentFinding(BaseModel):
    """A single finding from a code review agent."""

    line: int = Field(..., description="Line number", ge=1)
    severity: Literal["critical", "warning", "info", "suggestion"]
    message: str = Field(..., description="Issue description", min_length=10)
    suggestion: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
```

**Config:**

```python
class Settings(BaseSettings):
    SOME_VAR: str
    OPTIONAL_VAR: str | None = None

    model_config = SettingsConfigDict(env_file=".env")
```

---

## ⚡ Key Files Reference

| File                | Purpose             | Key Exports                                                   |
| ------------------- | ------------------- | ------------------------------------------------------------- |
| `agents/state.py`   | Workflow state      | `GraphState`, `FileChange`, `ReviewComment`, `PRContext`      |
| `agents/models.py`  | LLM output schemas  | `AgentFinding`, `AgentFindings`, `FixResult`, `ExplainResult` |
| `agents/graph.py`   | PR review workflow  | `graph`, `create_graph()`                                     |
| `chat/commands.py`  | Command definitions | `Command` enum (FIX, EXPLAIN, TESTS, HELP)                    |
| `chat/handler.py`   | Command dispatcher  | `CommandHandler`                                              |
| `chat/context.py`   | Command context     | `CommandContext` dataclass                                    |
| `core/constants.py` | Shared constants    | `LANGUAGE_MAP`, `SKIP_PATTERNS`, `get_language_from_path()`   |
| `core/llm.py`       | LLM client          | `get_llm()`                                                   |
| `app/config.py`     | Settings            | `get_settings()`                                              |
| `workers/tasks.py`  | Celery tasks        | `process_pr_review_task`, `process_command_task`              |

---

## 🔧 Common Operations

### Add New Review Agent

1. Create `src/agents/nodes/new_agent.py`:

```python
from ..state import GraphState, ReviewComment
from ..models import AgentFindings
from ..prompts.new import PROMPT
from ...core.llm import get_llm

async def run(state: GraphState) -> dict:
    llm = get_llm().with_structured_output(AgentFindings)
    comments = []
    for file in state["files"]:
        result = await llm.ainvoke(PROMPT.format(...))
        # Convert findings to comments
    return {"comments": comments}
```

2. Create `src/agents/prompts/new.py`:

```python
PROMPT = """You are a {specialty} expert analyzing code for issues.

## File: {filename}
## Language: {language}
## Diff:
{diff}

Analyze and return findings as JSON.
"""
```

3. Register in `graph.py`:

```python
g.add_node("new_agent", new_agent.run)
g.add_edge("extract", "new_agent")
g.add_edge("new_agent", "aggregate")
```

### Add New Chat Command

1. Add command to `src/chat/commands.py`:

```python
class Command(Enum):
    FIX = "fix"
    EXPLAIN = "explain"
    TESTS = "tests"
    NEW_CMD = "newcmd"  # Add new command
    HELP = "help"
```

2. Create handler `src/chat/handlers/new_cmd.py`:

```python
from .base import BaseHandler
from ..context import CommandContext

class NewCmdHandler(BaseHandler):
    """Handle @reviewer newcmd commands."""

    async def handle(self, ctx: CommandContext) -> str:
        # Implementation
        return "Response message"
```

3. Register in `src/chat/handlers/__init__.py`:

```python
from .new_cmd import NewCmdHandler

HANDLERS = {
    Command.NEW_CMD: NewCmdHandler(),
    # ...existing handlers
}
```

4. Add prompt to `src/chat/prompts.py` if using LLM.

### Add New Endpoint

```python
# src/app/api/v1/new_endpoint.py
from fastapi import APIRouter

router = APIRouter(prefix="/new", tags=["new"])

@router.get("")
async def get_something():
    return {"data": "value"}
```

Register in `router.py`.

### Add New Service

```python
# src/app/services/new_service.py
import structlog
from ..config import get_settings

log = structlog.get_logger()

class NewService:
    def __init__(self):
        self.settings = get_settings()

    async def do_something(self) -> dict:
        log.info("doing something")
        return {}
```

---

## ⚠️ Do's and Don'ts

### ✅ Do

- Use `async/await` for I/O operations
- Use `llm.with_structured_output(PydanticModel)` for LLM calls
- Return partial state updates from agents: `{"comments": [...]}`
- Use `structlog` for logging
- Keep prompts in separate files (or `prompts.py`)
- Use `get_settings()` for config access
- Use constants from `core/constants.py` (e.g., `LANGUAGE_MAP`)
- Follow BaseHandler pattern for new chat commands

### ❌ Don't

- Don't use `print()` (use `structlog`)
- Don't hardcode API keys
- Don't catch bare `Exception` without logging
- Don't modify state directly (return updates)
- Don't put business logic in endpoints
- Don't parse LLM JSON manually (use structured output)
- Don't duplicate constants (use `core/constants.py`)

---

## 📦 Dependencies

```toml
# Core
fastapi, uvicorn, pydantic, pydantic-settings

# AI
langgraph, langchain, langchain-openai, langchain-anthropic

# GitHub
httpx, PyJWT, cryptography

# Background Tasks
celery[redis], redis

# Utilities
structlog, python-dotenv, tenacity, sentry-sdk[fastapi], slack-sdk
```

Add new: `uv add <package>`

---

## 🧪 Testing

```bash
uv run pytest tests/ -v
```

Test pattern:

```python
import pytest

class TestFeature:
    def test_something(self, app, mock_settings):
        response = app.get("/endpoint")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_async_function(self):
        result = await some_async_function()
        assert result is not None
```

---

## 🚀 Commands

```bash
# Development
make install  # Install dependencies (uv sync)
make dev      # Run FastAPI dev server (--reload)
make worker   # Run Celery worker
make run      # Run FastAPI production

# Code Quality
make lint     # Check code style (ruff check)
make format   # Auto-format code (ruff format)
make test     # Run tests
make clean    # Remove __pycache__ and *.pyc

# Scripts
./scripts/start.sh  # Start all services (FastAPI + Celery)
./scripts/stop.sh   # Stop all services
```

---

## 🔄 Workflows

### PR Review Flow

```
Webhook (PR opened/synchronized)
    ↓
Celery Task: process_pr_review_task
    ↓
LangGraph Workflow:
    acknowledger → context_extractor → [security, logic, style] → aggregator → github_publisher → slack_reporter
```

### Chat Command Flow

```
Webhook (issue_comment created with @reviewer)
    ↓
Parse command (parser.py)
    ↓
Celery Task: process_command_task
    ↓
CommandHandler.handle() → Specific Handler (fix, explain, tests)
    ↓
Post response as GitHub comment
```

---

## 📝 Quick Reference

### Severity Levels

```python
"critical"   # Security vulnerabilities, data loss risks
"warning"    # Bugs, logic errors, performance issues
"info"       # Best practices, improvements
"suggestion" # Style, readability enhancements
```

### Supported Languages

See `core/constants.py` → `LANGUAGE_MAP` for full list:

- Python, JavaScript/TypeScript, Java, Go, Rust, C/C++, Ruby, PHP, etc.

### Chat Commands

| Command             | Description                   |
| ------------------- | ----------------------------- |
| `@reviewer fix`     | Generate fix for the issue    |
| `@reviewer explain` | Explain why this is a problem |
| `@reviewer tests`   | Generate unit tests           |
| `@reviewer help`    | Show available commands       |
