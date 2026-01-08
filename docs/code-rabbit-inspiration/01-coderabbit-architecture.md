# 🏗️ CodeRabbit Architecture Deep Dive

> Phân tích chi tiết kiến trúc của CodeRabbit dựa trên research từ nhiều nguồn.

---

## 1. Tổng Quan Kiến Trúc

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CodeRabbit System Architecture                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────┐   │
│  │   GitHub/GitLab  │───▶│  Webhook Handler │───▶│   Google Cloud Tasks     │   │
│  │     (Webhooks)   │    │  (Cloud Run)     │    │   (Queue)                │   │
│  └──────────────────┘    └──────────────────┘    └──────────────────────────┘   │
│                                                              │                   │
│                                                              ▼                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        Processing Pipeline                                │   │
│  ├──────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                           │   │
│  │  ┌─────────────┐   ┌──────────────────────────────────────────────────┐  │   │
│  │  │   Clone     │   │           Static Analysis Layer                   │  │   │
│  │  │   Repo      │──▶│  • 40+ Linters & Security Scanners               │  │   │
│  │  │             │   │  • AST Analysis                                   │  │   │
│  │  └─────────────┘   │  • Code Graph Analysis                           │  │   │
│  │                     └──────────────────────────────────────────────────┘  │   │
│  │                                          │                                │   │
│  │                                          ▼                                │   │
│  │  ┌──────────────────────────────────────────────────────────────────────┐│   │
│  │  │                         LLM Agent Layer                               ││   │
│  │  ├──────────────────────────────────────────────────────────────────────┤│   │
│  │  │                                                                       ││   │
│  │  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ ││   │
│  │  │   │  Security   │  │   Style     │  │   Logic     │  │ Performance │ ││   │
│  │  │   │  Auditor    │  │  Enforcer   │  │  Analyzer   │  │  Optimizer  │ ││   │
│  │  │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ ││   │
│  │  │                                                                       ││   │
│  │  │   ┌─────────────────────────────────────────────────────────────────┐││   │
│  │  │   │              Agentic Tooling (Shell, grep, ast-grep, Python)    │││   │
│  │  │   └─────────────────────────────────────────────────────────────────┘││   │
│  │  └──────────────────────────────────────────────────────────────────────┘│   │
│  │                                          │                                │   │
│  │                                          ▼                                │   │
│  │  ┌──────────────────────────────────────────────────────────────────────┐│   │
│  │  │                         Output Layer                                  ││   │
│  │  │  • Line-by-line Comments                                             ││   │
│  │  │  • PR Summary                                                         ││   │
│  │  │  • Security Findings                                                  ││   │
│  │  │  • One-click Fixes                                                    ││   │
│  │  └──────────────────────────────────────────────────────────────────────┘│   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      Ephemeral Container (Privacy)                        │   │
│  │  • Code không lưu trữ lâu dài                                            │   │
│  │  • Không dùng để training                                                 │   │
│  │  • Container destroy sau khi xử lý                                        │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Hybrid AI Architecture

CodeRabbit sử dụng **hybrid architecture** kết hợp 2 paradigms:

#### Pipeline AI (Deterministic)

```
Input → Static Analysis → Preprocessing → LLM Prompt → Postprocessing → Output
```

- **Ưu điểm**: Dự đoán được, consistent, dễ debug
- **Nhược điểm**: Không linh hoạt, khó handle edge cases

#### Agentic AI (Autonomous)

```
Input → Observe → Think → Plan → Act → Observe → ... → Output
```

- **Ưu điểm**: Linh hoạt, có thể khám phá codebase
- **Nhược điểm**: Khó dự đoán, cần guardrails

