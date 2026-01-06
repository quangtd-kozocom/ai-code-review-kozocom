# 01. Tổng quan kiến trúc

## 🎯 Vấn đề cần giải quyết

### Hiện tại: Basic Diff Analysis

```
PR Diff ──▶ LLM ──▶ Comments

Vấn đề:
1. LLM chỉ thấy diff text, không hiểu code structure
2. Không biết context từ codebase
3. Không biết function này được dùng ở đâu
4. False positives cao vì thiếu context
```

### Mục tiêu: Context-Aware Analysis

```
PR Diff ──▶ Tree-sitter ──▶ AST Info
       └──▶ RAG ──────────▶ Related Code
                    │
                    └──▶ LLM (với full context) ──▶ Smart Comments
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENHANCED REVIEW SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ╔═══════════════════════════════════════════════════════════════════╗  │
│  ║  INDEXING LAYER (Background/On-demand)                            ║  │
│  ╠═══════════════════════════════════════════════════════════════════╣  │
│  ║                                                                    ║  │
│  ║   Codebase ──▶ Tree-sitter ──▶ Chunks ──▶ Embeddings ──▶ VectorDB ║  │
│  ║                    │              │                                ║  │
│  ║              Parse files    By function/class                     ║  │
│  ║                                                                    ║  │
│  ╚═══════════════════════════════════════════════════════════════════╝  │
│                                                                          │
│  ╔═══════════════════════════════════════════════════════════════════╗  │
│  ║  REVIEW LAYER (Per PR)                                            ║  │
│  ╠═══════════════════════════════════════════════════════════════════╣  │
│  ║                                                                    ║  │
│  ║   PR Webhook                                                       ║  │
│  ║       │                                                            ║  │
│  ║       ▼                                                            ║  │
│  ║   ┌─────────────────────────────────────────────────────────┐     ║  │
│  ║   │              context_extractor (ENHANCED)               │     ║  │
│  ║   │                                                         │     ║  │
│  ║   │  1. Fetch diff (như cũ)                                │     ║  │
│  ║   │  2. Fetch full file + Parse AST (Tree-sitter)     NEW  │     ║  │
│  ║   │  3. Query related code (RAG)                      NEW  │     ║  │
│  ║   │                                                         │     ║  │
│  ║   └──────────────────────┬──────────────────────────────────┘     ║  │
│  ║                          │                                        ║  │
│  ║                          ▼                                        ║  │
│  ║              ┌───────────────────────┐                            ║  │
│  ║              │  EnhancedFileChange   │                            ║  │
│  ║              │  • patch (diff)       │                            ║  │
│  ║              │  • ast_info           │ ◀── Tree-sitter            ║  │
│  ║              │  • related_context    │ ◀── RAG                    ║  │
│  ║              └───────────┬───────────┘                            ║  │
│  ║                          │                                        ║  │
│  ║           ┌──────────────┼──────────────┐                         ║  │
│  ║           ▼              ▼              ▼                         ║  │
│  ║     ┌──────────┐   ┌──────────┐   ┌──────────┐                   ║  │
│  ║     │ security │   │  logic   │   │  style   │                   ║  │
│  ║     │  agent   │   │  agent   │   │  agent   │                   ║  │
│  ║     └──────────┘   └──────────┘   └──────────┘                   ║  │
│  ║                                                                    ║  │
│  ╚═══════════════════════════════════════════════════════════════════╝  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Directory Structure

```
src/
├── agents/                      # Existing
│   ├── nodes/
│   │   ├── context_extractor.py # MODIFIED: Add AST + RAG
│   │   ├── base_agent.py        # MODIFIED: Enhanced prompts
│   │   └── ...
│   └── prompts/
│       ├── logic.py             # MODIFIED: Add context sections
│       └── ...
│
├── ast/                         # NEW: Tree-sitter
│   ├── __init__.py
│   ├── parser.py                # Multi-language parser
│   ├── models.py                # AST data models
│   └── extractors/
│       ├── __init__.py
│       ├── base.py
│       ├── python.py
│       ├── javascript.py
│       └── php.py
│
└── rag/                         # NEW: RAG System
    ├── __init__.py
    ├── chunker.py               # Smart code chunking
    ├── embedder.py              # Code embedding
    ├── vector_store.py          # ChromaDB wrapper
    ├── retriever.py             # Context retrieval
    └── indexer.py               # Codebase indexing service
