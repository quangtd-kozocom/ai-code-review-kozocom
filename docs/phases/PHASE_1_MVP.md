# 🚀 Phase 1: MVP - Core Review System

**Thời gian:** 4 tuần  
**Mục tiêu:** Hệ thống AI Code Review hoạt động end-to-end.

---

## 📋 Scope

### ✅ Implement

- Webhook receiver + HMAC signature validation
- LangGraph multi-agent workflow (3 agents: Security, Style, Logic)
- GitHub API: fetch PR diff, post review comments
- Slack notification cơ bản
- Logging với structlog + Sentry

### ❌ KHÔNG implement (defer to Phase 2/3)

- Database persistence
- Redis caching
- RAG / Vector embeddings
- YAML config per repo
- Interactive chat

---

## 🛠️ Tech Stack

```yaml
Runtime:
  python: "3.13"
  framework: FastAPI 0.115.x
  server: uvicorn 0.32.x
  package_manager: uv

AI/LLM:
  orchestration: LangGraph 0.2.x
  llm: LangChain 0.3.x + OpenAI/Anthropic
  primary_model: gpt-4o
  fallback_model: gpt-4o-mini

Background Tasks:
  queue: Celery 5.4.x
  broker: Upstash Redis (managed)

Integrations:
  github: httpx (async HTTP client)
  slack: slack-sdk

Observability:
  logging: structlog
  errors: Sentry

Deployment:
  platform: Railway / Render
  redis: Upstash (managed)
```

---

## 📁 Project Structure

```
ai-code-reviewer/
├── src/
│   ├── app/                          # FastAPI Application
│   │   ├── __init__.py
│   │   ├── main.py                   # App entrypoint
│   │   ├── config.py                 # Settings (env vars)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py         # API router
│   │   │       ├── webhooks.py       # GitHub webhook handler
│   │   │       └── health.py         # Health check
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── github.py             # GitHub API client
│   │       └── slack.py              # Slack client
│   │
│   ├── agents/                       # LangGraph
│   │   ├── __init__.py
│   │   ├── graph.py                  # Main workflow
│   │   ├── state.py                  # GraphState schema
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── context_extractor.py
│   │   │   ├── security_agent.py
│   │   │   ├── style_agent.py
│   │   │   ├── logic_agent.py
│   │   │   ├── aggregator.py
│   │   │   ├── github_publisher.py
│   │   │   └── slack_reporter.py
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── security.py
│   │       ├── style.py
│   │       └── logic.py
│   │
│   ├── core/                         # Shared utilities
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   └── llm.py                    # LLM client setup
│   │
│   └── workers/                      # Celery
│       ├── __init__.py
│       ├── celery_app.py
│       └── tasks.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── unit/
│       └── test_webhooks.py
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── Makefile
└── README.md
```

---

## 📦 Dependencies

**File:** `pyproject.toml`

```toml
[project]
name = "ai-code-reviewer"
version = "0.1.0"
requires-python = ">=3.13"

dependencies = [
    # FastAPI
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",

    # LangGraph + LLM
    "langgraph>=0.2.55",
    "langchain>=0.3.13",
    "langchain-openai>=0.2.14",
    "langchain-anthropic>=0.3.0",

    # GitHub
    "httpx>=0.28.0",
    "PyJWT>=2.10.0",
    "cryptography>=44.0.0",

    # Background Tasks
    "celery[redis]>=5.4.0",
    "redis>=5.2.0",

    # Slack
    "slack-sdk>=3.33.0",

    # Utilities
    "structlog>=24.4.0",
    "python-dotenv>=1.0.0",
    "tenacity>=9.0.0",
    "sentry-sdk[fastapi]>=2.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

---

## 🔧 Environment Variables

**File:** `.env.example`

```bash
# App
DEBUG=false
LOG_LEVEL=INFO

# GitHub App (get from https://github.com/settings/apps)
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# LLM (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Redis (Upstash)
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# Slack (optional)
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#pr-reviews

# Sentry (optional)
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

---

## 📝 Implementation Details

### 1. Config (`src/app/config.py`)

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # GitHub
    GITHUB_APP_ID: int
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str

    # LLM
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # Redis
    REDIS_URL: str

    # Slack
    SLACK_BOT_TOKEN: str | None = None
    SLACK_CHANNEL: str = "#pr-reviews"

    # Sentry
    SENTRY_DSN: str | None = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 2. Main App (`src/app/main.py`)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