#### Hybrid Approach của CodeRabbit

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Hybrid Review Pipeline                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PIPELINE PHASE                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 1. Collect diff/context                                        │  │
│  │ 2. Run static analyzers                                        │  │
│  │ 3. Build code graph                                            │  │
│  │ 4. Prepare structured prompt                                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  AGENTIC PHASE                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 5. LLM reasons about code                                      │  │
│  │ 6. Agent uses tools when needed:                               │  │
│  │    • grep/ast-grep to search patterns                          │  │
│  │    • Python code for analysis                                  │  │
│  │    • curl for external services (Jira, Linear)                 │  │
│  │ 7. Iterative refinement based on observations                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  PIPELINE PHASE                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 8. Validate & filter output                                    │  │
│  │ 9. Format as GitHub comments                                   │  │
│  │ 10. Post results                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Scalability & Performance

### 2.1 Infrastructure (Google Cloud Run)

```
Peak Performance:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Concurrent Requests: Up to 10 requests/second                      │
│  Cloud Run Instances: 200+ during peak times                        │
│  Configuration per Instance:                                         │
│    • Significant CPU allocation                                      │
│    • High memory for code analysis                                   │
│                                                                      │
│  Benefits:                                                           │
│  ✓ Dynamic scaling based on demand                                  │
│  ✓ Ephemeral containers (privacy)                                   │
│  ✓ Pay per use                                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Queue-based Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│   Webhook   │───▶│  Cloud Run      │───▶│  Cloud Tasks Queue  │
│   Events    │    │  (Lightweight)  │    │                     │
└─────────────┘    │  - Validate     │    │  - Decouple events  │
                   │  - Check billing│    │  - Handle bursts    │
                   │  - Enqueue      │    │  - Retry on failure │
                   └─────────────────┘    └─────────────────────┘
                                                   │
                                                   ▼
                   ┌─────────────────────────────────────────────┐
                   │              Worker Instances                │
                   │                                              │
                   │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
                   │  │ Worker  │  │ Worker  │  │ Worker  │ ... │
                   │  └─────────┘  └─────────┘  └─────────┘     │
                   │                                              │
                   └─────────────────────────────────────────────┘
```

**Key Design Decisions:**

1. **Lightweight Webhook Handler**: Chỉ validate và enqueue, không xử lý nặng
2. **Queue Decoupling**: Tách webhook handling khỏi processing
3. **Burst Handling**: Queue có thể buffer requests khi có spike
4. **Retry Logic**: Tự động retry khi có failures

---

## 3. Multi-Agent Coordination Patterns

### 3.1 Pattern 1: Parallel Fan-out/Gather

```
                    ┌───────────────┐
                    │   Router/     │
                    │  Coordinator  │
                    └───────┬───────┘
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Security │  │  Style   │  │  Logic   │
        │  Agent   │  │  Agent   │  │  Agent   │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                    ┌───────────────┐
                    │   Aggregator  │
                    └───────────────┘
```

**Đặc điểm:**

- Các agents chạy song song
- Không có dependency giữa các agents
- Aggregator tổng hợp kết quả

### 3.2 Pattern 2: Sequential Pipeline

```
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
│ Parse  │──▶│ Enrich │──▶│ Analyze│──▶│ Format │
│ Agent  │   │ Agent  │   │ Agent  │   │ Agent  │
└────────┘   └────────┘   └────────┘   └────────┘
```

**Đặc điểm:**

- Output của agent trước là input của agent sau
- Phù hợp khi có data transformation steps
- Dễ debug từng step

### 3.3 Pattern 3: Generator-Critic (Iterative Refinement)

```
┌─────────────────────────────────────────┐
│                                          │
│   ┌────────────┐      ┌────────────┐    │
│   │ Generator  │─────▶│  Critic    │    │
│   │ Agent      │      │  Agent     │    │
│   └────────────┘      └────────────┘    │
│         ▲                   │            │
│         │                   │            │
│         └───────────────────┘            │
│              (Not Pass)                  │
│                                          │
│              Pass? ─────────▶ Output     │
│                                          │
└─────────────────────────────────────────┘
```

**Đặc điểm:**

- Generator tạo output (code fix, review comment)
- Critic đánh giá chất lượng
- Loop cho đến khi pass criteria

### 3.4 Pattern 4: Supervisor with Sub-agents (CodeRabbit's Approach)

