# 🚀 Streaming Code Review Architecture với LangGraph

> **Tác giả**: AI Research  
> **Ngày**: 2026-01-08  
> **Status**: Draft - Pending Review  
> **Focus**: Tận dụng sức mạnh của LangGraph cho MVP

---

## 📋 Mục lục

1. [Tại sao Streaming?](#1-tại-sao-streaming)
2. [LangGraph Streaming Capabilities](#2-langgraph-streaming-capabilities)
3. [Kiến trúc đề xuất](#3-kiến-trúc-đề-xuất)
4. [Implementation Chi tiết](#4-implementation-chi-tiết)
5. [Trade-offs và Giải pháp](#5-trade-offs-và-giải-pháp)
6. [MVP Implementation Plan](#6-mvp-implementation-plan)

---

## 1. Tại sao Streaming?

### 1.1 Vấn đề với Batch Mode

```
User mở PR → Đợi 30-45s → Thấy TẤT CẢ comments cùng lúc
                  😴
              (không biết đang làm gì)
```

### 1.2 Lợi ích của Streaming

```
User mở PR → Thấy "Reviewing file1.py..." (3s)
           → Thấy comment cho file1 (5s)
           → Thấy "Reviewing file2.py..." (8s)
           → Thấy comment cho file2 (10s)
           → ...
           → Summary cuối cùng (20s)
```

**UX tốt hơn nhiều!**

---

## 2. LangGraph Streaming Capabilities

### 2.1 Các Streaming Modes

| Mode | Mô tả | Use Case |
|------|-------|----------|
| `values` | Stream full state sau mỗi node | Debug |
| `updates` | Stream state delta sau mỗi node | Track changes |
| `messages` | Stream LLM tokens | Real-time text |
| `custom` | Stream arbitrary data | **Progress updates!** |
| `debug` | Maximum info | Development |

### 2.2 Key Tool: `get_stream_writer()`

**Đây là sức mạnh thực sự của LangGraph!**

```python
from langgraph.config import get_stream_writer

async def review_node(state: GraphState):
    writer = get_stream_writer()
    
    for file in state["files"]:
        # Emit progress NGAY LẬP TỨC
        writer({"event": "reviewing", "file": file.filename})
        
        # Do review
        result = await llm.ainvoke(prompt)
        
        # Emit result NGAY LẬP TỨC
        writer({
            "event": "file_complete",
            "file": file.filename,
            "findings": result.findings
        })
    
    return {"comments": all_comments}
```

**Consumer nhận được events real-time:**
```python
async for chunk in graph.astream(inputs, stream_mode="custom"):
    if chunk["event"] == "reviewing":
        print(f"🔍 Đang review: {chunk['file']}")
    elif chunk["event"] == "file_complete":
        print(f"✅ Xong: {chunk['file']} - {len(chunk['findings'])} findings")
        # CÓ THỂ PUBLISH LÊN GITHUB NGAY TẠI ĐÂY!
```

### 2.3 Side Effects trong Streaming

```python
async def review_and_publish_node(state: GraphState):
    writer = get_stream_writer()
    github = GitHubClient(state["context"])
    
    for file in state["files"]:
        # 1. Review
        findings = await review_file(file)
        
        # 2. Publish NGAY (side effect)
        if findings:
            await github.create_review_comment(findings)
        
        # 3. Emit progress
        writer({
            "event": "published",
            "file": file.filename,
            "count": len(findings)
        })
    
    return {"comments": all_comments}
```

---

## 3. Kiến trúc đề xuất

### 3.1 Option 1: Single Node Streaming (Simple MVP)

**Ý tưởng**: 1 node xử lý và stream tất cả.

```
┌─────────────────────────────────────────────────────────────┐
│                      LangGraph                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  START                                                      │
│    │                                                        │
│    ▼                                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            streaming_review_node                       │  │
│  │                                                        │  │
│  │  for file in files:                                   │  │
│  │    ├─► writer({"event": "start", "file": ...})       │──┼──► Stream event
│  │    ├─► findings = await llm.invoke(...)              │  │
│  │    ├─► await github.publish(findings)                │──┼──► GitHub API
│  │    └─► writer({"event": "done", "file": ...})        │──┼──► Stream event
│  │                                                        │  │
│  └───────────────────────────────────────────────────────┘  │
│    │                                                        │
│    ▼                                                        │
│  END                                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Ưu điểm**:
- ✅ Cực kỳ đơn giản
- ✅ Stream real-time từng file
- ✅ Publish ngay sau mỗi file
- ✅ Code dễ hiểu, dễ debug

**Nhược điểm**:
- ⚠️ Sequential processing (không parallel)
- ⚠️ Không tận dụng được graph structure

---

### 3.2 Option 2: Parallel Review + Sequential Publish (Balanced)

**Ý tưởng**: Review parallel, nhưng publish sequential để kiểm soát.

```
┌─────────────────────────────────────────────────────────────┐
│                      LangGraph                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  START                                                      │
│    │                                                        │
│    ▼                                                        │
│  ┌─────────────┐                                            │
│  │  extract    │                                            │
│  └──────┬──────┘                                            │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         parallel_review_node                            ││
│  │  ┌─────────────────────────────────────────────────┐    ││
│  │  │  asyncio.gather(*[review(f) for f in files])    │    ││
│  │  │       │           │           │                 │    ││
│  │  │       ▼           ▼           ▼                 │    ││
│  │  │   file1.py    file2.py    file3.py              │    ││
│  │  │       │           │           │                 │    ││
│  │  │       └───────────┴───────────┘                 │    ││
│  │  │                   │                             │    ││
│  │  │          Collected Results                      │    ││
│  │  └───────────────────┬─────────────────────────────┘    ││
│  └──────────────────────┼──────────────────────────────────┘│
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         streaming_publish_node                          ││
│  │                                                         ││
│  │  for result in sorted_results:                         ││
│  │    ├─► writer({"publishing": result.file})    ──────────┼┼─► Stream
│  │    ├─► await github.publish(result)           ──────────┼┼─► GitHub
│  │    └─► writer({"published": result.file})     ──────────┼┼─► Stream
│  │                                                         ││
│  └─────────────────────────────────────────────────────────┘│
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────┐                                            │
│  │   summary   │                                            │
│  └─────────────┘                                            │
│         │                                                   │
│         ▼                                                   │
│       END                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Ưu điểm**:
- ✅ Review parallel = nhanh hơn
- ✅ Publish sequential = kiểm soát được order
- ✅ Có thể dedup trước khi publish
- ✅ Stream progress cho user

**Nhược điểm**:
- ⚠️ User phải đợi review xong hết mới thấy publish
- ⚠️ Phức tạp hơn Option 1

---

### 3.3 Option 3: Dynamic Parallel với Send() API (Advanced)

**Ý tưởng**: Mỗi file là 1 "task" độc lập, xử lý và publish ngay.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           LangGraph                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  START                                                              │
│    │                                                                │
│    ▼                                                                │
│  ┌─────────────┐                                                    │
│  │   extract   │                                                    │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────┐                                               │
│  │   fan_out_files  │ ── Send("review_file", {file: f1}) ──┐       │
│  │                  │ ── Send("review_file", {file: f2}) ──┼──┐    │
│  │                  │ ── Send("review_file", {file: f3}) ──┼──┼──┐ │
│  └──────────────────┘                                      │  │  │ │
│                                                            │  │  │ │
│         ┌──────────────────────────────────────────────────┘  │  │ │
│         │         ┌───────────────────────────────────────────┘  │ │
│         │         │         ┌────────────────────────────────────┘ │
│         ▼         ▼         ▼                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                               │
│  │ review  │ │ review  │ │ review  │  ← Chạy PARALLEL              │
│  │ file_1  │ │ file_2  │ │ file_3  │                               │
│  │         │ │         │ │         │                               │
│  │ writer()│ │ writer()│ │ writer()│  ← Mỗi task stream riêng      │
│  │ github()│ │ github()│ │ github()│  ← Mỗi task publish riêng     │
│  └────┬────┘ └────┬────┘ └────┬────┘                               │
│       │           │           │                                    │
│       └───────────┴───────────┘                                    │
│                   │                                                │
│                   ▼                                                │
│            ┌─────────────┐                                         │
│            │  aggregate  │  ← Fan-in: gộp results                  │
│            └──────┬──────┘                                         │
│                   │                                                │
│                   ▼                                                │
│            ┌─────────────┐                                         │
│            │   summary   │  ← Post summary comment                 │
│            └──────┬──────┘                                         │
│                   │                                                │
│                   ▼                                                │
│                 END                                                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation với Send() API**:
```python
from langgraph.types import Send

def fan_out_files(state: GraphState):
    """Tạo parallel tasks cho mỗi file"""
    return [
        Send("review_and_publish_file", {
            "file": file,
            "context": state["context"],
            "config": state["repo_config"]
        })
        for file in state["files"]
        if file.patch
    ]

async def review_and_publish_file(state: dict):
    """Review 1 file và publish ngay"""
    writer = get_stream_writer()
    file = state["file"]
    
    # 1. Emit start
    writer({"event": "file_start", "file": file.filename})
    
    # 2. Review
    findings = await unified_review(file)
    
    # 3. Publish NGAY
    if findings:
        github = GitHubClient(state["context"])
        await github.create_inline_comments(findings)
    
    # 4. Emit done
    writer({
        "event": "file_done",
        "file": file.filename,
        "findings_count": len(findings)
    })
    
    return {"file_result": {"file": file.filename, "findings": findings}}
```

**Ưu điểm**:
- ✅ TRUE parallel: mỗi file xử lý độc lập
- ✅ Publish NGAY sau khi review xong mỗi file
- ✅ User thấy results sớm nhất có thể
- ✅ Tận dụng ĐÚNG sức mạnh của LangGraph

**Nhược điểm**:
- ⚠️ Không có cross-file dedup
- ⚠️ GitHub notifications nhiều hơn
- ⚠️ Phức tạp nhất

---

## 4. Implementation Chi tiết

### 4.1 🏆 Recommended: Option 1 + Improvement (Smart Sequential)

**Lý do chọn cho MVP**:
- Simple code, easy to debug
- Vẫn stream real-time
- Có thể dedup on-the-fly
- Dễ migrate lên Option 3 sau

```python
# src/agents/nodes/streaming_reviewer.py

from langgraph.config import get_stream_writer
from ..prompts.unified import UNIFIED_REVIEW_PROMPT
from ..models import ReviewComment, UnifiedReviewOutput

async def run(state: GraphState) -> dict:
    """
    Streaming unified reviewer.
    Review từng file và stream progress real-time.
    """
    writer = get_stream_writer()
    github = GitHubClient(state["context"])
    config = state["repo_config"]
    
    files = [f for f in state["files"] if f.patch]
    all_comments: list[ReviewComment] = []
    seen_issues: set[tuple[str, int, str]] = set()  # For dedup
    
    total = len(files)
    
    # Emit: Review started
    writer({
        "event": "review_started",
        "total_files": total,
        "pr_number": state["context"].pr_number
    })
    
    for idx, file in enumerate(files):
        file_progress = f"{idx + 1}/{total}"
        
        # Emit: File review starting
        writer({
            "event": "file_reviewing",
            "file": file.filename,
            "progress": file_progress
        })
        
        # Review file
        try:
            findings = await _review_single_file(file, config)
        except Exception as e:
            writer({
                "event": "file_error",
                "file": file.filename,
                "error": str(e)
            })
            continue
        
        # Dedup on-the-fly
        new_findings = []
        for f in findings:
            key = (f.file, f.line, f.category)
            if key not in seen_issues:
                seen_issues.add(key)
                new_findings.append(f)
        
        # Convert to comments
        comments = _findings_to_comments(new_findings, file)
        
        # Emit: File review complete
        writer({
            "event": "file_reviewed",
            "file": file.filename,
            "progress": file_progress,
            "findings_count": len(comments),
            "findings_preview": [
                {"line": c.line, "severity": c.severity, "title": c.message[:50]}
                for c in comments[:3]  # Preview first 3
            ]
        })
        
        # Publish to GitHub NGAY
        if comments and config.publish_inline:
            try:
                await github.create_review_comments(
                    pr_number=state["context"].pr_number,
                    comments=comments
                )
                writer({
                    "event": "file_published",
                    "file": file.filename,
                    "published_count": len(comments)
                })
            except Exception as e:
                writer({
                    "event": "publish_error",
                    "file": file.filename,
                    "error": str(e)
                })
        
        all_comments.extend(comments)
    
    # Emit: Review complete
    writer({
        "event": "review_complete",
        "total_findings": len(all_comments),
        "by_severity": _count_by_severity(all_comments)
    })
    
    return {"comments": all_comments}


async def _review_single_file(
    file: EnhancedFileChange,
    config: ReviewerConfig
) -> list[Finding]:
    """Review single file with unified prompt"""
    
    prompt = _build_unified_prompt(file, config)
    
    result = await llm.with_structured_output(
        UnifiedReviewOutput
    ).ainvoke(prompt)
    
    return result.findings
```

### 4.2 Graph Definition

```python
# src/agents/graph.py

from langgraph.graph import StateGraph, START, END
from .state import GraphState
from .nodes import (
    acknowledger,
    context_extractor,
    streaming_reviewer,  # NEW
    summary_publisher,
    slack_reporter,
)

def build_streaming_graph() -> StateGraph:
    """Build streaming review graph"""
    
    g = StateGraph(GraphState)
    
    # Nodes
    g.add_node("acknowledge", acknowledger.run)
    g.add_node("extract", context_extractor.run)
    g.add_node("review", streaming_reviewer.run)  # Streaming node
    g.add_node("summary", summary_publisher.run)  # Only posts summary
    g.add_node("notify", slack_reporter.run)
    
    # Linear flow (streaming happens inside review node)
    g.add_edge(START, "acknowledge")
    g.add_edge("acknowledge", "extract")
    g.add_edge("extract", "review")
    g.add_edge("review", "summary")
    g.add_edge("summary", "notify")
    g.add_edge("notify", END)
    
    return g.compile()
```

### 4.3 Consumer (API endpoint)

```python
# src/app/api/webhook.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

router = APIRouter()

@router.post("/webhook/github")
async def github_webhook(payload: dict):
    """Handle GitHub webhook với streaming response"""
    
    pr_context = parse_webhook(payload)
    
    async def event_generator():
        async for chunk in graph.astream(
            {"context": pr_context},
            stream_mode="custom"
        ):
            # Convert to Server-Sent Events format
            yield f"data: {json.dumps(chunk)}\n\n"
        
        yield "data: {\"event\": \"done\"}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### 4.4 Frontend Integration (Optional)

```typescript
// Nếu có UI để show progress
const eventSource = new EventSource('/api/review/stream?pr=123');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.event) {
    case 'file_reviewing':
      showProgress(`Reviewing ${data.file}... (${data.progress})`);
      break;
    case 'file_reviewed':
      addFileResult(data.file, data.findings_preview);
      break;
    case 'file_published':
      markAsPublished(data.file);
      break;
    case 'review_complete':
      showSummary(data.total_findings, data.by_severity);
      break;
  }
};
```

---

## 5. Trade-offs và Giải pháp

### 5.1 GitHub Notifications

**Vấn đề**: Mỗi `create_review_comment` = 1 notification

**Giải pháp**: Dùng **Pending Review** pattern

```python
async def streaming_with_pending_review(state: GraphState):
    writer = get_stream_writer()
    github = GitHubClient(state["context"])
    
    # 1. Tạo pending review (không notify)
    review_id = await github.create_pending_review(
        pr_number=state["context"].pr_number
    )
    
    for file in state["files"]:
        findings = await review_file(file)
        
        # 2. Add comments to pending review (không notify)
        await github.add_review_comments(
            review_id=review_id,
            comments=findings
        )
        
        # 3. Stream progress
        writer({"event": "file_done", "file": file.filename})
    
    # 4. Submit review (1 notification cho TẤT CẢ)
    await github.submit_review(
        review_id=review_id,
        body="AI Code Review Complete",
        event="COMMENT"
    )
    
    writer({"event": "review_submitted"})
```

**Kết quả**: User thấy progress real-time, nhưng chỉ nhận 1 notification!

### 5.2 Cross-file Deduplication

**Vấn đề**: Stream từng file → khó dedup cross-file

**Giải pháp**: On-the-fly dedup với seen set

```python
seen_issues: set[tuple] = set()

for file in files:
    findings = await review(file)
    
    # Dedup against already seen
    new_findings = [
        f for f in findings
        if (f.file, f.line, f.category) not in seen_issues
    ]
    
    # Update seen set
    for f in new_findings:
        seen_issues.add((f.file, f.line, f.category))
    
    # Only publish new findings
    await publish(new_findings)
```

### 5.3 Error Recovery

**Vấn đề**: Nếu fail giữa chừng → partial state

**Giải pháp**: Checkpointing

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
graph = builder.compile(checkpointer=checkpointer)

# Mỗi PR có thread_id riêng
config = {"configurable": {"thread_id": f"pr-{pr_number}"}}

# Nếu fail, có thể resume
async for chunk in graph.astream(inputs, config, stream_mode="custom"):
    # Process...
    pass

# Resume từ checkpoint nếu cần
state = graph.get_state(config)
if state.next:  # Còn nodes chưa chạy
    async for chunk in graph.astream(None, config, stream_mode="custom"):
        pass
```

---

## 6. MVP Implementation Plan

### 6.1 Phase 1: Basic Streaming (3 days)

**Deliverables**:
- [ ] `streaming_reviewer.py` với `get_stream_writer()`
- [ ] Update `graph.py`
- [ ] Stream events trong single node

**Code changes**:
```
src/agents/
├── nodes/
│   ├── streaming_reviewer.py  # NEW
│   └── summary_publisher.py   # NEW (split from aggregator)
├── graph.py                   # UPDATE
└── prompts/
    └── unified.py             # NEW
```

### 6.2 Phase 2: GitHub Integration (2 days)

**Deliverables**:
- [ ] Pending Review pattern
- [ ] Inline comments publishing
- [ ] 1 notification cuối cùng

### 6.3 Phase 3: Polish (2 days)

**Deliverables**:
- [ ] Error handling
- [ ] On-the-fly dedup
- [ ] Checkpointing (optional)

---

## 📊 Expected Results

| Metric | Current (Batch) | Streaming |
|--------|-----------------|-----------|
| **Time to first feedback** | 30-45s | **3-5s** |
| **User awareness** | "Đang làm gì?" | "Đang review file X" |
| **GitHub notifications** | 1 | 1 (với pending review) |
| **LLM calls** | 3N | N |
| **Perceived speed** | Chậm | **Nhanh hơn nhiều** |

---

## 🎯 Recommendation cho MVP

### Chọn: **Option 1 + Pending Review Pattern**

**Lý do**:
1. ✅ **Simple**: Code dễ hiểu, debug
2. ✅ **Stream real-time**: User thấy progress ngay
3. ✅ **1 notification**: Không spam
4. ✅ **Dedup on-the-fly**: Giảm noise
5. ✅ **Tận dụng LangGraph**: `get_stream_writer()` là core feature
6. ✅ **Dễ upgrade**: Sau này có thể chuyển sang Option 3

**Implementation effort**: ~1 week

---

## 📚 References

- [LangGraph Streaming Concepts](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [get_stream_writer() API](https://langchain-ai.github.io/langgraph/how-tos/streaming-content/)
- [GitHub Reviews API](https://docs.github.com/en/rest/pulls/reviews)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
