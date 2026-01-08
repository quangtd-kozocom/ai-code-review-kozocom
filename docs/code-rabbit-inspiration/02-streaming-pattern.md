# 📡 Streaming & Incremental Processing Pattern

> Chi tiết về cách implement streaming và incremental processing để giải quyết bottleneck.

---

## 1. Vấn Đề Hiện Tại

### 1.1 Current Flow Analysis

```python
# Current implementation (base_agent.py)
async def run(state: GraphState) -> dict:
    files = state["files"]  # Lấy TẤT CẢ files

    # Process TẤT CẢ files song song
    results = await asyncio.gather(*[analyze_file(f) for f in files])

    # Đợi TẤT CẢ complete mới return
    comments = [c for file_comments in results for c in file_comments]
    return {"comments": comments}
```

```
Timeline hiện tại:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  PR Submitted ─┬─ File 1 ──────────────────────┐                        │
│    t=0         ├─ File 2 ────────────────────┐ │                        │
│                ├─ File 3 ──────────────┐     │ │                        │
│                │                        │     │ │                        │
│                │                        ▼     ▼ ▼                        │
│                │                     ALL COMPLETE ──▶ Aggregate ──▶ POST│
│                │                                                         │
│  t=30s ◄───────┴──────────────────────────────────────────────────────►  │
│                                                                          │
│  User waits 30 seconds to see ANY feedback                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Problems

| Problem                     | Impact                               |
| --------------------------- | ------------------------------------ |
| **Batch Processing**        | User đợi lâu nhất = file chậm nhất   |
| **No Progress Feedback**    | User không biết system đang làm gì   |
| **Single Point of Failure** | 1 file error → có thể block cả batch |
| **Resource Spike**          | Tất cả LLM calls cùng lúc            |

---

## 2. Giải Pháp: Streaming Pattern

### 2.1 Incremental Processing Flow

```
Timeline mong muốn:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  PR Submitted ─┬─ File 1 ────┐                                          │
│    t=0         │             │                                          │
│                │             ▼                                          │
│                │      POST Comment 1 (t=5s)                             │
│                │                                                         │
│                ├─ File 2 ────────────┐                                  │
│                │                      │                                  │
│                │                      ▼                                  │
│                │               POST Comment 2 (t=12s)                   │
│                │                                                         │
│                ├─ File 3 ──────────────────────┐                        │
│                │                                │                        │
│                │                                ▼                        │
│                │                         POST Comment 3 (t=25s)         │
│                │                                                         │
│                └─────────────────────────────────▶ POST Summary (t=26s)│
│                                                                          │
│  User sees first feedback at t=5s!                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Concepts

#### 2.2.1 Stream Processing

```python
# Thay vì batch:
results = await asyncio.gather(*tasks)  # Đợi TẤT CẢ

# Dùng streaming:
async for result in asyncio.as_completed(tasks):  # Yield từng cái
    await post_comment(result)  # Post ngay
```

#### 2.2.2 LangGraph Streaming Modes

```python
from langgraph.graph import StateGraph

# Stream modes available:
# - "updates": State changes after each step
# - "messages": Token-level LLM streaming
# - "custom": Custom events from nodes
# - "values": Full state after each step
# - "debug": Detailed execution traces

# Usage:
async for event in graph.astream(input, stream_mode=["updates", "custom"]):
    if "updates" in event:
        handle_state_update(event["updates"])
    if "custom" in event:
        handle_custom_event(event["custom"])
```

---

## 3. Implementation Patterns

### 3.1 Pattern 1: Per-File Streaming với `Send` API

LangGraph's `Send` API cho phép dynamic fan-out:

```python
from langgraph.graph import StateGraph, Send

def route_to_file_processors(state: GraphState) -> list[Send]:
    """Fan-out: Create a processing subgraph for each file."""
    files = state["files"]
    return [
        Send(
            "process_single_file",
            {
                "file": file,
                "context": state["context"],
                "repo_config": state["repo_config"],
            }
        )
        for file in files
    ]

async def process_single_file(state: dict) -> dict:
    """Process a single file and emit results as they complete."""
    file = state["file"]

    # Run all agents for this file
    security = await security_agent.analyze(file)
    style = await style_agent.analyze(file)
    logic = await logic_agent.analyze(file)

    # Aggregate for this file only
    comments = security + style + logic

    return {
        "file_result": FileResult(
            filename=file.filename,
            comments=comments,
        )
    }

def create_streaming_graph() -> StateGraph:
    g = StateGraph(StreamingGraphState)

    # Entry point
    g.add_node("extract", context_extractor.run)
    g.add_node("process_single_file", process_single_file)
    g.add_node("publish_file_comments", publish_file_comments)
    g.add_node("final_summary", generate_final_summary)

    # Flow
    g.set_entry_point("extract")

    # Dynamic fan-out to per-file processing
    g.add_conditional_edges(
        "extract",
        route_to_file_processors,  # Returns list of Send objects
    )

    # Each file result goes to publisher immediately
    g.add_edge("process_single_file", "publish_file_comments")

    # After all files done, generate summary
    # (LangGraph waits for all Send branches)
    g.add_edge("publish_file_comments", "final_summary")

    return g.compile()
```