import sentry_sdk

from .config import get_settings
from .api.v1.router import router as api_router
from ..core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    settings = get_settings()
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)
    yield
    # Shutdown


app = FastAPI(
    title="AI Code Reviewer",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 3. Webhook Handler (`src/app/api/v1/webhooks.py`)

```python
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
import hmac
import hashlib
import structlog

from ...config import get_settings
from ...services.github import GitHubService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = structlog.get_logger()


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    """Handle GitHub webhook events."""
    settings = get_settings()
    body = await request.body()

    # Validate signature
    if not _verify_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        log.warning("Invalid webhook signature", delivery=x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Handle pull_request events
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize", "reopened"):
            pr = payload["pull_request"]
            repo = payload["repository"]

            log.info(
                "PR event received",
                action=action,
                pr=pr["number"],
                repo=repo["full_name"],
            )

            # Queue review task
            from ...workers.tasks import review_pr
            review_pr.delay(
                owner=repo["owner"]["login"],
                repo=repo["name"],
                pr_number=pr["number"],
                installation_id=payload["installation"]["id"],
            )

            return {"status": "queued", "pr": pr["number"]}

    return {"status": "ignored", "event": x_github_event}


def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 4. GraphState (`src/agents/state.py`)

```python
from typing import TypedDict, Annotated, Literal
from pydantic import BaseModel, Field
import operator


class FileChange(BaseModel):
    """A file changed in the PR."""
    filename: str
    status: Literal["added", "modified", "removed", "renamed"]
    additions: int
    deletions: int
    patch: str  # Git diff
    language: str | None = None


class ReviewComment(BaseModel):
    """A review comment from an agent."""
    file: str
    line: int
    severity: Literal["critical", "warning", "info", "suggestion"]
    category: str  # security, style, logic
    message: str
    suggestion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    agent: str  # Which agent created this


class PRContext(BaseModel):
    """Context about the PR being reviewed."""
    owner: str
    repo: str
    pr_number: int
    title: str
    author: str
    installation_id: int


class GraphState(TypedDict):
    """State passed through the LangGraph workflow."""
    # Input
    context: PRContext

    # Extracted
    files: list[FileChange]

    # Agent outputs (merged via operator.add)
    comments: Annotated[list[ReviewComment], operator.add]

    # Aggregated
    final_comments: list[ReviewComment]
    summary: str

    # Output
    review_id: int | None
    errors: list[str]
```

### 5. Graph Workflow (`src/agents/graph.py`)

```python
from langgraph.graph import StateGraph, END
from .state import GraphState
from .nodes import (
    context_extractor,
    security_agent,
    style_agent,
    logic_agent,
    aggregator,
    github_publisher,
    slack_reporter,
)


def create_graph() -> StateGraph:
    """Create the review workflow graph."""
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)

    # Flow
    g.set_entry_point("extract")

    # Parallel agents (fan-out)
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")

    # Fan-in to aggregator
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")

    # Publish and notify
    g.add_edge("aggregate", "publish")
    g.add_edge("publish", "notify")
    g.add_edge("notify", END)

    return g.compile()


# Singleton
graph = create_graph()
```

### 6. Context Extractor (`src/agents/nodes/context_extractor.py`)

```python
from ..state import GraphState, FileChange
from ...app.services.github import GitHubService
import structlog

log = structlog.get_logger()

IGNORE_PATTERNS = (
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "*.min.js", "*.min.css", "*.map",
    "node_modules/*", "vendor/*", "dist/*", ".git/*",
)


async def run(state: GraphState) -> dict:
    """Fetch PR files and extract relevant changes."""
    ctx = state["context"]
    github = GitHubService(ctx.installation_id)

    raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    files = []
    for f in raw_files:
        if _should_ignore(f["filename"]):
            continue

        files.append(FileChange(
            filename=f["filename"],
            status=f["status"],
            additions=f["additions"],
            deletions=f["deletions"],
            patch=f.get("patch", ""),
            language=_detect_language(f["filename"]),
        ))

    log.info("Extracted files", count=len(files), pr=ctx.pr_number)
    return {"files": files}


def _should_ignore(filename: str) -> bool:
    import fnmatch
    return any(fnmatch.fnmatch(filename, p) for p in IGNORE_PATTERNS)


