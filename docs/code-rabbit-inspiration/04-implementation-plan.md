# 📋 Implementation Plan: Streaming Review System

> Kế hoạch chi tiết để implement streaming review system dựa trên CodeRabbit architecture.

---

## 1. Executive Summary

### 1.1 Current State

| Component               | Status     | Description                                     |
| ----------------------- | ---------- | ----------------------------------------------- |
| Agent System            | ✅ Working | 3 agents (security, style, logic) chạy parallel |
| LangGraph               | ✅ Working | Fan-out/Fan-in pattern                          |
| GitHub Integration      | ✅ Working | Post review comments                            |
| **Streaming**           | ❌ Missing | Đợi tất cả files hoàn thành                     |
| **Per-file Processing** | ❌ Missing | Batch processing tất cả                         |
| **Dynamic Agents**      | ❌ Missing | Static agent list                               |

### 1.2 Target State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Streaming Review Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Webhook ──▶ Extract ──▶ ┌─────────────────────────────────────────────┐   │
│                          │ Per-File Processing Pipeline                 │   │
│                          │                                              │   │
│                          │  File 1 → Agents → Post ──▶ Comment 1       │   │
│                          │  File 2 → Agents → Post ──▶ Comment 2       │   │
│                          │  File N → Agents → Post ──▶ Comment N       │   │
│                          │                                              │   │
│                          └───────────────────────────┬─────────────────┘   │
│                                                       │                      │
│                                                       ▼                      │
│                                              Final Summary                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Key Deliverables

| Phase   | Deliverable                 | Duration |
| ------- | --------------------------- | -------- |
| Phase 1 | Agent Registry System       | 2-3 days |
| Phase 2 | Per-File Streaming Graph    | 3-4 days |
| Phase 3 | Incremental Comment Posting | 2-3 days |
| Phase 4 | Progress Tracking UI        | 1-2 days |
| Phase 5 | Testing & Migration         | 2-3 days |

**Total Estimated: 10-15 days**

---

## 2. Phase 1: Agent Registry System

### 2.1 Objective

Tách agents thành pluggable components để dễ thêm/bỏ agents mà không cần sửa graph.

### 2.2 Tasks

#### Task 1.1: Create Agent Base Classes

```python
# File: src/agents/base.py

# Create:
# - AgentCapability (Pydantic model)
# - AgentMetadata (Pydantic model)
# - BaseReviewAgent (ABC)
```

**Acceptance Criteria:**

- [ ] `AgentCapability` defines language/file pattern matching
- [ ] `AgentMetadata` defines agent name, version, priority
- [ ] `BaseReviewAgent` has `analyze()` and `should_run()` methods
- [ ] Unit tests for capability matching

#### Task 1.2: Create Agent Registry

```python
# File: src/agents/registry.py

# Create:
# - AgentRegistry singleton
# - register() method
# - get_agents_for_file() method
```

**Acceptance Criteria:**

- [ ] Agents can be registered via decorator
- [ ] Registry filters agents by file type
- [ ] Registry respects priority order
- [ ] Unit tests for registry operations

#### Task 1.3: Migrate Existing Agents

```python
# Migrate:
# - security_agent.py → BaseReviewAgent subclass
# - style_agent.py → BaseReviewAgent subclass
# - logic_agent.py → BaseReviewAgent subclass
```

**Acceptance Criteria:**

- [ ] All 3 agents implement BaseReviewAgent
- [ ] All agents register with registry on import
- [ ] Existing tests still pass
- [ ] No changes to current behavior

### 2.3 File Changes

| File                                 | Action | Description                           |
| ------------------------------------ | ------ | ------------------------------------- |
| `src/agents/base.py`                 | Create | Base classes                          |
| `src/agents/registry.py`             | Create | Registry singleton                    |
| `src/agents/nodes/security_agent.py` | Modify | Implement BaseReviewAgent             |
| `src/agents/nodes/style_agent.py`    | Modify | Implement BaseReviewAgent             |
| `src/agents/nodes/logic_agent.py`    | Modify | Implement BaseReviewAgent             |
| `src/agents/nodes/__init__.py`       | Modify | Import agents to trigger registration |
| `tests/agents/test_registry.py`      | Create | Registry tests                        |

