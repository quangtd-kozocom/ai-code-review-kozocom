# 🚀 Phase 3: Scale + RAG + Analytics

**Thời gian:** 4 tuần (sau Phase 2)  
**Prerequisites:** Phase 1 & 2 hoàn thành và stable  
**Mục tiêu:** RAG context, scale infrastructure, analytics dashboard.

---

## 📋 Scope

### ✅ Implement

- Vector Database cho RAG (Qdrant Cloud hoặc Pinecone)
- Codebase embeddings cho better context
- Production-ready infrastructure (multiple workers)
- Multi-repository analytics
- Quality dashboard API
- Custom agent builder (basic)

### ❌ Out of scope

- Kubernetes (use managed platforms instead)
- Self-hosted vector DB
- Enterprise SSO

---

## 🛠️ Tech Stack Additions

```yaml
Vector Store:
  provider: Qdrant Cloud / Pinecone (managed)
  embeddings: OpenAI text-embedding-3-small

Infrastructure:
  platform: Railway / Render (scale horizontally)
  workers: Multiple Celery workers

Analytics:
  storage: PostgreSQL (existing)
  api: FastAPI endpoints
```

### New Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
phase3 = [
    "qdrant-client>=1.12.0",
    # Or "pinecone-client>=3.0.0",
    "langchain-community>=0.3.13", # For embeddings
]
```

Install:

```bash
uv pip install -e ".[phase2,phase3]"
```

---

## 🔧 Environment Variables (additions)

```bash
# Vector DB (choose one)
# Qdrant Cloud
QDRANT_URL=https://xxx.qdrant.io:6333
QDRANT_API_KEY=xxx

# Or Pinecone
# PINECONE_API_KEY=xxx
# PINECONE_ENVIRONMENT=us-east-1

# Embeddings model
EMBEDDING_MODEL=text-embedding-3-small
```

---

## 📁 Project Structure Additions

```
src/
├── app/
│   ├── services/
│   │   └── embeddings.py             # NEW: Embedding service
│   │
│   └── api/v1/
│       ├── analytics.py              # NEW: Analytics endpoints
│       └── agents.py                 # NEW: Custom agents CRUD
│
├── agents/
│   └── nodes/
│       └── context_enricher.py       # NEW: RAG context
│
└── scripts/
    └── index_codebase.py             # NEW: Indexing script
```

---

## 📝 Implementation Details

### 1. Embedding Service (`src/app/services/embeddings.py`)

```python
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import hashlib
from ..config import get_settings
import structlog

log = structlog.get_logger()


class EmbeddingService:
    """Service for code embeddings and similarity search."""

    COLLECTION = "codebase"
    DIMENSION = 1536  # text-embedding-3-small

    def __init__(self):
        settings = get_settings()
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )

    async def init_collection(self) -> None:
        """Create collection if not exists."""
        collections = await self.qdrant.get_collections()
        exists = any(c.name == self.COLLECTION for c in collections.collections)

        if not exists:
            await self.qdrant.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(
                    size=self.DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            log.info("Created vector collection", name=self.COLLECTION)

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        response = await self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    async def index_file(
        self, owner: str, repo: str, filepath: str, content: str
    ) -> int:
        """Index a file's chunks into vector store."""
        chunks = _chunk_code(content)
        points = []

        for i, chunk in enumerate(chunks):
            embedding = await self.embed(chunk)
            point_id = hashlib.md5(f"{owner}/{repo}/{filepath}:{i}".encode()).hexdigest()

            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "owner": owner,
                    "repo": repo,
                    "filepath": filepath,
                    "chunk_index": i,
                    "content": chunk,
                },
            ))

        if points:
            await self.qdrant.upsert(
                collection_name=self.COLLECTION,
                points=points,
            )

        return len(points)

    async def search(
        self, query: str, owner: str, repo: str, limit: int = 5
    ) -> list[dict]:
        """Find similar code chunks."""
        embedding = await self.embed(query)

        results = await self.qdrant.search(
            collection_name=self.COLLECTION,
            query_vector=embedding,
            query_filter=Filter(
                must=[
                    FieldCondition(key="owner", match=MatchValue(value=owner)),
                    FieldCondition(key="repo", match=MatchValue(value=repo)),
                ],
            ),
            limit=limit,
        )

        return [
            {
                "filepath": r.payload["filepath"],
                "content": r.payload["content"],
                "score": r.score,
            }
            for r in results
        ]

    async def delete_repo(self, owner: str, repo: str) -> None:
        """Delete all vectors for a repository."""
        await self.qdrant.delete(
            collection_name=self.COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(key="owner", match=MatchValue(value=owner)),
                    FieldCondition(key="repo", match=MatchValue(value=repo)),
                ],
            ),
        )