```
┌───────────────────────────────────────────────────────────────────────┐
│                           Supervisor Agent                             │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  1. Analyze PR context                                          │   │
│  │  2. Decide which sub-agents to invoke                          │   │
│  │  3. Coordinate parallel execution                               │   │
│  │  4. Synthesize results                                          │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌───────────────────────────────────────────────────────────────────┐│
│  │                        Tool/Agent Pool                            ││
│  │                                                                    ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            ││
│  │  │   Static     │  │    LLM       │  │   External   │            ││
│  │  │  Analyzers   │  │   Agents     │  │   Tools      │            ││
│  │  │              │  │              │  │              │            ││
│  │  │  • Linters   │  │  • Security  │  │  • grep      │            ││
│  │  │  • SAST      │  │  • Style     │  │  • ast-grep  │            ││
│  │  │  • Type-check│  │  • Logic     │  │  • shell     │            ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘            ││
│  │                                                                    ││
│  └───────────────────────────────────────────────────────────────────┘│
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 4. LLM Integration

### 4.1 Models Used

| Provider  | Models                  | Use Case          |
| --------- | ----------------------- | ----------------- |
| OpenAI    | GPT-4.5, o3, o4-mini    | Primary reasoning |
| Anthropic | Claude Opus 4, Sonnet 4 | Complex analysis  |
| NVIDIA    | Nemotron                | Scalability       |

### 4.2 Structured Output

CodeRabbit sử dụng structured output để đảm bảo consistency:

```python
# Example structured output schema
class ReviewFinding(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "warning", "info", "suggestion"]
    category: str
    message: str
    suggestion: str | None
    confidence: float
```

### 4.3 Prompt Engineering Strategies

1. **Context Preparation**: Collect diff, file content, AST info
2. **Structured Instructions**: Clear output format expectations
3. **Chain-of-Thought**: "Think step by step" reasoning
4. **Few-shot Examples**: Real examples for better accuracy

---

## 5. Learning & Adaptation

### 5.1 Feedback Loop

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Learning Loop                                  │
│                                                                       │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐│
│  │ AI Posts   │───▶│ Developer  │───▶│ Feedback   │───▶│ Update     ││
│  │ Comment    │    │ Responds   │    │ Collected  │    │ Behavior   ││
│  └────────────┘    └────────────┘    └────────────┘    └────────────┘│
│                                                                       │
│  Signals:                                                             │
│  • Thread resolved → Good feedback                                   │
│  • Replied with disagreement → Bad feedback                          │
│  • Code changed as suggested → Very good feedback                    │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Customization

- **`.coderabbit.yaml`**: Repository-specific config
- **Path-based Rules**: Different rules for different directories
- **Team Preferences**: Learn from team's coding style

---

## 6. Key Takeaways for Implementation

### 6.1 Architecture Decisions

| Decision        | CodeRabbit            | Recommendation for Our Project      |
| --------------- | --------------------- | ----------------------------------- |
| Queue System    | Google Cloud Tasks    | Celery/Redis (already have)         |
| Container       | Cloud Run (ephemeral) | Docker containers                   |
| LLM Provider    | Multi-provider        | Keep OpenRouter abstraction         |
| Static Analysis | 40+ tools             | Start with core tools, expand later |
| Agent Framework | Custom hybrid         | LangGraph (already using)           |

### 6.2 Immediate Improvements

1. **Incremental Posting**: Post comments as they complete
2. **Per-file Processing**: Process files independently
3. **Streaming**: Use LangGraph streaming for real-time feedback
4. **Send API**: Dynamic agent fan-out

### 6.3 Future Improvements

1. Add static analysis tools (ESLint, Ruff, etc.)
2. Implement feedback learning loop
3. Add more specialized agents
4. IDE integration (VS Code extension)

---

## 📚 References

- [Google Cloud Blog: CodeRabbit Case Study](https://cloud.google.com/)
- [CodeRabbit Documentation](https://docs.coderabbit.ai/)
- [InfoWorld: CodeRabbit Review](https://infoworld.com/)
- [LangGraph Documentation](https://langchain.com/langgraph)