### 2.4 Code Examples

```python
# src/agents/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Literal

class AgentCapability(BaseModel):
    """Describes what an agent can analyze."""
    languages: list[str] = ["*"]  # ["python", "javascript"] or ["*"]
    file_patterns: list[str] = []  # ["*_test.py", "*.spec.ts"]
    categories: list[str] = []  # ["security", "style"]

class AgentMetadata(BaseModel):
    """Agent metadata for registration."""
    name: str
    description: str
    version: str = "1.0.0"
    capability: AgentCapability = AgentCapability()
    priority: int = 100  # Lower = runs first
    enabled: bool = True

class BaseReviewAgent(ABC):
    """Abstract base for all review agents."""

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        pass

    @abstractmethod
    async def analyze(
        self,
        file: "FileChange",
        context: dict,
    ) -> list["ReviewComment"]:
        pass

    def should_run(self, file: "FileChange") -> bool:
        """Check if agent should run for file."""
        cap = self.metadata.capability

        # Language check
        if cap.languages and "*" not in cap.languages:
            if file.language and file.language not in cap.languages:
                return False

        # File pattern check
        if cap.file_patterns:
            from fnmatch import fnmatch
            if not any(fnmatch(file.filename, p) for p in cap.file_patterns):
                return False

        return True
```

```python
# src/agents/registry.py
from typing import Type
import structlog
from .base import BaseReviewAgent

log = structlog.get_logger()

class AgentRegistry:
    _instance = None

    def __init__(self):
        self._agents: dict[str, BaseReviewAgent] = {}

    @classmethod
    def get_instance(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, agent: BaseReviewAgent) -> None:
        name = agent.metadata.name
        self._agents[name] = agent
        log.info("agent.registered", name=name)

    def register_class(self, cls: Type[BaseReviewAgent]) -> Type[BaseReviewAgent]:
        """Decorator for agent classes."""
        self.register(cls())
        return cls

    def get_agents_for_file(
        self,
        file: "FileChange",
        enabled_only: bool = True,
    ) -> list[BaseReviewAgent]:
        agents = [
            a for a in self._agents.values()
            if (not enabled_only or a.metadata.enabled) and a.should_run(file)
        ]
        return sorted(agents, key=lambda a: a.metadata.priority)

registry = AgentRegistry.get_instance()
```

---

## 3. Phase 2: Per-File Streaming Graph

### 3.1 Objective

Refactor LangGraph để xử lý từng file riêng biệt, sử dụng `Send` API cho dynamic fan-out.

### 3.2 Tasks

#### Task 2.1: Create New State Schema

```python
# File: src/agents/streaming_state.py

# Add:
# - FileResult model
# - StreamingGraphState TypedDict
```

**Acceptance Criteria:**

- [ ] `FileResult` captures per-file processing results
- [ ] `StreamingGraphState` includes file_results accumulator
- [ ] Backward compatible with existing state

#### Task 2.2: Create Router Function

```python
# File: src/agents/router.py

# Create:
# - route_files_to_processors() function
# - Returns list[Send] for dynamic fan-out
```

**Acceptance Criteria:**

- [ ] Creates Send for each file
- [ ] Passes file-specific context
- [ ] Respects config for agent selection

#### Task 2.3: Create Per-File Processor

```python
# File: src/agents/nodes/file_processor.py

# Create:
# - process_single_file() node
# - Runs all applicable agents for one file
```

**Acceptance Criteria:**

- [ ] Uses registry to get applicable agents
- [ ] Runs agents sequentially or parallel (configurable)
- [ ] Returns FileResult
- [ ] Handles errors gracefully

#### Task 2.4: Create Streaming Graph

```python
# File: src/agents/streaming_graph.py

# Create:
# - create_streaming_graph() function
# - Uses Send API for fan-out
# - Includes per-file posting
```

**Acceptance Criteria:**

- [ ] Graph compiles successfully
- [ ] Files processed independently
- [ ] Results accumulated correctly
- [ ] Integration tests pass

### 3.3 File Changes