### 3.2 Pattern 2: Custom Events cho Real-time Updates

```python
from langgraph.graph import StateGraph

async def process_file_with_events(state: GraphState) -> dict:
    """Process file and emit custom events for real-time tracking."""
    file = state["file"]
    context = state["context"]

    # Emit: Starting file processing
    yield CustomEvent(
        type="file_processing_started",
        data={"filename": file.filename}
    )

    # Security analysis
    yield CustomEvent(type="agent_started", data={"agent": "security"})
    security_results = await security_agent.analyze(file)
    yield CustomEvent(
        type="agent_completed",
        data={"agent": "security", "findings": len(security_results)}
    )

    # Style analysis
    yield CustomEvent(type="agent_started", data={"agent": "style"})
    style_results = await style_agent.analyze(file)
    yield CustomEvent(
        type="agent_completed",
        data={"agent": "style", "findings": len(style_results)}
    )

    # Emit: File complete, ready to post
    comments = security_results + style_results
    yield CustomEvent(
        type="file_ready_to_post",
        data={
            "filename": file.filename,
            "comments": [c.model_dump() for c in comments],
        }
    )

    return {"comments": comments}

# Consumer side:
async def run_with_streaming():
    async for event in graph.astream(input_state, stream_mode="custom"):
        if event["type"] == "file_ready_to_post":
            # Post comments immediately!
            await github_api.create_review_comments(
                pr_number=context.pr_number,
                comments=event["data"]["comments"],
            )
        elif event["type"] == "agent_started":
            # Update progress indicator
            await update_progress(f"Running {event['data']['agent']} analysis...")
```

### 3.3 Pattern 3: Progress Tracking với Acknowledge Comment

```python
async def run_review_with_progress(pr_context: PRContext, files: list[FileChange]):
    """Run review with real-time progress updates in a GitHub comment."""

    # 1. Create initial progress comment
    progress_comment = await github_api.create_issue_comment(
        owner=pr_context.owner,
        repo=pr_context.repo,
        issue_number=pr_context.pr_number,
        body=render_progress_template(
            status="starting",
            files=files,
            completed=[],
        )
    )

    completed_files = []
    all_comments = []

    # 2. Process files with streaming
    async def process_and_track(file: FileChange):
        result = await process_single_file(file)
        completed_files.append(file.filename)
        all_comments.extend(result.comments)

        # Update progress comment
        await github_api.update_issue_comment(
            comment_id=progress_comment.id,
            body=render_progress_template(
                status="processing",
                files=files,
                completed=completed_files,
            )
        )

        # Post file-specific comments immediately
        if result.comments:
            await post_review_comments(pr_context, result.comments)

        return result

    # 3. Run all files (concurrently but post as complete)
    await asyncio.gather(*[process_and_track(f) for f in files])

    # 4. Final summary
    await github_api.update_issue_comment(
        comment_id=progress_comment.id,
        body=render_final_summary(all_comments)
    )

def render_progress_template(status: str, files: list, completed: list) -> str:
    """Render a progress indicator as markdown."""
    lines = ["## 🤖 AI Code Review in Progress", ""]

    for file in files:
        if file.filename in completed:
            lines.append(f"✅ `{file.filename}` - Complete")
        else:
            lines.append(f"⏳ `{file.filename}` - Processing...")

    lines.extend([
        "",
        f"**Progress: {len(completed)}/{len(files)} files**",
        "",
        "_Comments will appear as each file completes._"
    ])

    return "\n".join(lines)
```

---

## 4. GitHub API Considerations

### 4.1 Comment Posting Strategies

#### Strategy 1: Individual Review Comments (Per Finding)

```python
# Post each comment separately
for comment in comments:
    await github_api.create_review_comment(
        owner=owner,
        repo=repo,
        pull_number=pr_number,
        body=comment.message,
        commit_id=head_sha,
        path=comment.file,
        line=comment.line,
    )
```

**Pros:**

- Real-time feedback per finding
- Easy to update/delete individual comments

**Cons:**

- Many API calls → rate limiting
- Can spam notifications

#### Strategy 2: Batched Review (Per File)

