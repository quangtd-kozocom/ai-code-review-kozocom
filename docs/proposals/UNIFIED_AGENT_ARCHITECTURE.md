# 🏗️ Đề xuất Kiến trúc Unified Agent cho MVP

> **Tác giả**: AI Research  
> **Ngày**: 2026-01-08  
> **Status**: Draft - Pending Review

---

## 📋 Mục lục

1. [Tóm tắt vấn đề](#1-tóm-tắt-vấn-đề)
2. [Phân tích kiến trúc hiện tại](#2-phân-tích-kiến-trúc-hiện-tại)
3. [Đề xuất kiến trúc mới](#3-đề-xuất-kiến-trúc-mới)
4. [So sánh Chi tiết](#4-so-sánh-chi-tiết)
5. [Implementation Plan](#5-implementation-plan)
6. [Migration Strategy](#6-migration-strategy)

---

## 1. Tóm tắt vấn đề

### 1.1 Vấn đề hiện tại

| Vấn đề | Mô tả | Impact |
|--------|-------|--------|
| **Comment Noise** | 3 agents (security, style, logic) review cùng 1 file → trùng lặp findings | 🔴 High |
| **LLM Cost cao** | N files × 3 agents = 3N LLM calls | 🔴 High |
| **Fan-in Latency** | Aggregator phải đợi cả 3 agents hoàn thành | 🟡 Medium |
| **Dedup chậm** | Deduplicate sau khi đã tốn LLM calls | 🟡 Medium |
| **Context lãng phí** | 3 agents nhận cùng RAG context | 🟡 Medium |

### 1.2 Ví dụ Noise cụ thể

Với đoạn code:
```python
if len(password) < 8:
    return False
```

**Hiện tại** sẽ nhận:
- ❌ **Security**: "Weak password policy - minimum 8 characters is too short"
- ❌ **Style**: "Magic number 8 - extract to constant MIN_PASSWORD_LENGTH"
- ❌ **Logic**: "Potential off-by-one: should be <= 8?"

→ **3 comments cho 1 dòng code** = NOISE!

---

## 2. Phân tích kiến trúc hiện tại

### 2.1 Graph Flow hiện tại

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ acknowledge │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   extract   │  ← RAG enrichment
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ security │    │  style   │    │  logic   │   ← 3 PARALLEL AGENTS
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  aggregate  │  ← Dedup SAU KHI đã chạy hết
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │   publish   │
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │   notify    │
                  └──────┬──────┘
                         │
                         ▼
                    ┌─────────────┐
                    │     END     │
                    └─────────────┘
```

### 2.2 Chi tiết vấn đề

#### A) Mỗi agent xử lý độc lập
```python
# base_agent.py hiện tại
async def run(state: GraphState) -> dict:
    files = [f for f in state["files"] if f.patch]  # TẤT CẢ files
    
    # Xử lý TỪNG file với TỪNG agent
    for file in files:
        findings = await llm.invoke(prompt)  # 1 LLM call
```

**→ Với 10 files = 30 LLM calls!**

#### B) Không có coordination giữa agents
- Security agent không biết Style agent đã flag gì
- Logic agent có thể lặp lại Security findings
- Aggregator chỉ dedup theo (file, line, category) - quá cơ bản

#### C) RAG context giống nhau cho tất cả
```python
# Tất cả agents nhận cùng related_context
if rag_context:
    parts.append(f"## Related Code Context: {rag_context}")
```

---

## 3. Đề xuất kiến trúc mới

### 3.1 Option A: Unified Single Agent (Recommended cho MVP)

**Ý tưởng**: Gộp 3 agents thành 1 agent duy nhất với comprehensive prompt.

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ acknowledge │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   extract   │
                    └──────┬──────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ unified_review  │  ← 1 AGENT với comprehensive review
                  └────────┬────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   publish   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   notify    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │     END     │
                    └─────────────┘
```

**Ưu điểm**:
- ✅ Giảm 3N → N LLM calls (tiết kiệm 66% cost)
- ✅ LLM tự coordinate: không trùng lặp findings
- ✅ Context đầy đủ trong 1 prompt → quyết định tốt hơn
- ✅ Đơn giản hóa graph
- ✅ Phù hợp với MVP

**Nhược điểm**:
- ⚠️ Prompt dài hơn (nhưng vẫn trong context window)
- ⚠️ Khó parallelize theo agent type

---

### 3.2 Option B: Smart Router + Specialized Agents

**Ý tưởng**: Thêm Router node để quyết định agents nào cần chạy.

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ acknowledge │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   extract   │
                    └──────┬──────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  smart_router   │  ← Phân tích file → quyết định agents
                  └────────┬────────┘
                           │
              ┌────────────┼────────────┐ (conditional)
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ security │ │  style   │ │  logic   │
        │ (nếu có  │ │ (nếu     │ │ (nếu có  │
        │ security │ │ enable)  │ │ bugs)    │
        │ patterns)│ │          │ │          │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  aggregate  │
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   publish   │
                   └─────────────┘
```

**Router Logic**:
```python
def smart_router(state: GraphState) -> list[str]:
    agents = []
    file = state["current_file"]
    
    # Security: chỉ với files có risk patterns
    if has_security_patterns(file):  # SQL, exec, input handling
        agents.append("security")
    
    # Style: chỉ với source files (không test)
    if not is_test_file(file) and config.style_enabled:
        agents.append("style")
    
    # Logic: chỉ với files có functions/classes changed
    if has_logic_changes(file):
        agents.append("logic")
    
    return agents if agents else ["quick_review"]
```

**Ưu điểm**:
- ✅ Chỉ chạy agents cần thiết
- ✅ Giữ specialized knowledge của từng agent
- ✅ Flexible, dễ mở rộng

**Nhược điểm**:
- ⚠️ Router có thể sai (false negatives)
- ⚠️ Phức tạp hơn Option A
- ⚠️ Vẫn có thể trùng findings

---

### 3.3 Option C: File-Level Parallel với Unified Review

**Ý tưởng**: Parallelize theo FILE thay vì theo AGENT TYPE.

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ acknowledge │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   extract   │
                    └──────┬──────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  fan_out_files  │  ← Send() API
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  ┌───────────┐      ┌───────────┐      ┌───────────┐
  │ review    │      │ review    │      │ review    │
  │ file_1    │      │ file_2    │      │ file_N    │
  │(unified)  │      │(unified)  │      │(unified)  │
  └─────┬─────┘      └─────┬─────┘      └─────┬─────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  aggregate  │  ← Gộp từ all files
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   publish   │
                    └─────────────┘
```

**Implementation với LangGraph Send()**:
```python
from langgraph.types import Send

def fan_out_files(state: GraphState):
    """Tạo parallel review tasks cho mỗi file"""
    return [
        Send("review_file", {
            "file": file,
            "config": state["repo_config"],
            "context": state["context"]
        })
        for file in state["files"]
        if file.patch  # Chỉ files có changes
    ]

builder.add_conditional_edges("extract", fan_out_files, ["review_file"])
```

**Ưu điểm**:
- ✅ True parallelism (mỗi file parallel)
- ✅ Unified review per file = no duplication
- ✅ Scales với số files
- ✅ Sử dụng đúng sức mạnh LangGraph Send() API

**Nhược điểm**:
- ⚠️ Mất cross-file context (file A gọi function trong file B)
- ⚠️ State management phức tạp hơn

---

### 3.4 Option D: Streaming Publish (File-by-File)

**Ý tưởng**: Xử lý xong file nào → publish comment lên GitHub ngay, không đợi.

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ acknowledge │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   extract   │
                    └──────┬──────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   for each file:       │
              │   ┌──────────────────┐ │
              │   │  review_file     │ │──► POST comment to GitHub NGAY
              │   └──────────────────┘ │
              │            ↓           │
              │   ┌──────────────────┐ │
              │   │  review_file     │ │──► POST comment to GitHub NGAY
              │   └──────────────────┘ │
              │            ↓           │
              │          ...           │
              └────────────┬───────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   summary   │  ← Chỉ post summary cuối cùng
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   notify    │
                    └─────────────┘
```

**Implementation**:
```python
async def streaming_review(state: GraphState) -> dict:
    """Review và publish từng file ngay lập tức"""
    github = GitHubClient(state["context"])
    all_comments = []
    
    for file in state["files"]:
        if not file.patch:
            continue
            
        # 1. Review file
        findings = await unified_review_file(file, state["repo_config"])
        
        # 2. Publish NGAY (không đợi)
        if findings:
            await github.create_review_comments(
                pr_number=state["context"].pr_number,
                comments=findings
            )
            all_comments.extend(findings)
        
        # 3. Yield progress (optional - for UI updates)
        yield {"processed": file.filename, "findings_count": len(findings)}
    
    return {"comments": all_comments}
```

#### Trade-offs Analysis cho MVP:

| Aspect | Batch (Options A-C) | Streaming (Option D) |
|--------|--------------------|--------------------|
| **User Experience** | Đợi 20-30s rồi thấy tất cả | Thấy từng comment ngay (~3s/file) |
| **GitHub API** | 1-2 API calls | N API calls (mỗi file 1 call) |
| **Rate Limit Risk** | 🟢 Thấp | 🟡 Trung bình (nếu PR lớn) |
| **Cross-file Dedup** | ✅ Có thể | ❌ Không thể |
| **Summary Quality** | ✅ Biết tổng thể trước | 🟡 Summary sau cùng |
| **Error Handling** | Rollback dễ | Partial state phức tạp |
| **Implementation** | 🟢 Đơn giản | 🟡 Phức tạp hơn |

#### ⚠️ Vấn đề với Streaming cho MVP:

1. **GitHub Notifications Spam**: 
   - Mỗi comment = 1 notification cho PR author
   - 10 files × 3 comments = 30 notifications! 😱

2. **Không thể Global Dedup**:
   ```python
   # File A: "Magic number 100 detected"
   # File B: "Magic number 100 detected"  
   # → Với batch: có thể gộp thành 1 finding
   # → Với streaming: 2 comments riêng biệt
   ```

3. **Summary khó chính xác**:
   - Batch: "Found 5 critical, 3 warnings across 10 files"
   - Streaming: Phải update summary liên tục hoặc đợi cuối

4. **Rate Limits**:
   - GitHub API: 5000 requests/hour
   - Nếu PR có 50 files, mỗi file 3 comments = 150 API calls
   - Với nhiều PRs đồng thời → có thể hit limit

---

### 3.5 💡 Option E: Hybrid Batch-Stream (Recommended cho MVP + Quality)

**Ý tưởng**: Kết hợp ưu điểm của cả hai:
- **Batch review** để có cross-file context và dedup
- **Chunked publish** để user thấy progress sớm

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ acknowledge │  ← "AI Review started..."
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   extract   │
                    └──────┬──────┘
                           │
                           ▼
        ┌─────────────────────────────────────┐
        │         unified_review              │
        │  (parallel review ALL files)        │
        │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
        │  │ f1  │ │ f2  │ │ f3  │ │ ... │   │
        │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘   │
        │     └───────┴───────┴───────┘       │
        │                 │                   │
        │                 ▼                   │
        │        ┌──────────────┐             │
        │        │  quick_dedup │             │
        │        └──────────────┘             │
        └─────────────────┬───────────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   publish   │  ← 1 GitHub Review với ALL comments
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   notify    │
                   └─────────────┘
```

**Tại sao Hybrid tốt cho MVP?**

| Yêu cầu MVP | Hybrid đáp ứng |
|-------------|----------------|
| **Chạy được** | ✅ Simple flow, ít edge cases |
| **Chất lượng** | ✅ Cross-file dedup, proper summary |
| **UX chấp nhận được** | ✅ ~15-20s total (acceptable) |
| **Maintainable** | ✅ Code đơn giản |
| **Cost effective** | ✅ 1 GitHub Review API call |

**Key insight**: GitHub hỗ trợ **1 Review với nhiều comments** = 1 API call!

```python
# Thay vì N API calls (streaming):
for comment in comments:
    await github.create_comment(comment)  # N calls

# Dùng 1 Review API call (batch):
await github.create_review(
    pr_number=pr.number,
    body=summary,
    event="COMMENT",
    comments=[
        {"path": c.file, "line": c.line, "body": c.message}
        for c in all_comments
    ]
)  # 1 call với tất cả comments!
```

---

## 4. So sánh Chi tiết

### 4.1 Comparison Matrix

| Tiêu chí | Current | A (Unified) | B (Router) | C (File Parallel) | D (Streaming) | E (Hybrid) ⭐ |
|----------|---------|-------------|------------|-------------------|---------------|---------------|
| **LLM Calls** | 3N | N | ~1.5N | N | N | N |
| **GitHub API Calls** | 1 | 1 | 1 | 1 | N | 1 |
| **Cost** | 🔴 High | 🟢 Low | 🟡 Med | 🟢 Low | 🟢 Low | 🟢 Low |
| **Noise** | 🔴 High | 🟢 Low | 🟡 Med | 🟢 Low | 🟡 Med | 🟢 Low |
| **UX Speed** | 🔴 Slow | 🟡 Med | 🟡 Med | 🟡 Med | 🟢 Fast | 🟡 Med |
| **Cross-file Dedup** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Complexity** | Med | 🟢 Simple | 🟡 Med | 🟡 Med | 🟡 Med | 🟢 Simple |
| **MVP Fit** | ❌ | ✅✅ | ✅ | ✅ | 🟡 | ✅✅ |

### 4.2 Recommendation cho MVP

> **🏆 Đề xuất: Option E (Hybrid) hoặc Option A (Unified)**
>
> Cả hai đều phù hợp MVP. Option E = Option A + tối ưu GitHub API.

**Lý do**:
1. **Simplicity**: MVP cần nhanh, đơn giản
2. **Cost Effective**: Giảm 66% LLM calls
3. **Zero Noise**: 1 agent = 1 decision per line
4. **Quick Implementation**: ~2-3 days
5. **Easy Rollback**: Có thể quay lại multi-agent sau

**Future Enhancement Path**:
```
MVP (Option A) → Phase 2 (Option C) → Phase 3 (Option B + C hybrid)
```

---

## 5. Implementation Plan

### 5.1 Unified Agent Design

#### A) New Prompt Structure

```python
UNIFIED_REVIEW_PROMPT = """
You are an expert code reviewer. Analyze this code change comprehensively.

## Review Dimensions (in priority order):

### 1. 🔴 CRITICAL: Security Issues
- SQL injection, XSS, command injection
- Hardcoded secrets, weak crypto
- Authentication/authorization flaws

### 2. 🟡 IMPORTANT: Logic & Bugs
- Off-by-one errors, null pointer dereferences
- Race conditions, incorrect comparisons
- Missing edge case handling

### 3. 🔵 SUGGESTION: Code Quality
- Naming conventions, magic numbers
- Code complexity, missing types
- Documentation gaps

## Rules:
1. ONE finding per unique issue - NO duplicates
2. If issue spans multiple dimensions, categorize by HIGHEST severity
3. Max 5 findings per file
4. Provide actionable suggestions

## File to Review:
{file_content}

## Diff:
{diff}

## Related Context:
{rag_context}
"""
```

#### B) New Output Schema

```python
from pydantic import BaseModel
from typing import Literal

class UnifiedFinding(BaseModel):
    """Single comprehensive finding"""
    file: str
    line: int
    severity: Literal["critical", "warning", "suggestion", "info"]
    dimension: Literal["security", "logic", "quality"]  # Primary dimension
    title: str
    description: str
    suggestion: str | None = None
    
class UnifiedReviewOutput(BaseModel):
    """Output từ unified review"""
    findings: list[UnifiedFinding]
    summary: str
    confidence: float  # 0-1, để track quality
```

#### C) New Agent Node

```python
# src/agents/nodes/unified_reviewer.py

from langchain_core.prompts import PromptTemplate
from ..prompts.unified import UNIFIED_REVIEW_PROMPT
from ..models import UnifiedReviewOutput, ReviewComment

async def run(state: GraphState) -> dict:
    """
    Unified code reviewer - replaces security, style, logic agents.
    """
    config = state["repo_config"]
    files = [f for f in state["files"] if f.patch]
    
    all_comments: list[ReviewComment] = []
    
    # Process files with concurrency control
    semaphore = asyncio.Semaphore(5)
    
    async def review_file(file: EnhancedFileChange) -> list[ReviewComment]:
        async with semaphore:
            prompt = _build_unified_prompt(file, config)
            
            result = await llm.with_structured_output(
                UnifiedReviewOutput
            ).ainvoke(prompt)
            
            return _convert_to_comments(result.findings, file)
    
    # Run reviews in parallel
    tasks = [review_file(f) for f in files]
    results = await asyncio.gather(*tasks)
    
    for comments in results:
        all_comments.extend(comments)
    
    return {"comments": all_comments}


def _build_unified_prompt(file: EnhancedFileChange, config: ReviewerConfig) -> str:
    """Build comprehensive prompt với tất cả context"""
    
    parts = [UNIFIED_REVIEW_PROMPT]
    
    # Add repo-specific instructions
    if config.custom_instructions:
        parts.append(f"\n## Repository Guidelines:\n{config.custom_instructions}")
    
    # Add RAG context
    if file.related_context:
        rag_section = _format_rag_context(file.related_context)
        parts.append(f"\n## Related Code:\n{rag_section}")
    
    return "\n".join(parts).format(
        file_content=file.full_content[:5000],  # Limit context
        diff=file.patch,
        rag_context=rag_section if file.related_context else "N/A"
    )
```

### 5.2 New Graph Definition

```python
# src/agents/graph.py (updated)

from langgraph.graph import StateGraph, START, END
from .state import GraphState
from .nodes import (
    acknowledger,
    context_extractor,
    unified_reviewer,  # NEW: replaces 3 agents
    aggregator,
    github_publisher,
    slack_reporter,
)

def build_review_graph() -> StateGraph:
    """Build simplified unified review graph"""
    
    g = StateGraph(GraphState)
    
    # Nodes
    g.add_node("acknowledge", acknowledger.run)
    g.add_node("extract", context_extractor.run)
    g.add_node("review", unified_reviewer.run)  # SINGLE unified agent
    g.add_node("aggregate", aggregator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)
    
    # Simple linear flow
    g.add_edge(START, "acknowledge")
    g.add_edge("acknowledge", "extract")
    g.add_edge("extract", "review")  # Direct to unified review
    g.add_edge("review", "aggregate")
    g.add_edge("aggregate", "publish")
    g.add_edge("publish", "notify")
    g.add_edge("notify", END)
    
    return g.compile()
```

### 5.3 Updated Aggregator

```python
# src/agents/nodes/aggregator.py (simplified)

def run(state: GraphState) -> dict:
    """
    Simplified aggregator - unified agent đã loại bỏ duplicates.
    Chỉ cần sort và limit.
    """
    comments = state.get("comments", [])
    config = state["repo_config"]
    
    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "suggestion": 2, "info": 3}
    sorted_comments = sorted(
        comments,
        key=lambda c: (severity_order.get(c.severity, 4), c.file, c.line)
    )
    
    # Limit per file
    limited = _limit_per_file(sorted_comments, config.max_comments_per_file)
    
    # Generate summary
    summary = _generate_summary(limited)
    
    return {
        "final_comments": limited,
        "summary": summary
    }
```

---

## 6. Migration Strategy

### 6.1 Phase 1: Parallel Run (1 week)

```python
# Chạy cả 2 systems song song để compare

async def run_comparison(pr_context: PRContext):
    # Old system
    old_result = await old_graph.ainvoke({"context": pr_context})
    
    # New unified system
    new_result = await new_graph.ainvoke({"context": pr_context})
    
    # Compare và log
    comparison = compare_results(old_result, new_result)
    log.info("comparison_result", 
             old_count=len(old_result["final_comments"]),
             new_count=len(new_result["final_comments"]),
             overlap_ratio=comparison.overlap_ratio)
```

### 6.2 Phase 2: Gradual Rollout (1 week)

```python
# Feature flag based rollout
async def review_pr(pr_context: PRContext):
    if feature_flags.use_unified_agent(pr_context.repo):
        graph = unified_graph
    else:
        graph = legacy_graph
    
    return await graph.ainvoke({"context": pr_context})
```

### 6.3 Phase 3: Full Migration (1 week)

1. Remove legacy agents code
2. Update documentation
3. Monitor metrics

### 6.4 Rollback Plan

```python
# Giữ legacy agents trong archive
# src/agents/nodes/_legacy/
#   ├── security_agent.py
#   ├── style_agent.py
#   └── logic_agent.py

# Quick rollback:
# git revert <unified-agent-commit>
```

---

## 📊 Expected Metrics Improvement

| Metric | Current | After Unified | Improvement |
|--------|---------|---------------|-------------|
| LLM Calls/PR | ~30 (10 files × 3) | ~10 | **-66%** |
| Review Time | ~45s | ~20s | **-55%** |
| Comments/PR | ~25 | ~12 | **-52% (less noise)** |
| Cost/PR | ~$0.15 | ~$0.05 | **-66%** |
| Duplicate Rate | ~15% | ~2% | **-87%** |

---

## ✅ Next Steps

1. [ ] Review và approve proposal này
2. [ ] Implement unified prompt
3. [ ] Create unified_reviewer.py
4. [ ] Update graph.py
5. [ ] Run comparison tests
6. [ ] Gradual rollout
7. [ ] Monitor và iterate

---

## 📚 References

- [LangGraph Multi-Agent Patterns](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [LangGraph Supervisor Pattern](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)
- [LangGraph Send API](https://langchain-ai.github.io/langgraph/how-tos/send/)
- [LangGraph State Management](https://langchain-ai.github.io/langgraph/concepts/low_level/#state)
