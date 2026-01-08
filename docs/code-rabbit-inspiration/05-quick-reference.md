# 📊 Quick Reference: Current vs Target Architecture

> So sánh nhanh giữa kiến trúc hiện tại và kiến trúc mục tiêu dựa trên CodeRabbit.

---

## 1. Architecture Comparison

### Current Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       CURRENT FLOW (Batch Mode)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Webhook ──▶ Acknowledge ──▶ Extract ──▶ ┌─────────────────────┐    │
│                                          │   PARALLEL AGENTS   │    │
│                                          │                     │    │
│                                          │  Security ──┐       │    │
│                                          │  Style    ──┼──▶ Aggregate    │
│                                          │  Logic    ──┘       │    │
│                                          │                     │    │
│                                          └─────────────────────┘    │
│                                                    │                 │
│                                                    ▼                 │
│                                            Publish (BATCH)           │
│                                              All at once             │
│                                                    │                 │
│                                                    ▼                 │
│                                                 Notify               │
│                                                                      │
│  Time: ████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░   │
│        0s                                 30s                  60s   │
│                                            ▲                         │
│                                            │                         │
│                              First feedback appears here             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Target Architecture (Streaming)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TARGET FLOW (Streaming Mode)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Webhook ──▶ Acknowledge ──▶ Extract ──▶ ┌─────────────────────┐    │
│              (Progress)                   │   DYNAMIC ROUTING   │    │
│                                          │   (Send API)        │    │
│                                          └─────────────────────┘    │
│                                                    │                 │
│                          ┌─────────────────────────┼─────────────┐  │
│                          │                         │             │  │
│                          ▼                         ▼             ▼  │
│                    ┌──────────┐            ┌──────────┐    ┌──────────┐
│                    │  File 1  │            │  File 2  │    │  File N  │
│                    │ Agents   │            │ Agents   │    │ Agents   │
│                    └────┬─────┘            └────┬─────┘    └────┬─────┘
│                         │                       │               │    │
│                         ▼                       ▼               ▼    │
│                    POST Comment            POST Comment    POST Comment
│                    (Immediate)             (Immediate)     (Immediate)
│                         │                       │               │    │
│                         └───────────────────────┼───────────────┘    │
│                                                 │                     │
│                                                 ▼                     │
│                                          Final Summary               │
│                                                                      │
│  Time: ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│        0s  5s                                                   60s  │
│             ▲                                                        │
│             │                                                        │
│    First feedback appears here!                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Feature Comparison

| Feature               | Current        | Target           | CodeRabbit      |
| --------------------- | -------------- | ---------------- | --------------- |
| **Agent System**      |                |                  |                 |
| Parallel Agents       | ✅ 3 agents    | ✅ N agents      | ✅ Many         |
| Dynamic Selection     | ❌ Static      | ✅ Registry      | ✅ Dynamic      |
| Per-file Routing      | ❌ All files   | ✅ By capability | ✅ By content   |
| Agent Priority        | ❌ None        | ✅ Configurable  | ✅ Configurable |
|                       |                |                  |                 |
| **Processing**        |                |                  |                 |
| Streaming             | ❌ Batch       | ✅ Per-file      | ✅ Per-commit   |
| Incremental Post      | ❌ All at once | ✅ As complete   | ✅ As complete  |
| Progress UI           | ❌ None        | ✅ Live update   | ✅ Live update  |
| Error Isolation       | ❌ Can block   | ✅ Per-file      | ✅ Per-file     |
|                       |                |                  |                 |
| **Performance**       |                |                  |                 |
| Time to First Comment | ~30s           | <10s             | <5s             |
| Rate Limiting         | ❌ None        | ✅ Configurable  | ✅ Built-in     |
| Caching               | ❌ None        | ⏳ Future        | ✅ Built-in     |
|                       |                |                  |                 |
| **UX**                |                |                  |                 |
| Real-time Feedback    | ❌             | ✅               | ✅              |
| Progress Indicator    | ❌             | ✅               | ✅              |
| Multi-language        | ✅ en/vi/ja    | ✅ en/vi/ja      | ✅ Multi        |

---

## 3. Code Changes at a Glance

### New Files to Create

