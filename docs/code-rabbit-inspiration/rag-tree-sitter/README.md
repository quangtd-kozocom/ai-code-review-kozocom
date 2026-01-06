# 🚀 RAG + Tree-sitter Integration

> Nâng cấp AI Code Review từ basic diff analysis lên intelligent, context-aware analysis.

## 📑 Mục lục

| File                                           | Nội dung                         |
| ---------------------------------------------- | -------------------------------- |
| [01-overview.md](./01-overview.md)             | Tổng quan kiến trúc và flow      |
| [02-tree-sitter.md](./02-tree-sitter.md)       | Tree-sitter integration chi tiết |
| [03-rag-system.md](./03-rag-system.md)         | RAG system architecture          |
| [04-combined-flow.md](./04-combined-flow.md)   | Flow kết hợp RAG + Tree-sitter   |
| [05-implementation.md](./05-implementation.md) | Hướng dẫn implementation         |

---

## 🎯 Mục tiêu

### Hiện tại (Basic)

- Chỉ phân tích diff text
- Mỗi file review độc lập
- Không có context từ codebase

### Sau khi upgrade (Advanced)

- Hiểu code structure (AST)
- Biết cross-file dependencies
- Context từ toàn bộ codebase
- Smart suggestions dựa trên patterns

---

## 🧩 Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Enhanced Review System                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────┐         ┌─────────────────┐          │
│   │   Tree-sitter   │         │       RAG       │          │
│   │   (Microscope)  │         │   (Telescope)   │          │
│   │                 │         │                 │          │
│   │  • Parse AST    │         │  • Embeddings   │          │
│   │  • Extract info │         │  • Vector DB    │          │
│   │  • Understand   │         │  • Retrieval    │          │
│   │    structure    │         │  • Context      │          │
│   └────────┬────────┘         └────────┬────────┘          │
│            │                           │                    │
│            └─────────┬─────────────────┘                    │
│                      │                                      │
│                      ▼                                      │
│            ┌─────────────────┐                              │
│            │  Enhanced       │                              │
│            │  Context for    │                              │
│            │  AI Agents      │                              │
│            └─────────────────┘                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏃 Quick Start

1. Đọc [01-overview.md](./01-overview.md) để hiểu kiến trúc tổng thể
2. Tìm hiểu [02-tree-sitter.md](./02-tree-sitter.md) cho code structure analysis
3. Tìm hiểu [03-rag-system.md](./03-rag-system.md) cho codebase context
4. Xem [04-combined-flow.md](./04-combined-flow.md) để hiểu cách kết hợp
5. Follow [05-implementation.md](./05-implementation.md) để implement

---

## 📊 So sánh Before/After

| Aspect                  | Before      | After         |
| ----------------------- | ----------- | ------------- |
| Code understanding      | Text only   | AST-aware     |
| Context                 | Single file | Full codebase |
| Cross-file analysis     | ❌          | ✅            |
| Pattern detection       | ❌          | ✅            |
| Caller/callee awareness | ❌          | ✅            |
| False positive rate     | ~30%        | <15%          |
