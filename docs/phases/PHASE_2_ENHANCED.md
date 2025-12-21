# 🔧 Phase 2: Enhanced Features + Persistence

**Thời gian:** 4 tuần (sau Phase 1)  
**Prerequisites:** Phase 1 hoàn thành và stable  
**Mục tiêu:** Database persistence, caching, và tính năng nâng cao.

---

## 📋 Scope

### ✅ Implement

- PostgreSQL (persist reviews, configs) - sử dụng **Neon** hoặc **Supabase**
- Redis caching (improve latency) - sử dụng **Upstash**
- YAML configuration per repository (`.ai-reviewer.yaml`)
- Incremental review (chỉ review commits mới)
- Interactive chat (@bot mentions)
- More agents: Performance, Documentation
- OpenTelemetry tracing

### ❌ Defer sang Phase 3

- Vector DB / RAG
- Kubernetes
- Multi-repo analytics
- Custom agent builder

---

## 🛠️ Tech Stack Additions

```yaml
Database:
  provider: Neon / Supabase (managed PostgreSQL)
  orm: SQLAlchemy 2.0 + asyncpg
  migrations: Alembic

Cache:
  provider: Upstash Redis (extend from Phase 1)

Observability:
  tracing: OpenTelemetry
  exporter: OTLP (Grafana Cloud / Honeycomb)
```

### New Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
phase2 = [
    "asyncpg>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "alembic>=1.14.0",
    "pyyaml>=6.0.2",
    "opentelemetry-api>=1.28.0",
    "opentelemetry-sdk>=1.28.0",
    "opentelemetry-instrumentation-fastapi>=0.49b0",
    "opentelemetry-exporter-otlp>=1.28.0",
]
```

Install:

```bash
uv pip install -e ".[phase2]"
```

---

## 📁 Project Structure Additions

```
src/
├── app/
│   ├── db/                           # NEW: Database
│   │   ├── __init__.py
│   │   ├── session.py                # Async session factory
│   │   └── models.py                 # SQLAlchemy models
│   │
│   └── services/
│       ├── cache.py                  # NEW: Redis cache
│       └── config_loader.py          # NEW: YAML config
│
├── agents/
│   └── nodes/
│       ├── config_loader.py          # NEW: Load repo config
│       ├── performance_agent.py      # NEW
│       └── docs_agent.py             # NEW
│
└── migrations/                       # NEW: Alembic
    ├── alembic.ini
    ├── env.py
    └── versions/
```

---

## 🔧 Environment Variables (additions)

```bash
# Database (Neon / Supabase)
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/dbname?sslmode=require

# OpenTelemetry (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.example.com:4317
OTEL_SERVICE_NAME=ai-code-reviewer
```

---

## 📝 Implementation Details

### 1. Database Session (`src/app/db/session.py`)

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### 2. Database Models (`src/app/db/models.py`)

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, UTC

Base = declarative_base()


class Repository(Base):
    """Repository configuration and metadata."""
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    installation_id = Column(Integer, nullable=False)
    config = Column(JSON, default={})  # Cached .ai-reviewer.yaml
    config_updated_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    reviews = relationship("Review", back_populates="repository")

    __table_args__ = (
        {"schema": None},  # Use default schema
    )


class Review(Base):
    """A review of a PR."""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    pr_number = Column(Integer, nullable=False)
    commit_sha = Column(String(40), nullable=False)
    status = Column(String(20), default="pending")  # pending, completed, failed
    github_review_id = Column(Integer)
    summary = Column(Text)
    comment_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    repository = relationship("Repository", back_populates="reviews")
    comments = relationship("ReviewComment", back_populates="review")


class ReviewComment(Base):
    """Individual review comment."""
    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    file = Column(String(500), nullable=False)
    line = Column(Integer, nullable=False)
    severity = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    suggestion = Column(Text)
    agent = Column(String(50))
    confidence = Column(Integer)  # 0-100
    dismissed = Column(Boolean, default=False)

    review = relationship("Review", back_populates="comments")
```

### 3. Alembic Setup

```bash
# Initialize
alembic init migrations

# Edit migrations/env.py to use async
# Edit alembic.ini to use DATABASE_URL

# Create migration
alembic revision --autogenerate -m "Initial models"

# Apply
alembic upgrade head
```

**migrations/env.py** (key parts):

```python
from src.app.db.models import Base
from src.app.config import get_settings
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata

def run_migrations_online():
    settings = get_settings()

    connectable = create_async_engine(settings.DATABASE_URL)

    async def do_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(do_migrations())
```

### 4. Cache Service (`src/app/services/cache.py`)

