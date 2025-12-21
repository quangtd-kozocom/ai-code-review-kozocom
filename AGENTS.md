# 🤖 AGENTS.md - AI Code Generation Guidelines

> Compact reference for AI coding assistants. Minimal context, maximum clarity.

---

## 📁 Project Structure

```
src/
├── app/           # FastAPI (API layer)
│   ├── api/v1/    # Endpoints (webhooks.py, health.py)
│   ├── services/  # External integrations (github.py, slack.py)
│   ├── config.py  # Pydantic Settings
│   └── main.py    # App entrypoint
├── agents/        # LangGraph (AI layer)
│   ├── nodes/     # Agent implementations
│   ├── prompts/   # LLM prompts
│   ├── graph.py   # Workflow definition
│   └── state.py   # GraphState schema
├── core/          # Shared utilities
│   ├── llm.py     # LLM client
│   └── logging.py # structlog setup
└── workers/       # Celery (async layer)
    ├── celery_app.py
    └── tasks.py
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

**Agent Node:**

```python
async def run(state: GraphState) -> dict:
    """One-line description."""
    # 1. Get dependencies
    # 2. Process each file
    # 3. Return partial state update
    return {"comments": comments}
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

| File        | Purpose      | Key Exports                                              |
| ----------- | ------------ | -------------------------------------------------------- |
| `state.py`  | Data schemas | `GraphState`, `FileChange`, `ReviewComment`, `PRContext` |
| `graph.py`  | Workflow     | `graph`, `create_graph()`                                |
| `config.py` | Settings     | `get_settings()`                                         |
| `llm.py`    | LLM client   | `get_llm()`                                              |

---

## 🔧 Common Operations

### Add New Agent

1. Create `src/agents/nodes/new_agent.py`:

```python
from ..state import GraphState, ReviewComment
from ..prompts.new import PROMPT
from ...core.llm import get_llm

async def run(state: GraphState) -> dict:
    llm = get_llm()
    comments = []
    # Process files, append to comments
    return {"comments": comments}
```

2. Create `src/agents/prompts/new.py`:

```python
PROMPT = """You are a {specialty} expert...
## File: {filename}
## Diff:
{diff}
## Output (JSON only):
{{"findings": [...]}}
"""
```

3. Register in `graph.py`:

```python
g.add_node("new_agent", new_agent.run)
g.add_edge("extract", "new_agent")
g.add_edge("new_agent", "aggregate")
```

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
- Return partial state updates from agents: `{"comments": [...]}`
- Use `structlog` for logging
- Keep prompts in separate files
- Use `get_settings()` for config access

### ❌ Don't

- Don't use `print()` (use `structlog`)
- Don't hardcode API keys
- Don't catch bare `Exception` without logging
- Don't modify state directly (return updates)
- Don't put business logic in endpoints

---

## 📦 Dependencies

```toml
# Core
fastapi, uvicorn, pydantic, pydantic-settings

# AI
langgraph, langchain, langchain-openai, langchain-anthropic

# Background
celery, redis

# Utils
structlog, httpx, tenacity, sentry-sdk
```

Add new: `uv add <package>`

---

## 🧪 Testing

```bash
uv run pytest tests/ -v
```

Test pattern:

```python
class TestFeature:
    def test_something(self, app, mock_settings):
        response = app.get("/endpoint")
        assert response.status_code == 200
```

---

## 🚀 Commands

```bash
make dev      # Run FastAPI (dev mode)
make worker   # Run Celery worker
make test     # Run tests
make lint     # Check code style
make format   # Auto-format code
```