```
src/agents/
├── base.py              # BaseReviewAgent, AgentCapability, AgentMetadata
├── registry.py          # AgentRegistry singleton
├── router.py            # route_files_to_processors()
├── streaming_state.py   # FileResult, StreamingGraphState
├── streaming_graph.py   # create_streaming_graph()
├── comment_tracker.py   # CommentTracker for idempotency
├── nodes/
│   ├── file_processor.py     # process_single_file()
│   └── incremental_publisher.py  # post_file_result()
└── templates/
    └── progress.py      # Progress rendering templates

src/core/
└── rate_limiter.py      # RateLimiter class

tests/
├── agents/
│   ├── test_registry.py
│   ├── test_streaming_graph.py
│   └── test_incremental_publisher.py
└── integration/
    └── test_streaming_e2e.py
```

### Files to Modify

```
src/agents/
├── nodes/
│   ├── security_agent.py   # Implement BaseReviewAgent
│   ├── style_agent.py      # Implement BaseReviewAgent
│   ├── logic_agent.py      # Implement BaseReviewAgent
│   └── __init__.py         # Import to trigger registration
└── graph.py                 # Keep for backward compatibility

src/core/
└── config.py               # Add streaming config

src/app/
└── github/
    └── service.py          # Add review posting methods
```

---

## 4. Example: Before vs After

### Before (Current)

```python
# src/agents/graph.py - Static, hardcoded flow
def create_graph() -> StateGraph:
    g = StateGraph(GraphState)

    # Static nodes
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)

    # Static fan-out
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")

    # Wait for ALL, then aggregate
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")

    # Publish ALL at once
    g.add_edge("aggregate", "publish")
```

### After (Target)

```python
# src/agents/streaming_graph.py - Dynamic, streaming flow
from langgraph.graph import StateGraph, Send

def create_streaming_graph() -> StateGraph:
    g = StateGraph(StreamingGraphState)

    # Dynamic processing node
    g.add_node("process_single_file", process_single_file)
    g.add_node("post_file_result", post_file_result)  # Posts immediately!

    # Dynamic fan-out per file (using Send API)
    g.add_conditional_edges(
        "extract",
        route_files_to_processors,  # Returns list[Send]
    )

    # Each file posts immediately when done
    g.add_edge("process_single_file", "post_file_result")

    # Join for summary only
    g.add_edge("post_file_result", "finalize")
```

---

## 5. Timeline Overview

```
Week 1                   Week 2                   Week 3                   Week 4
├─────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┤
│                     │                      │                      │                      │
│  Phase 1            │  Phase 2             │  Phase 3             │  Phase 4 & 5         │
│  Agent Registry     │  Streaming Graph     │  Incremental Post    │  Polish & Rollout    │
│                     │                      │                      │                      │
│  - Base classes     │  - New state         │  - Publisher         │  - Progress UI       │
│  - Registry         │  - Router            │  - Tracking          │  - Testing           │
│  - Migrate agents   │  - File processor    │  - Rate limiter      │  - Feature flags     │
│                     │  - Graph             │                      │  - Documentation     │
│                     │                      │                      │                      │
├─────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┤
│                                                                                          │
│  ████████████████████████████████████████████████████████████████████████████████████   │
│  |         |         |         |         |         |         |         |         |      │
│  Day 1     Day 4     Day 7     Day 10    Day 13    Day 16    Day 19    Day 22    Day 25 │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Quick Start Commands

```bash
# After implementation, test streaming mode:
pytest tests/agents/test_streaming_graph.py -v

# Enable streaming via environment:
export STREAMING_ENABLED=true
make dev

# Run with feature flag:
curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -d '{"action": "opened", ...}'

# Check logs for streaming behavior:
tail -f logs/app.log | grep "streaming\|file_result\|post"
```

---

## 7. Key Decisions Made

| Decision         | Choice                | Rationale                                       |
| ---------------- | --------------------- | ----------------------------------------------- |
| Framework        | LangGraph (keep)      | Already integrated, Send API supports streaming |
| Fan-out          | `Send` API            | Dynamic per-file routing without graph rebuild  |
| Comment Strategy | Review per file       | Balance between immediacy and API efficiency    |
| Rate Limiting    | Custom async limiter  | Simple, no external dependency                  |
| Progress UI      | GitHub comment update | No additional infrastructure needed             |
| Migration        | Feature flags         | Safe rollout with easy rollback                 |
| Agent Registry   | Singleton pattern     | Simple, extensible, Python-idiomatic            |

---

## 8. Related Documentation

- [01-coderabbit-architecture.md](./01-coderabbit-architecture.md) - CodeRabbit deep dive
- [02-streaming-pattern.md](./02-streaming-pattern.md) - Streaming implementation details
- [03-parallel-agent-design.md](./03-parallel-agent-design.md) - Agent system design
- [04-implementation-plan.md](./04-implementation-plan.md) - Detailed implementation plan