| File                                   | Action | Description           |
| -------------------------------------- | ------ | --------------------- |
| `src/agents/streaming_state.py`        | Create | New state definitions |
| `src/agents/router.py`                 | Create | File routing logic    |
| `src/agents/nodes/file_processor.py`   | Create | Per-file processing   |
| `src/agents/streaming_graph.py`        | Create | New streaming graph   |
| `tests/agents/test_streaming_graph.py` | Create | Integration tests     |

### 3.4 Code Examples

```python
# src/agents/streaming_state.py
from typing import TypedDict, Annotated, Literal
import operator
from pydantic import BaseModel

class FileResult(BaseModel):
    """Result of processing a single file."""
    filename: str
    comments: list["ReviewComment"]
    processing_time_ms: int
    status: Literal["success", "error", "skipped"]
    error: str | None = None

class StreamingGraphState(TypedDict):
    context: "PRContext"
    repo_config: "ReviewerConfig"
    files: list["FileChange"]

    # Accumulated per-file results
    file_results: Annotated[list[FileResult], operator.add]

    # Control
    acknowledge_comment_id: int | None
    summary: str
    errors: list[str]
```

```python
# src/agents/router.py
from langgraph.constants import Send
from .registry import registry

def route_files_to_processors(state: "StreamingGraphState") -> list[Send]:
    """Create a processing task for each file."""
    sends = []

    for file in state["files"]:
        if not file.patch:
            continue

        # Get applicable agents for this file
        agents = registry.get_agents_for_file(file)
        if not agents:
            continue

        sends.append(Send(
            "process_single_file",
            {
                "file": file,
                "agent_names": [a.metadata.name for a in agents],
                "context": state["context"],
                "repo_config": state["repo_config"],
            }
        ))

    return sends
```

```python
# src/agents/streaming_graph.py
from langgraph.graph import StateGraph, END

def create_streaming_graph() -> StateGraph:
    g = StateGraph(StreamingGraphState)

    # Nodes
    g.add_node("acknowledge", acknowledge_pr)
    g.add_node("extract", extract_files)
    g.add_node("process_single_file", process_single_file)
    g.add_node("post_file_result", post_file_result)
    g.add_node("finalize", generate_summary)

    # Entry
    g.set_entry_point("acknowledge")

    # Flow
    g.add_edge("acknowledge", "extract")

    # Dynamic fan-out to per-file processing
    g.add_conditional_edges("extract", route_files_to_processors)

    # Each file result gets posted
    g.add_edge("process_single_file", "post_file_result")

    # Join all branches
    g.add_edge("post_file_result", "finalize")
    g.add_edge("finalize", END)

    return g.compile()
```

---

## 4. Phase 3: Incremental Comment Posting

### 4.1 Objective

Post comments ngay khi mỗi file hoàn thành thay vì đợi tất cả.

### 4.2 Tasks

#### Task 3.1: Create Incremental Publisher

```python
# File: src/agents/nodes/incremental_publisher.py

# Create:
# - post_file_result() node
# - Posts review comments for single file
# - Handles idempotency (update vs create)
```

**Acceptance Criteria:**

- [ ] Posts comments immediately when file completes
- [ ] Uses review API (not individual comment API)
- [ ] Handles existing comments gracefully
- [ ] Rate limiting implemented

#### Task 3.2: Add Comment Tracking

```python
# File: src/agents/comment_tracker.py

# Create:
# - CommentTracker class
# - Tracks posted comments by file/line
# - Supports update vs create logic
```

**Acceptance Criteria:**

- [ ] Can detect existing comments
- [ ] Generates stable comment IDs
- [ ] Updates instead of duplicate posts

#### Task 3.3: Implement Rate Limiter

```python
# File: src/core/rate_limiter.py

# Create:
# - RateLimiter class
# - Async context manager
# - Configurable rate
```

**Acceptance Criteria:**

- [ ] Limits GitHub API calls
- [ ] Non-blocking async implementation
- [ ] Configurable calls per second

### 4.3 File Changes