def _detect_language(filename: str) -> str | None:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".jsx": "javascript", ".go": "go",
        ".rs": "rust", ".java": "java", ".rb": "ruby", ".php": "php",
    }
    import os
    _, ext = os.path.splitext(filename)
    return ext_map.get(ext.lower())
```

### 7. Security Agent (`src/agents/nodes/security_agent.py`)

```python
from ..state import GraphState, ReviewComment
from ..prompts.security import PROMPT
from ...core.llm import get_llm
import json
import structlog

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Analyze code for security vulnerabilities."""
    llm = get_llm()
    comments = []

    for file in state["files"]:
        if not file.patch:
            continue

        prompt = PROMPT.format(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
        )

        response = await llm.ainvoke(prompt)
        findings = _parse_findings(response.content)

        for f in findings:
            if f.get("confidence", 0) < 0.7:
                continue
            comments.append(ReviewComment(
                file=file.filename,
                line=f["line"],
                severity=f["severity"],
                category="security",
                message=f["message"],
                suggestion=f.get("suggestion"),
                confidence=f["confidence"],
                agent="security",
            ))

    log.info("Security scan complete", findings=len(comments))
    return {"comments": comments}


def _parse_findings(content: str) -> list[dict]:
    """Extract JSON findings from LLM response."""
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            return data.get("findings", [])
    except json.JSONDecodeError:
        pass
    return []
```

### 8. Security Prompt (`src/agents/prompts/security.py`)

```python
PROMPT = """You are a security expert reviewing code changes.

## File: {filename}
## Language: {language}

## Diff (lines starting with + are additions):
```

{diff}

```

## Task:
Analyze the NEW code (+ lines) for security vulnerabilities.

## Focus on:
- SQL injection
- XSS (Cross-Site Scripting)
- Hardcoded secrets/credentials
- Insecure authentication
- Path traversal
- Command injection
- SSRF (Server-Side Request Forgery)

## Rules:
1. Only report issues with confidence > 0.7
2. Only analyze NEW code (+ lines)
3. Be specific about the exact line number
4. Return empty findings array if no issues

## Output (JSON only, no markdown):
{{"findings": [
  {{"line": 42, "severity": "critical", "message": "SQL injection via string concatenation", "suggestion": "Use parameterized queries", "confidence": 0.95}}
]}}
"""
```

### 9. Aggregator (`src/agents/nodes/aggregator.py`)

```python
from ..state import GraphState, ReviewComment
import structlog

log = structlog.get_logger()

MAX_PER_FILE = 10
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}


async def run(state: GraphState) -> dict:
    """Aggregate, deduplicate, and limit comments."""
    comments = state["comments"]

    # Deduplicate by (file, line, category)
    seen = set()
    unique = []
    for c in comments:
        key = (c.file, c.line, c.category)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Sort by severity, then confidence
    unique.sort(key=lambda c: (SEVERITY_ORDER.get(c.severity, 99), -c.confidence))

    # Limit per file
    by_file: dict[str, list[ReviewComment]] = {}
    for c in unique:
        by_file.setdefault(c.file, []).append(c)

    final = []
    for file_comments in by_file.values():
        final.extend(file_comments[:MAX_PER_FILE])

    # Generate summary
    critical = sum(1 for c in final if c.severity == "critical")
    warning = sum(1 for c in final if c.severity == "warning")

    summary = f"""## 🤖 AI Code Review

| Severity | Count |
|----------|-------|
| 🔴 Critical | {critical} |
| 🟡 Warning | {warning} |
| 🔵 Info/Suggestion | {len(final) - critical - warning} |

**Total: {len(final)} comments**
"""

    log.info("Aggregation complete", total=len(final), critical=critical)
    return {"final_comments": final, "summary": summary}
```

### 10. GitHub Publisher (`src/agents/nodes/github_publisher.py`)

```python
from ..state import GraphState
from ...app.services.github import GitHubService
import structlog

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Post review to GitHub."""
    ctx = state["context"]
    comments = state["final_comments"]
    summary = state["summary"]

    if not comments:
        log.info("No comments to publish", pr=ctx.pr_number)
        return {"review_id": None}

    github = GitHubService(ctx.installation_id)

    # Format comments for GitHub API
    review_comments = [
        {
            "path": c.file,
            "line": c.line,
            "body": _format_comment(c),
        }
        for c in comments
    ]

    # Determine review action
    has_critical = any(c.severity == "critical" for c in comments)
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
        log.error("Failed to publish review", error=str(e))
        return {"errors": [str(e)]}


