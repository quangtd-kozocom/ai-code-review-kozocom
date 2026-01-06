# 03. RAG System - Codebase Context Retrieval

## 🎯 RAG là gì và tại sao cần?

### Retrieval-Augmented Generation (RAG)

```
RAG = Retrieval (tìm kiếm) + Generation (sinh nội dung)

Thay vì LLM phải "nhớ" tất cả → Cho LLM "tra cứu" thông tin liên quan
```

### Trong context Code Review

| Không có RAG                    | Có RAG                                      |
| ------------------------------- | ------------------------------------------- |
| LLM chỉ thấy diff của 1 file    | LLM được cung cấp code liên quan từ cả repo |
| Không biết patterns của project | Biết conventions đang dùng                  |
| Không biết ai gọi function này  | Tìm được callers/usages                     |
| Không biết có test chưa         | Tìm được related tests                      |

---

## 🏗️ RAG Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAG PIPELINE                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════     │
│  PHASE 1: INDEXING (Chạy offline, 1 lần hoặc khi code thay đổi)             │
│  ══════════════════════════════════════════════════════════════════════     │
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────┐  │
│   │  Codebase    │───▶│   Chunker    │───▶│  Embedder    │───▶│ VectorDB│  │
│   │  (all files) │    │ (chia nhỏ)   │    │(số hóa text) │    │ (lưu trữ)│  │
│   └──────────────┘    └──────────────┘    └──────────────┘    └─────────┘  │
│                                                                              │
│   Ví dụ:                                                                     │
│   services/order.py ──▶ [OrderService class, calculate_total func, ...]    │
│                      ──▶ [embedding vector cho mỗi chunk]                   │
│                      ──▶ Lưu vào ChromaDB                                   │
│                                                                              │
│  ══════════════════════════════════════════════════════════════════════     │
│  PHASE 2: RETRIEVAL (Mỗi khi review PR)                                      │
│  ══════════════════════════════════════════════════════════════════════     │
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────┐  │
│   │  PR Diff     │───▶│   Query      │───▶│   Search     │───▶│ Related │  │
│   │  (code mới)  │    │ Generation   │    │  VectorDB    │    │  Code   │  │
│   └──────────────┘    └──────────────┘    └──────────────┘    └─────────┘  │
│                                                                              │
│   Ví dụ:                                                                     │
│   "def calculate_total" ──▶ Query: "calculate_total function"              │
│                          ──▶ Search similar vectors                         │
│                          ──▶ Trả về: callers, tests, similar functions     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Các components chính

### 1. Chunker - Chia code thành chunks

**Vấn đề**: Không thể embed cả file vì quá dài và thiếu focus

**Giải pháp**: Chia theo semantic units (function, class)

```
┌────────────────────────────────────────────────────────┐
│ File: services/order.py                                │
├────────────────────────────────────────────────────────┤
│                                                        │
│  from models import Order, Item    ◀── Chunk 1: Imports│
│                                                        │
│  class OrderService:               ◀── Chunk 2: Class  │
│      def __init__(self):                               │
│          self.db = Database()                          │
│                                                        │
│      def create_order(self, ...):  ◀── Chunk 3: Method │
│          ...                                           │
│                                                        │
│      def calculate_total(self,...):◀── Chunk 4: Method │
│          ...                                           │
│                                                        │
└────────────────────────────────────────────────────────┘

Mỗi chunk có metadata:
- file_path: "services/order.py"
- chunk_type: "method"
- name: "calculate_total"
- start_line: 15
- end_line: 25
```

### 2. Embedder - Chuyển code thành vector

**Embedding là gì?**

```
Text ──▶ Vector (mảng số)

"def calculate_total" ──▶ [0.23, -0.15, 0.87, ..., 0.42]
                          (1536 dimensions với OpenAI)
                          (768 dimensions với CodeBERT)

Tại sao?
- Computers hiểu số, không hiểu text
- Similar code → Similar vectors
- Có thể search bằng vector similarity
```

**Model options**:
| Model | Ưu điểm | Nhược điểm |
|-------|---------|------------|
| OpenAI text-embedding-3 | Chất lượng cao | Tốn tiền API |
| CodeBERT | Free, train cho code | Cần GPU |
| all-MiniLM-L6-v2 | Nhanh, nhẹ | General, không specific cho code |

### 3. Vector Database - Lưu trữ và search

**Tại sao cần Vector DB?**

```
Traditional DB: SELECT * WHERE name = "calculate_total"
                → Exact match only

Vector DB: Find vectors similar to [0.23, -0.15, ...]
           → Tìm code "tương tự" về semantic
```

**Options**:
| DB | Ưu điểm | Use case |
|----|---------|----------|
| ChromaDB | Simple, embedded | Small-medium projects |
| Pinecone | Managed, scalable | Production, large scale |
| FAISS | Facebook, very fast | Large scale, self-hosted |
| Qdrant | Full-featured | Production self-hosted |