| File                                         | Action | Description                |
| -------------------------------------------- | ------ | -------------------------- |
| `src/agents/nodes/incremental_publisher.py`  | Create | Per-file posting           |
| `src/agents/comment_tracker.py`              | Create | Comment tracking           |
| `src/core/rate_limiter.py`                   | Create | Rate limiting              |
| `src/app/github/client.py`                   | Modify | Add review posting methods |
| `tests/agents/test_incremental_publisher.py` | Create | Publisher tests            |

### 4.4 Code Examples

````python
# src/agents/nodes/incremental_publisher.py
import structlog
from ..streaming_state import StreamingGraphState

log = structlog.get_logger()

async def post_file_result(state: dict) -> dict:
    """Post review comments for a single completed file."""
    file_results = state.get("file_results", [])
    context = state["context"]

    for result in file_results:
        if not result.comments:
            log.info("publisher.no_comments", file=result.filename)
            continue

        try:
            await _post_review_for_file(context, result)
            log.info("publisher.posted", file=result.filename, count=len(result.comments))
        except Exception as e:
            log.error("publisher.error", file=result.filename, error=str(e))

    return {}

async def _post_review_for_file(context: "PRContext", result: "FileResult"):
    """Post a single review for one file."""
    from ...app.github.service import github_service

    comments = [
        {
            "path": c.file,
            "line": c.line,
            "body": _format_comment(c),
        }
        for c in result.comments
    ]

    await github_service.create_review(
        owner=context.owner,
        repo=context.repo,
        pull_number=context.pr_number,
        body=f"## 🔍 `{result.filename}`\n\n{len(comments)} findings",
        comments=comments,
        event="COMMENT",
    )

def _format_comment(comment: "ReviewComment") -> str:
    """Format comment for GitHub."""
    severity_emoji = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
        "suggestion": "💡",
    }

    lines = [
        f"{severity_emoji.get(comment.severity, '•')} **{comment.severity.upper()}** ({comment.category})",
        "",
        comment.message,
    ]

    if comment.suggestion:
        lines.extend(["", "**Suggestion:**", f"```", comment.suggestion, "```"])

    return "\n".join(lines)
````

```python
# src/core/rate_limiter.py
import asyncio
from contextlib import asynccontextmanager

class RateLimiter:
    """Simple async rate limiter."""

    def __init__(self, calls_per_second: float = 2.0):
        self._min_interval = 1.0 / calls_per_second
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self._last_call + self._min_interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_call = asyncio.get_event_loop().time()
            yield

# Usage:
rate_limiter = RateLimiter(calls_per_second=5)

async def post_with_limit(...):
    async with rate_limiter.acquire():
        await github_api.create_review(...)
```

---

## 5. Phase 4: Progress Tracking UI

### 5.1 Objective

Hiển thị progress cho developer trong GitHub comment real-time.

### 5.2 Tasks

#### Task 4.1: Create Progress Template

```python
# File: src/agents/templates/progress.py

# Create:
# - render_progress() function
# - Markdown template với checkboxes
# - Status indicators per file
```

**Acceptance Criteria:**

- [ ] Shows file list with status icons
- [ ] Updates as files complete
- [ ] Final summary when done
- [ ] Multi-language support (en/vi/ja)

#### Task 4.2: Implement Progress Updates

```python
# Modify: src/agents/nodes/acknowledger.py

# Add:
# - Update existing comment with progress
# - Track completed files
```

**Acceptance Criteria:**

- [ ] Initial comment posted on PR open
- [ ] Comment updates as files complete
- [ ] Final summary replaces progress

#### Task 4.3: Add Streaming Events

```python
# Modify: streaming_graph.py

# Add:
# - Custom events for progress tracking
# - Event handlers for UI updates
```

**Acceptance Criteria:**

- [ ] Events emitted at key stages
- [ ] Can be consumed by external systems
- [ ] Non-blocking

### 5.3 File Changes

| File                               | Action | Description        |
| ---------------------------------- | ------ | ------------------ |
| `src/agents/templates/progress.py` | Create | Progress templates |
| `src/agents/nodes/acknowledger.py` | Modify | Progress updates   |
| `src/agents/streaming_graph.py`    | Modify | Add events         |
| `tests/agents/test_progress.py`    | Create | Template tests     |