```python
import redis.asyncio as redis
import json
from typing import Any
from ..config import get_settings

_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


class Cache:
    """Simple Redis cache wrapper."""

    @staticmethod
    async def get(key: str) -> Any | None:
        client = await get_redis()
        data = await client.get(key)
        return json.loads(data) if data else None

    @staticmethod
    async def set(key: str, value: Any, ttl: int = 3600) -> None:
        client = await get_redis()
        await client.setex(key, ttl, json.dumps(value))

    @staticmethod
    async def delete(key: str) -> None:
        client = await get_redis()
        await client.delete(key)

    @staticmethod
    def repo_config_key(owner: str, repo: str) -> str:
        return f"config:{owner}/{repo}"

    @staticmethod
    def pr_files_key(owner: str, repo: str, pr: int) -> str:
        return f"pr:{owner}/{repo}:{pr}:files"
```

### 5. YAML Config Schema (`.ai-reviewer.yaml`)

```yaml
# Place in repository root

version: "1.0"

# Files/patterns to ignore (glob syntax)
ignore:
  - "*.lock"
  - "*.min.js"
  - "node_modules/**"
  - "dist/**"
  - "__pycache__/**"

# Agent configuration
agents:
  security:
    enabled: true
    severity_threshold: warning # Only report warning+

  style:
    enabled: true
    severity_threshold: info

  logic:
    enabled: true
    severity_threshold: warning

  performance:
    enabled: false # Disabled for this repo

  documentation:
    enabled: false

# Custom rules (added to agent prompts)
rules:
  security: |
    - No API keys in code
    - Use environment variables for secrets

  style: |
    - Max line length: 100
    - Use async/await over callbacks

# Limits
limits:
  max_comments_per_file: 10
  max_total_comments: 50
  min_confidence: 0.7

# Slack channel override (optional)
notifications:
  slack_channel: "#team-reviews"
```

### 6. Config Loader Node (`src/agents/nodes/config_loader.py`)

```python
import yaml
from ..state import GraphState
from ...app.services.github import GitHubService
from ...app.services.cache import Cache
import structlog

log = structlog.get_logger()

DEFAULT_CONFIG = {
    "version": "1.0",
    "ignore": ["*.lock", "node_modules/**", "dist/**"],
    "agents": {
        "security": {"enabled": True, "severity_threshold": "warning"},
        "style": {"enabled": True, "severity_threshold": "info"},
        "logic": {"enabled": True, "severity_threshold": "warning"},
        "performance": {"enabled": False},
        "documentation": {"enabled": False},
    },
    "limits": {
        "max_comments_per_file": 10,
        "max_total_comments": 50,
        "min_confidence": 0.7,
    },
}


async def run(state: GraphState) -> dict:
    """Load repository configuration."""
    ctx = state["context"]
    cache_key = Cache.repo_config_key(ctx.owner, ctx.repo)

    # Check cache first
    cached = await Cache.get(cache_key)
    if cached:
        log.debug("Config loaded from cache", repo=f"{ctx.owner}/{ctx.repo}")
        return {"config": cached}

    # Fetch from repo
    github = GitHubService(ctx.installation_id)
    try:
        content = await github.get_file_content(
            ctx.owner, ctx.repo, ".ai-reviewer.yaml"
        )
        config = yaml.safe_load(content)
        config = _merge_with_defaults(config)
    except Exception as e:
        log.info("No config found, using defaults", error=str(e))
        config = DEFAULT_CONFIG

    # Cache for 1 hour
    await Cache.set(cache_key, config, ttl=3600)

    return {"config": config}


def _merge_with_defaults(config: dict) -> dict:
    """Deep merge user config with defaults."""
    result = DEFAULT_CONFIG.copy()
    for key, value in config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = {**result[key], **value}
        else:
            result[key] = value
    return result
```

### 7. Incremental Review Logic

Add to `src/agents/nodes/context_extractor.py`:

```python
from ...app.db.session import AsyncSessionLocal
from ...app.db.models import Review
from sqlalchemy import select


async def _get_last_reviewed_sha(repo_id: int, pr_number: int) -> str | None:
    """Get last reviewed commit SHA for incremental review."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Review.commit_sha)
            .where(Review.repository_id == repo_id, Review.pr_number == pr_number)
            .order_by(Review.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row


async def run(state: GraphState) -> dict:
    """Fetch PR files, with incremental support."""
    ctx = state["context"]
    github = GitHubService(ctx.installation_id)

    # Get current commit
    pr_info = await github.get_pr(ctx.owner, ctx.repo, ctx.pr_number)
    current_sha = pr_info["head"]["sha"]

    # Check for incremental
    last_sha = await _get_last_reviewed_sha(ctx.repository_id, ctx.pr_number)

    if last_sha and last_sha != current_sha:
        # Get only files changed since last review
        raw_files = await github.get_compare_files(
            ctx.owner, ctx.repo, last_sha, current_sha
        )
        log.info("Incremental review", from_sha=last_sha[:7], to_sha=current_sha[:7])
    else:
        # Full review
        raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    # ... rest of processing
    return {"files": files, "commit_sha": current_sha}
```