```python
# Collect all comments for a file, post as one review
file_comments = [c for c in comments if c.file == filename]

await github_api.create_review(
    owner=owner,
    repo=repo,
    pull_number=pr_number,
    commit_id=head_sha,
    event="COMMENT",
    comments=[
        {
            "path": c.file,
            "line": c.line,
            "body": c.message,
        }
        for c in file_comments
    ]
)
```

**Pros:**

- Fewer API calls
- Grouped notifications
- Better for UX

**Cons:**

- Still waits for file completion

#### Strategy 3: Hybrid (Recommended)

```python
async def post_incremental_review(pr_context, file_comments):
    """Post comments for one file as a single review, stream per file."""

    if not file_comments:
        return

    # Check for existing review from same file
    existing = await find_existing_file_review(pr_context, file_comments[0].file)

    if existing:
        # Update existing review
        await github_api.update_review_comments(existing.id, file_comments)
    else:
        # Create new review for this file
        await github_api.create_review(
            owner=pr_context.owner,
            repo=pr_context.repo,
            pull_number=pr_context.pr_number,
            event="COMMENT",
            body=f"## 🔍 Review for `{file_comments[0].file}`",
            comments=[c.to_github_format() for c in file_comments]
        )
```

### 4.2 Rate Limiting

```python
import asyncio
from contextlib import asynccontextmanager

class RateLimiter:
    """Simple rate limiter for GitHub API."""

    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_call + self.min_interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = asyncio.get_event_loop().time()
            yield

# Usage:
rate_limiter = RateLimiter(calls_per_second=5)  # 5 API calls/sec

async def post_with_rate_limit(comment):
    async with rate_limiter.acquire():
        await github_api.create_review_comment(comment)
```

### 4.3 Idempotency & Update Logic

```python
import hashlib

def generate_comment_id(file: str, line: int, category: str) -> str:
    """Generate unique ID for a comment to enable updates."""
    key = f"{file}:{line}:{category}"
    return hashlib.md5(key.encode()).hexdigest()[:8]

async def post_or_update_comment(pr_context, comment):
    """Post new comment or update existing one."""
    comment_id = generate_comment_id(comment.file, comment.line, comment.category)
    marker = f"<!-- review-comment-id:{comment_id} -->"

    body_with_marker = f"{marker}\n{comment.message}"

    # Search for existing comment with this marker
    existing_comments = await github_api.list_review_comments(
        owner=pr_context.owner,
        repo=pr_context.repo,
        pull_number=pr_context.pr_number,
    )

    for existing in existing_comments:
        if marker in existing.body:
            # Update existing
            if existing.body != body_with_marker:
                await github_api.update_review_comment(
                    comment_id=existing.id,
                    body=body_with_marker,
                )
            return

    # Create new
    await github_api.create_review_comment(
        body=body_with_marker,
        path=comment.file,
        line=comment.line,
    )
```

---

## 5. Complete Implementation Example

### 5.1 New State Definition

```python
# state.py additions
from typing import TypedDict, Annotated
import operator

class FileResult(BaseModel):
    """Result of processing a single file."""
    filename: str
    comments: list[ReviewComment]
    processing_time_ms: int
    status: Literal["success", "error", "skipped"]
    error: str | None = None

class StreamingGraphState(TypedDict):
    """State for streaming graph."""
    # Input
    context: PRContext
    repo_config: ReviewerConfig
    files: list[FileChange]

    # Per-file results (accumulated)
    file_results: Annotated[list[FileResult], operator.add]

    # Output
    acknowledge_comment_id: int | None
    summary: str
    errors: list[str]
```

### 5.2 New Graph Definition