def _chunk_code(content: str, max_lines: int = 50) -> list[str]:
    """Split code into logical chunks."""
    lines = content.split("\n")
    chunks = []
    current = []

    for line in lines:
        current.append(line)

        # Split at function/class boundaries or max lines
        if len(current) >= max_lines or _is_boundary(line):
            if current:
                chunks.append("\n".join(current))
                current = []

    if current:
        chunks.append("\n".join(current))

    return chunks


def _is_boundary(line: str) -> bool:
    """Check if line is a function/class boundary."""
    stripped = line.strip()
    return (
        stripped.startswith("def ")
        or stripped.startswith("class ")
        or stripped.startswith("async def ")
        or stripped.startswith("function ")
        or stripped.startswith("export ")
    )
```

### 2. Codebase Indexer Script (`src/scripts/index_codebase.py`)

```python
"""Script to index a repository's codebase for RAG."""
import asyncio
import argparse
from ..app.services.github import GitHubService
from ..app.services.embeddings import EmbeddingService
import structlog

log = structlog.get_logger()

# File extensions to index
INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".rb", ".php",
}

# Paths to skip
SKIP_PATHS = {
    "node_modules", "vendor", "dist", "build",
    ".git", "__pycache__", ".next", ".venv",
}


async def index_repository(owner: str, repo: str, installation_id: int):
    """Index all code files in a repository."""
    github = GitHubService(installation_id)
    embeddings = EmbeddingService()

    await embeddings.init_collection()

    # Get repository tree
    tree = await github.get_tree(owner, repo, recursive=True)

    indexed = 0
    for item in tree:
        if item["type"] != "blob":
            continue

        path = item["path"]

        # Skip non-code files
        if not any(path.endswith(ext) for ext in INDEXABLE_EXTENSIONS):
            continue

        # Skip ignored paths
        if any(skip in path for skip in SKIP_PATHS):
            continue

        try:
            content = await github.get_file_content(owner, repo, path)
            chunks = await embeddings.index_file(owner, repo, path, content)
            indexed += chunks
            log.info("Indexed file", path=path, chunks=chunks)
        except Exception as e:
            log.warning("Failed to index file", path=path, error=str(e))

    log.info("Indexing complete", total_chunks=indexed)
    return indexed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--installation-id", type=int, required=True)
    args = parser.parse_args()

    asyncio.run(index_repository(args.owner, args.repo, args.installation_id))
```

### 3. Context Enricher Node (`src/agents/nodes/context_enricher.py`)

```python
from ..state import GraphState
from ...app.services.embeddings import EmbeddingService
import structlog

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Enrich context with similar code from codebase."""
    ctx = state["context"]
    embeddings = EmbeddingService()

    enriched = []

    for file in state["files"]:
        if not file.patch:
            continue

        # Search for similar code patterns
        similar = await embeddings.search(
            query=file.patch[:2000],  # Limit query size
            owner=ctx.owner,
            repo=ctx.repo,
            limit=3,
        )

        if similar:
            enriched.append({
                "file": file.filename,
                "similar": similar,
            })

    log.info("Context enriched", files_with_context=len(enriched))
    return {"enriched_context": enriched}
```

### 4. Enhanced Agent Prompt (with RAG)

Update `src/agents/prompts/security.py`:

```python
PROMPT = """You are a security expert reviewing code changes.

## File: {filename}
## Language: {language}