### 4. Retriever - Tìm code liên quan

```
┌────────────────────────────────────────────────────────┐
│                    RETRIEVAL FLOW                       │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Input: PR đang review file payment.py                 │
│         Function: process_payment(order_id, amount)    │
│                                                        │
│  Step 1: Build query                                   │
│  ┌──────────────────────────────────────────────────┐ │
│  │ "payment processing, order_id, amount handling"  │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Step 2: Embed query → Vector                          │
│                                                        │
│  Step 3: Search VectorDB (top 5 similar)               │
│                                                        │
│  Step 4: Results                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 1. OrderService.complete_order() - similarity 0.9│ │
│  │ 2. test_payment.py - similarity 0.85             │ │
│  │ 3. PaymentGateway.charge() - similarity 0.82     │ │
│  │ 4. RefundService.process() - similarity 0.75     │ │
│  │ 5. docs/payment-flow.md - similarity 0.70        │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Step 5: Return context cho LLM                        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 🔄 Indexing Flow

### Khi nào cần index?

```
1. Lần đầu setup (full index)
   └──▶ Clone repo, index tất cả files

2. Khi có push mới (incremental)
   └──▶ Chỉ re-index files thay đổi

3. Scheduled (optional)
   └──▶ Re-index hàng đêm để đảm bảo fresh
```

### Index những gì?

```
┌─────────────────────────────────────────────────────────┐
│                    WHAT TO INDEX                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ✅ Index:                                               │
│     • Source code files (.py, .js, .ts, .php, ...)      │
│     • Test files (để tìm related tests)                 │
│     • Documentation (.md files)                         │
│     • Config files (package.json, pyproject.toml)       │
│                                                          │
│  ❌ Skip:                                                │
│     • node_modules/, vendor/, .venv/                    │
│     • Build outputs (dist/, build/)                     │
│     • Binary files                                      │
│     • Lock files (package-lock.json, poetry.lock)       │
│     • .git/                                             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🔍 Retrieval Strategies

### Strategy 1: Function-based Query

```
Khi review function calculate_total:

Query = "calculate_total function order pricing"
        ↑ tên function    ↑ inferred context

Tìm được:
- Các function khác cũng liên quan đến pricing
- Callers của calculate_total
- Tests cho calculate_total
```

### Strategy 2: Import-based Query

```
File đang review import những gì?

from services.order import OrderService
from utils.pricing import apply_discount

Query các modules này để hiểu context:
- OrderService làm gì?
- apply_discount hoạt động thế nào?
```

### Strategy 3: Similarity-based

```
Tìm code tương tự trong codebase:

Code đang review:
  def calculate_total(items, discount):
      return sum(i.price for i in items) * (1 - discount)

Tìm được code similar:
  def compute_subtotal(products):  # Similar pattern
      return sum(p.price for p in products)
```

---

## 💡 Kết hợp RAG + Tree-sitter

```
┌────────────────────────────────────────────────────────────────┐
│                    RAG + TREE-SITTER SYNERGY                    │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tree-sitter giúp RAG:                                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 1. Chunking chính xác hơn                                 │ │
│  │    - Chia theo function/class thay vì chia đều            │ │
│  │                                                            │ │
│  │ 2. Query chính xác hơn                                    │ │
│  │    - Biết tên function, params, types                     │ │
│  │    - Query: "calculate_total(items, discount) -> float"   │ │
│  │                                                            │ │
│  │ 3. Metadata rich hơn                                      │ │
│  │    - Lưu signature, docstring, decorators                 │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  RAG giúp Tree-sitter:                                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 1. Cross-file awareness                                   │ │
│  │    - Tree-sitter chỉ parse 1 file                         │ │
│  │    - RAG tìm relationships across files                   │ │
│  │                                                            │ │
│  │ 2. Pattern discovery                                      │ │
│  │    - Tìm similar code patterns trong repo                 │ │
│  │    - Detect conventions                                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 📊 Metrics

### Retrieval Quality Metrics

| Metric      | Mô tả                           | Target  |
| ----------- | ------------------------------- | ------- |
| Precision@K | % relevant trong top K results  | > 70%   |
| Recall      | % tìm được tất cả relevant code | > 80%   |
| Latency     | Thời gian query                 | < 500ms |

### Storage Estimates

```
Ví dụ repo 100K lines of code:
- ~2000 files
- ~5000 chunks (functions + classes)
- ~5000 * 1536 = ~7.5M floats = ~30MB vectors
- + metadata ~10MB
- Total: ~40MB per repo
```

---

## 🔜 Next: Combined Flow

Xem [04-combined-flow.md](./04-combined-flow.md) để hiểu cách RAG + Tree-sitter kết hợp trong PR review flow.