```python
# streaming_graph.py
from langgraph.graph import StateGraph, Send, END
from langgraph.constants import Send

def create_streaming_review_graph() -> StateGraph:
    """Create a streaming review graph that posts results incrementally."""

    g = StateGraph(StreamingGraphState)

    # Nodes
    g.add_node("acknowledge", acknowledge_pr)
    g.add_node("extract", extract_files)
    g.add_node("process_file", process_single_file)
    g.add_node("post_file_result", post_file_result)
    g.add_node("generate_summary", generate_summary)

    # Entry
    g.set_entry_point("acknowledge")

    # Flow
    g.add_edge("acknowledge", "extract")

    # Dynamic fan-out: create a branch for each file
    g.add_conditional_edges(
        "extract",
        lambda state: [
            Send("process_file", {"file": f, **state})
            for f in state["files"]
        ],
    )

    # Each file result is posted immediately
    g.add_edge("process_file", "post_file_result")

    # After all files done, gather for summary
    # LangGraph automatically joins parallel branches
    g.add_edge("post_file_result", "generate_summary")
    g.add_edge("generate_summary", END)

    return g.compile()

# Nodes implementation
async def acknowledge_pr(state: StreamingGraphState) -> dict:
    """Post initial acknowledgment."""
    context = state["context"]

    comment = await github_api.create_issue_comment(
        owner=context.owner,
        repo=context.repo,
        issue_number=context.pr_number,
        body="🤖 **AI Code Review started**\n\nReviewing files...",
    )

    return {"acknowledge_comment_id": comment.id}

async def process_single_file(state: dict) -> dict:
    """Process one file through all agents."""
    import time
    start = time.time()

    file = state["file"]
    config = state["repo_config"]

    try:
        # Run agents for this file (can be parallel or sequential)
        security = await security_agent.analyze_file(file, config)
        style = await style_agent.analyze_file(file, config)
        logic = await logic_agent.analyze_file(file, config)

        comments = security + style + logic

        return {
            "file_results": [FileResult(
                filename=file.filename,
                comments=comments,
                processing_time_ms=int((time.time() - start) * 1000),
                status="success",
            )]
        }

    except Exception as e:
        return {
            "file_results": [FileResult(
                filename=file.filename,
                comments=[],
                processing_time_ms=int((time.time() - start) * 1000),
                status="error",
                error=str(e),
            )]
        }

async def post_file_result(state: dict) -> dict:
    """Post review comments for completed file immediately."""
    context = state["context"]
    file_results = state.get("file_results", [])

    for result in file_results:
        if result.comments:
            await github_api.create_review(
                owner=context.owner,
                repo=context.repo,
                pull_number=context.pr_number,
                body=f"## Review: `{result.filename}`",
                comments=[
                    {
                        "path": c.file,
                        "line": c.line,
                        "body": format_comment(c),
                    }
                    for c in result.comments
                ]
            )

    return {}

async def generate_summary(state: StreamingGraphState) -> dict:
    """Generate final summary after all files processed."""
    file_results = state["file_results"]
    context = state["context"]
    config = state["repo_config"]

    # Aggregate stats
    total_comments = sum(len(r.comments) for r in file_results)
    errors = [r for r in file_results if r.status == "error"]

    summary = render_summary(file_results, config.language)

    # Update the acknowledge comment with final summary
    await github_api.update_issue_comment(
        comment_id=state["acknowledge_comment_id"],
        body=summary,
    )

    return {
        "summary": summary,
        "errors": [e.error for e in errors if e.error],
    }
```

---

## 6. Testing & Validation

### 6.1 Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_streaming_posts_per_file():
    """Verify that comments are posted as each file completes."""
    mock_github = AsyncMock()

    with patch("src.agents.streaming_graph.github_api", mock_github):
        graph = create_streaming_review_graph()

        input_state = {
            "context": PRContext(owner="test", repo="test", pr_number=1, ...),
            "files": [
                FileChange(filename="a.py", ...),
                FileChange(filename="b.py", ...),
            ],
            "repo_config": ReviewerConfig(),
        }

        # Run graph
        result = await graph.ainvoke(input_state)

        # Verify: create_review called once per file
        assert mock_github.create_review.call_count == 2

        # Verify: Files were processed and posted independently
        calls = mock_github.create_review.call_args_list
        files_posted = {call.kwargs["body"] for call in calls}
        assert "a.py" in str(files_posted)
        assert "b.py" in str(files_posted)
```

### 6.2 Integration Tests

```python
@pytest.mark.integration
async def test_streaming_end_to_end():
    """Full integration test with real GitHub API (test repo)."""
    # Setup: Create test PR with known files
    # Run: Execute streaming graph
    # Verify:
    #   1. Comments appear incrementally (check timestamps)
    #   2. Summary is generated after all files
    #   3. No duplicate comments on re-run
```

---

## 7. Migration Path

### 7.1 Phased Rollout

| Phase | Change                                      | Risk   |
| ----- | ------------------------------------------- | ------ |
| 1     | Add streaming mode as option (feature flag) | Low    |
| 2     | Enable for small PRs only (≤3 files)        | Low    |
| 3     | Enable for all PRs, batch mode as fallback  | Medium |
| 4     | Remove batch mode                           | High   |

### 7.2 Feature Flag

```python
# config.py
class StreamingConfig(BaseModel):
    enabled: bool = False
    max_files_for_streaming: int = 10
    fallback_to_batch_on_error: bool = True

# Usage
if config.streaming.enabled and len(files) <= config.streaming.max_files_for_streaming:
    result = await streaming_graph.ainvoke(state)
else:
    result = await batch_graph.ainvoke(state)
```