## Current Changes:
```

{diff}

````

## Similar Code in This Codebase:
{similar_code}

## Task:
1. Analyze NEW code (+ lines) for security vulnerabilities
2. Consider patterns from similar code when reviewing
3. If similar code has security issues, flag them here too
4. Check for consistency with existing security patterns

## Focus on:
- SQL injection, XSS, SSRF
- Hardcoded secrets
- Authentication/authorization issues
- Input validation

## Rules:
- Only report issues with confidence > 0.7
- Only analyze NEW code
- Return empty findings if no issues

## Output (JSON only):
{{"findings": [
  {{"line": 42, "severity": "critical", "message": "...", "suggestion": "...", "confidence": 0.9}}
]}}
"""


def format_similar_code(similar: list[dict]) -> str:
    """Format similar code for prompt."""
    if not similar:
        return "No similar code found."

    parts = []
    for s in similar[:3]:
        parts.append(f"### {s['filepath']} (similarity: {s['score']:.2f})\n```\n{s['content'][:500]}\n```")

    return "\n\n".join(parts)
````

### 5. Analytics Endpoints (`src/app/api/v1/analytics.py`)

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, UTC
from ...db.session import get_db
from ...db.models import Review, ReviewComment, Repository

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Get overview analytics for all repos."""
    since = datetime.now(UTC) - timedelta(days=days)

    # Total reviews
    total = await db.scalar(
        select(func.count(Review.id)).where(Review.created_at >= since)
    )

    # By status
    status_query = (
        select(Review.status, func.count(Review.id))
        .where(Review.created_at >= since)
        .group_by(Review.status)
    )
    status_result = await db.execute(status_query)
    by_status = dict(status_result.all())

    # By severity
    severity_query = (
        select(ReviewComment.severity, func.count(ReviewComment.id))
        .join(Review)
        .where(Review.created_at >= since)
        .group_by(ReviewComment.severity)
    )
    severity_result = await db.execute(severity_query)
    by_severity = dict(severity_result.all())

    # Avg processing time
    avg_time = await db.scalar(
        select(func.avg(Review.processing_time_ms))
        .where(Review.created_at >= since, Review.status == "completed")
    )

    return {
        "period_days": days,
        "total_reviews": total or 0,
        "by_status": by_status,
        "by_severity": by_severity,
        "avg_processing_time_ms": round(avg_time) if avg_time else None,
    }


@router.get("/repos/{owner}/{repo}")
async def get_repo_analytics(
    owner: str,
    repo: str,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Get analytics for a specific repository."""
    since = datetime.now(UTC) - timedelta(days=days)

    # Get repo
    repo_result = await db.execute(
        select(Repository).where(
            Repository.owner == owner,
            Repository.name == repo,
        )
    )
    repository = repo_result.scalar_one_or_none()

    if not repository:
        return {"error": "Repository not found"}

    # Reviews for this repo
    reviews = await db.execute(
        select(Review)
        .where(
            Review.repository_id == repository.id,
            Review.created_at >= since,
        )
        .order_by(Review.created_at.desc())
        .limit(100)
    )

    review_list = reviews.scalars().all()

    return {
        "repository": f"{owner}/{repo}",
        "period_days": days,
        "total_reviews": len(review_list),
        "total_comments": sum(r.comment_count or 0 for r in review_list),
        "total_critical": sum(r.critical_count or 0 for r in review_list),
        "avg_processing_time_ms": (
            sum(r.processing_time_ms or 0 for r in review_list) // len(review_list)
            if review_list else None
        ),
        "recent_reviews": [
            {
                "pr_number": r.pr_number,
                "status": r.status,
                "comments": r.comment_count,
                "critical": r.critical_count,
                "created_at": r.created_at.isoformat(),
            }
            for r in review_list[:10]
        ],
    }


@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=7, le=365),
):
    """Get daily trend data."""
    since = datetime.now(UTC) - timedelta(days=days)

    # Group by date
    query = (
        select(
            func.date(Review.created_at).label("date"),
            func.count(Review.id).label("reviews"),
            func.sum(Review.comment_count).label("comments"),
            func.sum(Review.critical_count).label("critical"),
        )
        .where(Review.created_at >= since)
        .group_by(func.date(Review.created_at))
        .order_by(func.date(Review.created_at))
    )

    result = await db.execute(query)

    return {
        "period_days": days,
        "data": [
            {
                "date": row.date.isoformat(),
                "reviews": row.reviews,
                "comments": row.comments or 0,
                "critical": row.critical or 0,
            }
            for row in result.all()
        ],
    }
```

### 6. Custom Agents Database Model

Add to `src/app/db/models.py`:

```python
class CustomAgent(Base):
    """User-defined custom review agent."""
    __tablename__ = "custom_agents"

    id = Column(Integer, primary_key=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    prompt_template = Column(Text, nullable=False)
    focus_areas = Column(JSON, default=[])  # ["performance", "security"]
    severity_threshold = Column(String(20), default="warning")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(UTC))

    repository = relationship("Repository")
```

### 7. Custom Agents CRUD (`src/app/api/v1/agents.py`)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from ...db.session import get_db
from ...db.models import CustomAgent, Repository