def _format_comment(c) -> str:
    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵", "suggestion": "💡"}
    body = f"{emoji.get(c.severity, '•')} **{c.severity.upper()}** ({c.category})\n\n{c.message}"
    if c.suggestion:
        body += f"\n\n**Suggestion:** {c.suggestion}"
    return body
```

### 11. GitHub Service (`src/app/services/github.py`)

```python
import httpx
import jwt
import time
from ..config import get_settings
import structlog

log = structlog.get_logger()


class GitHubService:
    """GitHub API client using App installation tokens."""

    BASE_URL = "https://api.github.com"

    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self.settings = get_settings()
        self._token: str | None = None
        self._token_expires: float = 0

    async def _get_token(self) -> str:
        """Get or refresh installation access token."""
        if self._token and time.time() < self._token_expires:
            return self._token

        # Create JWT
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": self.settings.GITHUB_APP_ID,
        }
        jwt_token = jwt.encode(payload, self.settings.GITHUB_PRIVATE_KEY, algorithm="RS256")

        # Exchange for installation token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/app/installations/{self.installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["token"]
            self._token_expires = time.time() + 3500  # ~1 hour
            return self._token

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Fetch files changed in a PR."""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def create_review(
        self, owner: str, repo: str, pr_number: int,
        body: str, comments: list[dict], event: str = "COMMENT"
    ) -> int:
        """Create a PR review with comments."""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                json={"body": body, "event": event, "comments": comments},
            )
            resp.raise_for_status()
            return resp.json()["id"]
```

### 12. Celery Task (`src/workers/tasks.py`)

```python
from .celery_app import celery_app
from ..agents.graph import graph
from ..agents.state import PRContext
import structlog

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3)
def review_pr(self, owner: str, repo: str, pr_number: int, installation_id: int):
    """Run the review workflow for a PR."""
    import asyncio

    async def _run():
        log.info("Starting review", owner=owner, repo=repo, pr=pr_number)

        initial_state = {
            "context": PRContext(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                title="",  # Will be fetched if needed
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

        return result

    try:
        return asyncio.run(_run())
    except Exception as e:
        log.error("Review failed", error=str(e))
        raise self.retry(exc=e, countdown=60)
```

### 13. Celery App (`src/workers/celery_app.py`)

```python
from celery import Celery
from ..app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_reviewer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    task_time_limit=300,  # 5 min max
)
```

---

## 🚀 Deployment

### Railway / Render

1. **Create project** on Railway/Render
2. **Add Redis** addon (or use Upstash)
3. **Set environment variables** from `.env.example`
4. **Deploy commands:**

```bash
# Web
uvicorn src.app.main:app --host 0.0.0.0 --port $PORT

# Worker
celery -A src.workers.celery_app worker --loglevel=info
```

### GitHub App Setup

1. Go to https://github.com/settings/apps
2. Create new app with:
   - **Webhook URL:** `https://your-app.railway.app/api/v1/webhooks/github`
   - **Permissions:** Contents (Read), Pull Requests (Write), Issues (Write), Metadata (Read)
   - **Events:** Pull request, Issue comment
3. Generate Private Key và save vào env

---

## ✅ Checklist

### Week 1: Foundation

- [ ] `uv init` + pyproject.toml
- [ ] Project structure
- [ ] config.py + .env.example
- [ ] main.py + health endpoint
- [ ] GitHub App registration
- [ ] Webhook handler + signature validation
- [ ] Test với ngrok

### Week 2: Agents

- [ ] state.py (GraphState)
- [ ] graph.py (workflow)
- [ ] context_extractor.py
- [ ] security_agent.py + prompt
- [ ] style_agent.py + prompt
- [ ] logic_agent.py + prompt

### Week 3: Integration

- [ ] aggregator.py
- [ ] github_publisher.py
- [ ] github.py service
- [ ] slack_reporter.py (optional)
- [ ] E2E test

### Week 4: Deploy

- [ ] Celery setup
- [ ] structlog setup
- [ ] Sentry integration
- [ ] Deploy to Railway/Render
- [ ] Live test with real PR

---

## ➡️ Next: [Phase 2 - Enhanced Features](./PHASE_2_ENHANCED.md)