### 5.4 Code Examples

```python
# src/agents/templates/progress.py

def render_progress(
    files: list["FileChange"],
    completed: list[str],
    errors: list[str],
    language: str = "en",
) -> str:
    """Render progress indicator as markdown."""

    templates = {
        "en": {
            "title": "🤖 AI Code Review in Progress",
            "processing": "Processing...",
            "complete": "Complete",
            "error": "Error",
            "wait": "Waiting",
            "progress": "Progress",
            "note": "_Comments will appear as each file completes._",
        },
        "vi": {
            "title": "🤖 AI Code Review đang xử lý",
            "processing": "Đang xử lý...",
            "complete": "Hoàn thành",
            "error": "Lỗi",
            "wait": "Đang chờ",
            "progress": "Tiến độ",
            "note": "_Comments sẽ xuất hiện khi mỗi file hoàn thành._",
        },
    }

    t = templates.get(language, templates["en"])

    lines = [f"## {t['title']}", ""]

    for file in files:
        if file.filename in errors:
            icon = "❌"
            status = t["error"]
        elif file.filename in completed:
            icon = "✅"
            status = t["complete"]
        else:
            icon = "⏳"
            status = t["processing"]

        lines.append(f"{icon} `{file.filename}` - {status}")

    lines.extend([
        "",
        f"**{t['progress']}: {len(completed)}/{len(files)} files**",
        "",
        t["note"],
    ])

    return "\n".join(lines)


def render_final_summary(
    file_results: list["FileResult"],
    language: str = "en",
) -> str:
    """Render final summary replacing progress."""

    total_comments = sum(len(r.comments) for r in file_results)
    successful = [r for r in file_results if r.status == "success"]
    errors = [r for r in file_results if r.status == "error"]

    severity_counts = {}
    for r in file_results:
        for c in r.comments:
            severity_counts[c.severity] = severity_counts.get(c.severity, 0) + 1

    templates = {
        "en": f"""## 🤖 AI Code Review Complete

| Severity | Count |
|----------|-------|
| 🔴 Critical | {severity_counts.get('critical', 0)} |
| 🟡 Warning | {severity_counts.get('warning', 0)} |
| 🔵 Info | {severity_counts.get('info', 0)} |
| 💡 Suggestion | {severity_counts.get('suggestion', 0)} |

**Total: {total_comments} comments across {len(successful)} files**
{f"⚠️ {len(errors)} files had errors" if errors else ""}
""",
        # Add vi, ja templates...
    }

    return templates.get(language, templates["en"])
```

---

## 6. Phase 5: Testing & Migration

### 6.1 Objective

Đảm bảo hệ thống mới hoạt động đúng và migrate từ batch sang streaming.

### 6.2 Tasks

#### Task 5.1: Comprehensive Testing

- [ ] Unit tests cho tất cả components mới
- [ ] Integration tests cho streaming graph
- [ ] End-to-end tests với mock GitHub API
- [ ] Performance benchmarks

#### Task 5.2: Feature Flag Implementation

```python
# File: src/core/config.py

# Add:
# - streaming_enabled flag
# - max_files_for_streaming config
# - fallback_on_error flag
```

#### Task 5.3: Migration Strategy

| Stage | Criteria             | Rollback     |
| ----- | -------------------- | ------------ |
| Alpha | Internal repos only  | Immediate    |
| Beta  | Small PRs (≤5 files) | Flag disable |
| GA    | All PRs              | N/A          |

#### Task 5.4: Monitoring & Alerting

- [ ] Metrics for processing time per file
- [ ] Error rate tracking
- [ ] Alert on high failure rate
- [ ] Dashboard for review statistics

### 6.3 Test Cases