```

---

## 🔄 Data Flow

### Phase 1: Indexing (Background)

```
┌──────────────────────────────────────────────────────────────────┐
│  INDEXING FLOW                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   1. Clone/fetch repository                                       │
│      └──▶ All source files                                       │
│                                                                   │
│   2. For each file:                                               │
│      └──▶ Tree-sitter parse                                      │
│          └──▶ Extract functions, classes, etc.                   │
│              └──▶ Create CodeChunks                              │
│                                                                   │
│   3. For each chunk:                                              │
│      └──▶ Generate embedding (CodeBERT)                          │
│          └──▶ Store in VectorDB with metadata                    │
│                                                                   │
│   Result: Searchable vector database of code                      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Phase 2: Review (Per PR)

```
┌──────────────────────────────────────────────────────────────────┐
│  REVIEW FLOW                                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   1. Receive PR webhook                                           │
│      └──▶ Extract: owner, repo, pr_number                        │
│                                                                   │
│   2. Fetch PR data                                                │
│      ├──▶ Diff/patch (như cũ)                                    │
│      └──▶ Full file content (NEW)                                │
│                                                                   │
│   3. Parse with Tree-sitter (NEW)                                 │
│      └──▶ Extract: functions, classes, imports, calls            │
│          └──▶ Identify: changed functions                        │
│                                                                   │
│   4. Query RAG (NEW)                                              │
│      ├──▶ Input: changed function names + signatures             │
│      └──▶ Output: related code, callers, tests                   │
│                                                                   │
│   5. Build EnhancedFileChange                                     │
│      ├──▶ patch: original diff                                   │
│      ├──▶ ast_info: parsed structure                             │
│      └──▶ related_context: RAG results                           │
│                                                                   │
│   6. Send to agents (security, logic, style)                      │
│      └──▶ Agents receive full context                            │
│          └──▶ Better analysis, fewer false positives             │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Benefits

### 1. Better Code Understanding

```python
# Không có Tree-sitter:
"Thấy text: def calculate_total(items, discount=0):"

# Có Tree-sitter:
"Đây là function calculate_total với 2 params:
 - items (required)
 - discount (optional, default=0)
 Return type có thể là float based on operation"
```

### 2. Cross-file Awareness

```python
# Không có RAG:
"Không biết function này được dùng ở đâu"

# Có RAG:
"Function này được gọi bởi:
 - OrderService.process_order() line 45
 - CheckoutAPI.complete() line 78
 - test_order.py có 3 test cases"
```

### 3. Smarter Suggestions

```python
# Không có context:
"Có thể có bug"

# Có full context:
"Function signature thay đổi nhưng 2 callers không được update.
 OrderService.process_order() cần thêm discount parameter."
```

---

## 📊 Metrics Improvement

| Metric               | Before | After  | Improvement    |
| -------------------- | ------ | ------ | -------------- |
| False positive rate  | ~30%   | <15%   | 50%+           |
| Cross-file detection | 0%     | 80%+   | New capability |
| Pattern matching     | None   | Good   | New capability |
| Review quality score | 6/10   | 8.5/10 | 40%+           |

---

## 🔜 Next Steps

1. **Read**: [02-tree-sitter.md](./02-tree-sitter.md) - Chi tiết về AST parsing
2. **Read**: [03-rag-system.md](./03-rag-system.md) - Chi tiết về RAG system
3. **Read**: [04-combined-flow.md](./04-combined-flow.md) - Cách kết hợp 2 systems
