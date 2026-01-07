# 🐰 CodeRabbit Architecture Research

> Research documentation về kiến trúc của CodeRabbit và cách áp dụng vào project AI Code Reviewer.

---

## 📚 Mục Lục

| File                                                             | Nội dung                                   |
| ---------------------------------------------------------------- | ------------------------------------------ |
| ⭐ [00-simple-explanation.md](./00-simple-explanation.md)        | **Giải thích đơn giản (đọc này trước!)**   |
| [01-coderabbit-architecture.md](./01-coderabbit-architecture.md) | Tổng quan kiến trúc CodeRabbit             |
| [02-streaming-pattern.md](./02-streaming-pattern.md)             | Streaming & Incremental Processing Pattern |
| [03-parallel-agent-design.md](./03-parallel-agent-design.md)     | Thiết kế Multi-Agent Song Song             |
| [04-implementation-plan.md](./04-implementation-plan.md)         | Kế hoạch áp dụng vào project               |
| [05-quick-reference.md](./05-quick-reference.md)                 | So sánh nhanh Current vs Target            |

---

## 🎯 Mục Tiêu Research

### Vấn đề hiện tại

```
Current Flow:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Webhook → Extract → [Security + Style + Logic] → Aggregate → Publish  │
│                              ▲                        │                 │
│                              │                        │                 │
│                         Parallel LLM calls           Wait ALL          │
│                         (bottleneck)                 complete           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Problems:
1. Phải đợi TẤT CẢ files xử lý xong mới publish
2. Bottleneck ở LLM API rate limits
3. Không thể nhúng thêm agents/logic vào flow một cách linh hoạt
4. User phải đợi lâu mới thấy feedback
```

### Giải pháp mong muốn

```
Desired Flow:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌──────────┐   ┌──────────────────────────────────────────────┐        │
│  │ File 1   │ → │ Extract → Agents → Publish (Post Comment)    │ ────┐  │
│  └──────────┘   └──────────────────────────────────────────────┘     │  │
│                                                                       │  │
│  ┌──────────┐   ┌──────────────────────────────────────────────┐     │  │
│  │ File 2   │ → │ Extract → Agents → Publish (Post Comment)    │ ────┤  │
│  └──────────┘   └──────────────────────────────────────────────┘     │  │
│                                                                       │  │
│  ┌──────────┐   ┌──────────────────────────────────────────────┐     │  │
│  │ File N   │ → │ Extract → Agents → Publish (Post Comment)    │ ────┤  │
│  └──────────┘   └──────────────────────────────────────────────┘     │  │
│                                                                       │  │
│                                                    Final Summary  ◄───┘  │
└─────────────────────────────────────────────────────────────────────────┘

Benefits:
✓ Xử lý file nào xong thì post comment ngay
✓ Stream real-time feedback cho user
✓ Dễ dàng nhúng thêm agents vào pipeline
✓ Tốt hơn cho UX (thấy progress ngay)
```

---

## 🔍 Key Takeaways từ CodeRabbit

### 1. **Hybrid Architecture**

- Kết hợp Pipeline AI + Agentic AI
- Static analysis + LLM reasoning
- Parallel processing với coordination

### 2. **Incremental Processing**

- Review từng commit thay vì toàn bộ PR
- Post comments ngay khi ready
- Update existing comments thay vì spam mới

### 3. **Parallel Fan-out/Gather Pattern**

- Nhiều specialized agents chạy song song
- Coordinator tổng hợp kết quả
- Rate limiting với semaphore

### 4. **Real-time Streaming**

- LangGraph streaming modes (`updates`, `messages`, `custom`)
- Token-level streaming cho LLM responses
- Progress indicators cho user

---

## 🚀 Quick Start

1. Đọc [01-coderabbit-architecture.md](./01-coderabbit-architecture.md) để hiểu tổng quan
2. Đọc [02-streaming-pattern.md](./02-streaming-pattern.md) để hiểu cách implement streaming
3. Đọc [03-parallel-agent-design.md](./03-parallel-agent-design.md) để hiểu thiết kế agents
4. Đọc [04-implementation-plan.md](./04-implementation-plan.md) để bắt đầu implement

---

## 📊 So sánh với project hiện tại

| Tính năng               | Current         | CodeRabbit     | Gap               |
| ----------------------- | --------------- | -------------- | ----------------- |
| Parallel Agents         | ✅ 3 agents     | ✅ Multi-agent | ✓ Same            |
| Streaming Comments      | ❌ Batch        | ✅ Incremental | Need to implement |
| Per-file Processing     | ❌ All at once  | ✅ Per-file    | Need to implement |
| Dynamic Agent Insertion | ❌ Static graph | ✅ Agentic     | Need `Send` API   |
| Static Analysis         | ❌ None         | ✅ 40+ linters | Nice to have      |
| Learning from Feedback  | ❌ None         | ✅ Continuous  | Nice to have      |

---

## 📁 Related Documentation

- [/docs/explain/rag-ast/](../explain/rag-ast/) - RAG Context implementation
- [/AGENTS.md](/AGENTS.md) - Project coding guidelines