```python
# tests/integration/test_streaming_e2e.py

@pytest.mark.asyncio
async def test_streaming_posts_incrementally():
    """Verify comments are posted as files complete."""
    mock_github = AsyncMock()

    with patch("src.app.github.service.github_service", mock_github):
        graph = create_streaming_graph()

        state = {
            "context": PRContext(owner="test", repo="test", pr_number=1, ...),
            "files": [
                FileChange(filename="a.py", ...),
                FileChange(filename="b.py", ...),
                FileChange(filename="c.py", ...),
            ],
            "repo_config": ReviewerConfig(),
        }

        result = await graph.ainvoke(state)

        # Verify create_review called 3 times (once per file)
        assert mock_github.create_review.call_count == 3

@pytest.mark.asyncio
async def test_streaming_handles_file_error():
    """Verify one file error doesn't block others."""
    # Setup: mock to fail on specific file
    # Verify: other files still process and post

@pytest.mark.asyncio
async def test_streaming_respects_rate_limit():
    """Verify rate limiting prevents API abuse."""
    # Measure timing between API calls
    # Verify minimum delay
```

---

## 7. Configuration Schema

### 7.1 Updated .reviewer.yaml

```yaml
# .reviewer.yaml

# Streaming configuration
streaming:
  enabled: true
  max_files: 20 # Max files for streaming mode
  fallback_on_error: true # Use batch if streaming fails

  # Progress updates
  progress:
    enabled: true
    update_interval_seconds: 5

  # Rate limiting
  rate_limit:
    github_api_calls_per_second: 5
    llm_calls_per_second: 2

# Agent configuration
agents:
  security:
    enabled: true
    priority: 10

  style:
    enabled: true
    priority: 50

  logic:
    enabled: true
    priority: 30

  # New agent example
  test_quality:
    enabled: true
    priority: 40
    capability:
      file_patterns:
        - "*_test.py"
        - "test_*.py"
        - "*.test.ts"
        - "*.spec.ts"

# General settings
language: en # en, vi, ja
confidence_threshold: 0.7
max_comments_per_file: 10
```

### 7.2 Environment Variables

```bash
# .env additions

# Streaming
STREAMING_ENABLED=true
STREAMING_MAX_FILES=20

# Rate limiting
GITHUB_API_RATE_LIMIT=5
LLM_RATE_LIMIT=2

# Feature flags
FEATURE_PROGRESS_TRACKING=true
FEATURE_INCREMENTAL_POSTING=true
```

---

## 8. Rollout Timeline

```
Week 1: Phase 1 - Agent Registry
├── Day 1-2: Base classes & registry
└── Day 3: Migrate existing agents

Week 2: Phase 2 - Streaming Graph
├── Day 1-2: New state & router
├── Day 3: File processor
└── Day 4: Graph integration

Week 3: Phase 3 - Incremental Posting
├── Day 1-2: Publisher & tracking
└── Day 3: Rate limiting

Week 4: Phase 4-5 - Polish & Migration
├── Day 1: Progress UI
├── Day 2-3: Testing
├── Day 4: Feature flags
└── Day 5: Documentation & rollout
```

---

## 9. Success Metrics

| Metric                 | Current | Target | Measurement |
| ---------------------- | ------- | ------ | ----------- |
| Time to first comment  | 30-60s  | <10s   | P95 latency |
| Total review time      | 60-120s | 30-60s | P95 latency |
| Developer satisfaction | N/A     | >4/5   | Survey      |
| Error rate             | <5%     | <2%    | Monitoring  |
| API rate limit hits    | Unknown | 0      | Logs        |

---

## 10. Risks & Mitigations

| Risk                               | Probability | Impact | Mitigation                    |
| ---------------------------------- | ----------- | ------ | ----------------------------- |
| LangGraph Send API issues          | Medium      | High   | Fallback to batch mode        |
| GitHub API rate limits             | Low         | Medium | Rate limiter implementation   |
| Complex migration                  | Low         | High   | Feature flags, phased rollout |
| Performance regression             | Low         | Medium | Benchmarks before/after       |
| User confusion (multiple comments) | Medium      | Low    | Clear grouping, progress UI   |

---

## 11. Future Enhancements

After core implementation:

1. **Static Analysis Integration**: Add ESLint, Ruff, etc.
2. **Learning Loop**: Learn from resolved/dismissed comments
3. **IDE Extension**: Real-time review in VS Code
4. **Commit-level Review**: Review each commit separately
5. **Interactive Fixes**: One-click apply suggestions