router = APIRouter(prefix="/agents", tags=["custom-agents"])


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    prompt_template: str
    focus_areas: list[str] = []
    severity_threshold: str = "warning"


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt_template: str | None = None
    focus_areas: list[str] | None = None
    severity_threshold: str | None = None
    enabled: bool | None = None


@router.get("/{owner}/{repo}")
async def list_agents(
    owner: str, repo: str,
    db: AsyncSession = Depends(get_db),
):
    """List custom agents for a repository."""
    repo_result = await db.execute(
        select(Repository).where(Repository.owner == owner, Repository.name == repo)
    )
    repository = repo_result.scalar_one_or_none()

    if not repository:
        raise HTTPException(404, "Repository not found")

    agents = await db.execute(
        select(CustomAgent).where(CustomAgent.repository_id == repository.id)
    )

    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "focus_areas": a.focus_areas,
            "enabled": a.enabled,
        }
        for a in agents.scalars().all()
    ]


@router.post("/{owner}/{repo}")
async def create_agent(
    owner: str, repo: str,
    agent: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a custom agent for a repository."""
    repo_result = await db.execute(
        select(Repository).where(Repository.owner == owner, Repository.name == repo)
    )
    repository = repo_result.scalar_one_or_none()

    if not repository:
        raise HTTPException(404, "Repository not found")

    new_agent = CustomAgent(
        repository_id=repository.id,
        name=agent.name,
        description=agent.description,
        prompt_template=agent.prompt_template,
        focus_areas=agent.focus_areas,
        severity_threshold=agent.severity_threshold,
    )

    db.add(new_agent)
    await db.commit()
    await db.refresh(new_agent)

    return {"id": new_agent.id, "name": new_agent.name}


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: int,
    updates: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a custom agent."""
    result = await db.execute(select(CustomAgent).where(CustomAgent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(404, "Agent not found")

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)

    await db.commit()
    return {"status": "updated"}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom agent."""
    result = await db.execute(select(CustomAgent).where(CustomAgent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(404, "Agent not found")

    await db.delete(agent)
    await db.commit()
    return {"status": "deleted"}
```

---

## 🚀 Scaling

### Multiple Workers

On Railway/Render, create separate services:

```bash
# Web service
uvicorn src.app.main:app --host 0.0.0.0 --port $PORT

# Worker service 1
celery -A src.workers.celery_app worker -Q default -c 2

# Worker service 2 (dedicated for heavy tasks)
celery -A src.workers.celery_app worker -Q reviews -c 4
```

### Queue Separation

```python
# In tasks.py
@celery_app.task(queue="reviews")
def review_pr(...):
    ...

@celery_app.task(queue="indexing")
def index_repository(...):
    ...
```

### Auto-scaling

Use platform auto-scaling based on:

- CPU usage > 70%
- Queue depth > 50 tasks
- Response time > 2s

---

## ✅ Checklist

### Week 9: Vector DB

- [ ] Setup Qdrant Cloud / Pinecone
- [ ] Create embeddings.py service
- [ ] Implement chunking logic
- [ ] Create indexing script
- [ ] Test search functionality

### Week 10: RAG Integration

- [ ] Create context_enricher node
- [ ] Update graph to include enricher
- [ ] Enhance prompts with similar code
- [ ] Test accuracy improvements
- [ ] Webhook to trigger re-indexing

### Week 11: Scaling

- [ ] Separate worker services
- [ ] Queue separation (reviews, indexing)
- [ ] Configure auto-scaling
- [ ] Load testing
- [ ] Monitoring alerts

### Week 12: Analytics

- [ ] Analytics API endpoints
- [ ] Custom agent model
- [ ] Custom agents CRUD API
- [ ] Dynamic agent loading in graph
- [ ] API documentation

---

## 📊 Success Metrics

| Metric              | Phase 2 | Phase 3 Target |
| ------------------- | ------- | -------------- |
| Review latency      | < 2 min | < 1 min        |
| False positive rate | < 20%   | < 10%          |
| RAG retrieval score | N/A     | > 0.8          |
| Concurrent reviews  | 5       | 20+            |

---

## 🎯 Post Phase 3

System capabilities:

- ✅ Production-ready with scaling
- ✅ Context-aware reviews (RAG)
- ✅ Analytics and insights
- ✅ Custom agents per repo

### Future Ideas (Phase 4+)

- AI-powered code suggestions (auto-fix)
- Jira/Linear integration
- Slack interactive app
- VS Code extension
- Self-hosted enterprise option
