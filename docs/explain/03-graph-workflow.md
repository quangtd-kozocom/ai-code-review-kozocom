# 🔄 LangGraph Workflow - Fan-out/Fan-in Pattern

## 1. LangGraph là gì?

**LangGraph** là thư viện từ LangChain để xây dựng **stateful, multi-actor applications** với LLMs. Nó cho phép:

- Định nghĩa workflow dạng DAG (Directed Acyclic Graph)
- Quản lý state tự động
- Xử lý song song (parallel execution)
- Conditional branching

## 2. Phân tích `graph.py`

### 2.1. Import và Dependencies

```python
from langgraph.graph import END, StateGraph

from .nodes import (
    acknowledger,
    aggregator,
    context_extractor,
    github_publisher,
    logic_agent,
    security_agent,
    slack_reporter,
    style_agent,
)
from .state import GraphState
```

### 2.2. Khởi tạo Graph

```python
def create_graph() -> StateGraph:
    """Create the review workflow graph."""
    g = StateGraph(GraphState)  # ← Định nghĩa state type
```

**StateGraph** nhận `GraphState` làm type definition để:

- Type-check các state updates
- Auto-merge annotated fields
- Validate node returns

### 2.3. Thêm Nodes

```python
    # Nodes
    g.add_node("acknowledge", acknowledger.run)
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)
```

Mỗi node là một **async function** với signature:

```python
async def run(state: GraphState) -> dict:
    # Process
    return {"field": value}  # Partial state update
```

### 2.4. Định nghĩa Flow

```python
    # Flow
    g.set_entry_point("acknowledge")  # ← Điểm bắt đầu

    # Sequential: acknowledge -> extract
    g.add_edge("acknowledge", "extract")

    # Fan-out: extract -> [security, style, logic] (PARALLEL!)
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")

    # Fan-in: [security, style, logic] -> aggregate
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")

    # Sequential: aggregate -> publish -> notify -> END
    g.add_edge("aggregate", "publish")
    g.add_edge("publish", "notify")
    g.add_edge("notify", END)  # ← Điểm kết thúc
```

### 2.5. Compile và Export

```python
    return g.compile()

# Singleton
graph = create_graph()
```

## 3. Fan-out/Fan-in Pattern Deep Dive

### 3.1. Fan-out (Parallel Execution)

```
                    ┌─────────────┐
                    │   extract   │
                    └─────┬───────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
           ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ security │   │  style   │   │  logic   │
    └──────────┘   └──────────┘   └──────────┘
```

**Khi `extract` hoàn thành:**

1. LangGraph phát hiện 3 outgoing edges
2. Tạo 3 async tasks chạy **đồng thời**
3. Mỗi agent nhận **cùng một state** (snapshot)

### 3.2. Fan-in (Merge Results)

```
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ security │   │  style   │   │  logic   │
    └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │  aggregate   │
                 └──────────────┘
```

**Khi cả 3 agents hoàn thành:**

1. LangGraph chờ tất cả tasks
2. Merge results với `operator.add` cho `comments` field
3. Chuyển state đã merge cho `aggregate`

### 3.3. Merge Mechanism

```python
# State trước khi 3 agents chạy:
state["comments"] = []

# Security agent returns:
{"comments": [comment1, comment2]}

# Style agent returns:
{"comments": [comment3]}

# Logic agent returns:
{"comments": [comment4]}

# LangGraph auto-merges (vì Annotated[..., operator.add]):
state["comments"] = [] + [comment1, comment2] + [comment3] + [comment4]
                  = [comment1, comment2, comment3, comment4]
```

## 4. Visual Graph Representation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph Execution Flow                            │
│                                                                             │
│    START                                                                    │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────┐                                                         │
│  │  acknowledge   │  ─────▶  Posts "🤖 AI Review Started" comment           │
│  └───────┬────────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│  ┌────────────────┐                                                         │
│  │    extract     │  ─────▶  Fetches PR files from GitHub API               │
│  └───────┬────────┘                                                         │
│          │                                                                  │
│  ════════╬════════════════════════════════════════════════════════════      │
│  PARALLEL│ZONE (Fan-out)                                                    │
│          │                                                                  │
│    ┌─────┴──────┬──────────────┐                                           │
│    │            │              │                                            │
│    ▼            ▼              ▼                                            │
│ ┌──────┐    ┌──────┐      ┌──────┐                                         │
│ │ SEC  │    │STYLE │      │LOGIC │   ◀── Each calls LLM concurrently       │
│ └──┬───┘    └──┬───┘      └──┬───┘                                         │
│    │           │             │                                              │
│    └───────────┼─────────────┘                                              │
│                │                                                            │
│  ══════════════╬═══════════════════════════════════════════════════════     │
│  SYNC POINT    │ (Fan-in with operator.add)                                │
│                │                                                            │
│                ▼                                                            │
│  ┌────────────────┐                                                         │
│  │   aggregate    │  ─────▶  Deduplicates, sorts, limits comments          │
│  └───────┬────────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│  ┌────────────────┐                                                         │
│  │    publish     │  ─────▶  Creates PR Review via GitHub API              │
│  └───────┬────────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│  ┌────────────────┐                                                         │
│  │     notify     │  ─────▶  Sends Slack notification                      │
│  └───────┬────────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│        END                                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. Cách invoke Graph

```python
# Từ nơi khác trong codebase
from src.agents import graph

initial_state = {
    "context": PRContext(
        owner="org",
        repo="repo",
        pr_number=123,
        title="Feature X",
        author="dev",
        installation_id=456
    ),
    "files": [],
    "comments": [],
    "final_comments": [],
    "summary": "",
    "acknowledge_comment_id": None,
    "review_id": None,
    "errors": [],
}

# Run the graph
final_state = await graph.ainvoke(initial_state)

# Access results
print(f"Review ID: {final_state['review_id']}")
print(f"Total comments: {len(final_state['final_comments'])}")
```

## 6. Lợi ích của kiến trúc này

| Benefit               | Description                                 |
| --------------------- | ------------------------------------------- |
| **Parallel AI Calls** | 3 agents chạy đồng thời, giảm latency ~3x   |
| **Type Safety**       | TypedDict + Pydantic đảm bảo data integrity |
| **Auto Merge**        | `operator.add` tự động merge results        |
| **Modularity**        | Mỗi node độc lập, dễ test và maintain       |
| **Extensibility**     | Thêm agent mới chỉ cần add_node + add_edge  |
| **Observability**     | LangGraph có built-in tracing               |

---

**Tiếp theo:** [04-nodes-detail.md](./04-nodes-detail.md) - Chi tiết từng node