### 8. Interactive Chat (`src/app/api/v1/webhooks.py` additions)

```python
@router.post("/github")
async def github_webhook(...):
    # ... existing pull_request handling ...

    # Handle issue_comment for @bot mentions
    if x_github_event == "issue_comment":
        comment = payload.get("comment", {})
        body = comment.get("body", "")

        if "@ai-reviewer" in body.lower() or "@ai-review" in body.lower():
            issue = payload["issue"]
            repo = payload["repository"]

            # Parse command
            command = _parse_bot_command(body)

            from ...workers.tasks import handle_bot_command
            handle_bot_command.delay(
                owner=repo["owner"]["login"],
                repo=repo["name"],
                issue_number=issue["number"],
                command=command,
                comment_id=comment["id"],
                installation_id=payload["installation"]["id"],
            )

            return {"status": "command_queued", "command": command}

    return {"status": "ignored"}


def _parse_bot_command(body: str) -> dict:
    """Parse bot command from comment."""
    body_lower = body.lower()

    if "review" in body_lower:
        return {"action": "review"}
    elif "explain" in body_lower:
        return {"action": "explain"}
    elif "dismiss" in body_lower:
        return {"action": "dismiss"}
    elif "help" in body_lower:
        return {"action": "help"}

    return {"action": "unknown"}
```

### 9. Bot Command Handler (`src/workers/tasks.py` additions)

```python
@celery_app.task
def handle_bot_command(
    owner: str, repo: str, issue_number: int,
    command: dict, comment_id: int, installation_id: int
):
    """Handle @bot commands in PR comments."""
    import asyncio

    async def _run():
        github = GitHubService(installation_id)
        action = command.get("action")

        if action == "review":
            # Trigger full re-review
            review_pr.delay(owner, repo, issue_number, installation_id)
            await github.add_reaction(owner, repo, comment_id, "+1")

        elif action == "help":
            help_text = """## 🤖 AI Reviewer Commands

- `@ai-reviewer review` - Re-run full review
- `@ai-reviewer explain` - Explain last findings
- `@ai-reviewer dismiss` - Dismiss low-priority findings
- `@ai-reviewer help` - Show this help
"""
            await github.create_comment(owner, repo, issue_number, help_text)

        elif action == "dismiss":
            # Mark info-level comments as dismissed
            await _dismiss_low_severity(owner, repo, issue_number)
            await github.add_reaction(owner, repo, comment_id, "+1")

        else:
            await github.add_reaction(owner, repo, comment_id, "confused")

    asyncio.run(_run())
```

### 10. OpenTelemetry Setup (`src/core/tracing.py`)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from ..app.config import get_settings


def setup_tracing(app):
    """Initialize OpenTelemetry tracing."""
    settings = get_settings()

    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return

    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME or "ai-code-reviewer",
    })

    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str):
    return trace.get_tracer(name)
```

Usage in nodes:

```python
from ...core.tracing import get_tracer

tracer = get_tracer(__name__)

async def run(state: GraphState) -> dict:
    with tracer.start_as_current_span("security_agent"):
        # ... agent logic
```

---

## ✅ Checklist

### Week 5: Database

- [ ] Add phase2 dependencies
- [ ] Create db/session.py
- [ ] Create db/models.py (Repository, Review, ReviewComment)
- [ ] Setup Alembic migrations
- [ ] Create initial migration
- [ ] Connect to Neon/Supabase
- [ ] Test CRUD operations

### Week 6: Config & Cache

- [ ] Create cache.py service
- [ ] Create config_loader.py node
- [ ] Define .ai-reviewer.yaml schema
- [ ] Update graph to include config_loader
- [ ] Update agents to respect config
- [ ] Test caching

### Week 7: Features

- [ ] Implement incremental review
- [ ] Add @bot mention detection
- [ ] Implement bot commands (review, help, dismiss)
- [ ] Update GitHub service (reactions, get_compare)
- [ ] Test interactive chat

### Week 8: Polish

- [ ] Add Performance agent
- [ ] Add Documentation agent
- [ ] Setup OpenTelemetry
- [ ] Update prompts with custom rules
- [ ] Integration tests
- [ ] Update documentation

---

## 📊 Success Metrics

| Metric              | Phase 1 | Phase 2 Target |
| ------------------- | ------- | -------------- |
| Review latency      | < 3 min | < 2 min        |
| False positive rate | < 30%   | < 20%          |
| Cache hit rate      | N/A     | > 60%          |

---

## ➡️ Next: [Phase 3 - Scale + RAG](./PHASE_3_SCALE.md)
