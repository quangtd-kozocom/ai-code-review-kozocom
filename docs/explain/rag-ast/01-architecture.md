# 01. Kiến Trúc RAG Context-Aware Code Review

## Vấn Đề Cần Giải Quyết

Khi review code, LLM chỉ nhìn thấy **diff của file đang thay đổi**. Nó không biết:

- Function này được gọi ở đâu?
- Có test nào cover function này không?
- Có code tương tự trong codebase không?

**RAG (Retrieval-Augmented Generation)** giải quyết vấn đề này bằng cách:

1. **Index toàn bộ codebase** → lưu vào vector database
2. **Khi review PR** → tìm code liên quan → đưa vào context cho LLM

---

## Luồng Hoạt Động

### Giai đoạn 1: Indexing (Khi cài đặt GitHub App)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INDEXING FLOW                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. User cài GitHub App vào repo                                    │
│           ↓                                                          │
│  2. GitHub gửi webhook: installation.created                        │
│           ↓                                                          │
│  3. Server nhận webhook → queue Celery task                         │
│           ↓                                                          │
│  4. Celery worker chạy task index_installation:                     │
│           │                                                          │
│           ├── git clone --depth 1 (vào thư mục tạm)                 │
│           │                                                          │
│           ├── Duyệt tất cả file code (.py, .js, .ts, ...)           │
│           │                                                          │
│           ├── Parse AST từng file:                                  │
│           │   ┌─────────────────────────────────────────┐           │
│           │   │ def calculate_total(items):             │           │
│           │   │     return sum(i.price for i in items)  │           │
│           │   └─────────────────────────────────────────┘           │
│           │                    ↓                                     │
│           │   ┌─────────────────────────────────────────┐           │
│           │   │ CodeChunk:                              │           │
│           │   │   name: "calculate_total"               │           │
│           │   │   type: "function"                      │           │
│           │   │   file: "src/utils.py"                  │           │
│           │   │   lines: 10-12                          │           │
│           │   │   signature: "def calculate_total(...)" │           │
│           │   └─────────────────────────────────────────┘           │
│           │                                                          │
│           ├── Gọi OpenAI để tạo embedding (vector 1024 chiều)       │
│           │                                                          │
│           └── Lưu vào Pinecone (namespace = owner/repo)             │
│                                                                      │
│  5. Xoá thư mục tạm                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Giai đoạn 2: Retrieval (Khi Review PR)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RETRIEVAL FLOW                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. PR opened → webhook → review_pr task                            │
│           ↓                                                          │
│  2. Context Extractor nhận danh sách files changed:                 │
│     - src/order.py (modified)                                       │
│     - tests/test_order.py (added)                                   │
│           ↓                                                          │
│  3. Với mỗi file modified:                                          │
│           │                                                          │
│           ├── Fetch nội dung file từ GitHub                         │
│           │                                                          │
│           ├── Parse AST → tìm functions bị thay đổi                 │
│           │   (dựa vào line numbers trong diff)                     │
│           │                                                          │
│           ├── Với mỗi function thay đổi, query Pinecone:            │
│           │   "Tìm code giống với function calculate_total"          │
│           │                    ↓                                     │
│           │   Pinecone trả về top 5 chunks giống nhất:              │
│           │   ┌─────────────────────────────────────────┐           │
│           │   │ 1. tests/test_utils.py:test_calculate   │ (0.92)    │
│           │   │ 2. src/billing.py:compute_total         │ (0.85)    │
│           │   │ 3. src/cart.py:get_total                │ (0.80)    │
│           │   └─────────────────────────────────────────┘           │
│           │                                                          │
│           └── Gắn related_context vào file                          │
│                                                                      │
│  4. Agents nhận files với context bổ sung:                          │
│     - File diff                                                      │
│     - Related code từ codebase                                      │
│           ↓                                                          │
│  5. LLM review với đầy đủ context                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Giai đoạn 3: Incremental Update (Khi PR Merged)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INCREMENTAL UPDATE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. PR merged → webhook: pull_request.closed (merged=true)          │
│           ↓                                                          │
│  2. update_rag_index task:                                          │
│           │                                                          │
│           ├── File added → Parse + Embed + Upsert                   │
│           │                                                          │
│           ├── File modified → Delete old + Add new                  │
│           │                                                          │
│           └── File removed → Delete vectors                         │
│                                                                      │
│  3. Index luôn đồng bộ với code trên main branch                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components Chi Tiết

### 1. AST Parser (`src/ast/`)

**Mục đích:** Parse code thành các đơn vị có nghĩa (functions, classes)

```
┌──────────────────────────────────────────────────────────────────┐
│                     AST PARSER                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  INPUT: File path + Content                                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ # src/utils.py                                              │ │
│  │                                                             │ │
│  │ import math                                                 │ │
│  │                                                             │ │
│  │ class Calculator:                                           │ │
│  │     def add(self, a, b):                                    │ │
│  │         return a + b                                        │ │
│  │                                                             │ │
│  │ def multiply(x, y):                                         │ │
│  │     return x * y                                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                           │                                       │
│                           ↓                                       │
│                    Tree-sitter Parse                              │
│                           │                                       │
│                           ↓                                       │
│  OUTPUT: List of CodeChunks                                      │
│                                                                   │
│  ┌────────────────────────┐  ┌────────────────────────┐         │
│  │ CodeChunk #1           │  │ CodeChunk #2           │         │
│  │ type: "class"          │  │ type: "function"       │         │
│  │ name: "Calculator"     │  │ name: "multiply"       │         │
│  │ lines: 5-7             │  │ lines: 9-10            │         │
│  └────────────────────────┘  └────────────────────────┘         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Ngôn ngữ hỗ trợ:** Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, Scala, PHP, Ruby, C, C++, Swift

---

### 2. Embedder (`src/rag/embedder.py`)

**Mục đích:** Chuyển code thành vector số để so sánh

```
┌──────────────────────────────────────────────────────────────────┐
│                       EMBEDDER                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  INPUT: Code text                                                │
│  "function: calculate_total                                      │
│   Signature: def calculate_total(items):                         │
│   Code: return sum(i.price for i in items)"                      │
│                           │                                       │
│                           ↓                                       │
│                    OpenAI API                                     │
│              (text-embedding-3-small)                             │
│                           │                                       │
│                           ↓                                       │
│  OUTPUT: Vector [0.023, -0.156, 0.089, ..., 0.042]               │
│                    (1024 dimensions)                              │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│  Tại sao dùng vector?                                            │
│                                                                   │
│  Code giống nhau → Vector gần nhau                               │
│  Code khác nhau → Vector xa nhau                                 │
│                                                                   │
│  Ví dụ:                                                          │
│  "calculate_total" ≈ "compute_sum" (cosine similarity: 0.85)     │
│  "calculate_total" ≠ "parse_json" (cosine similarity: 0.15)      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 3. Vector Store (`src/rag/vector_store.py`)

**Mục đích:** Lưu trữ và tìm kiếm vectors

```
┌──────────────────────────────────────────────────────────────────┐
│                    PINECONE VECTOR DATABASE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Index: "code-reviewer"                                          │
│  │                                                                │
│  ├── Namespace: "mycompany/backend"                              │
│  │   ├── Vector ID: "src/utils.py:calculate:10"                  │
│  │   │   ├── values: [0.023, -0.156, ...]                        │
│  │   │   └── metadata: {file, name, type, content}               │
│  │   │                                                            │
│  │   ├── Vector ID: "src/order.py:process:25"                    │
│  │   └── ...                                                      │
│  │                                                                │
│  ├── Namespace: "mycompany/frontend"                             │
│  │   └── ...                                                      │
│  │                                                                │
│  └── Namespace: "otherorg/project"                               │
│      └── ...                                                      │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  Query: "Find similar to calculate_total"                        │
│           │                                                       │
│           ↓                                                       │
│  1. Embed query → vector                                         │
│  2. Search namespace "mycompany/backend"                         │
│  3. Return top K nearest neighbors                               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 4. Chunker (`src/rag/chunker.py`)

**Mục đích:** Quyết định file nào cần xử lý, phát hiện secrets

```
┌──────────────────────────────────────────────────────────────────┐
│                        CHUNKER                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  File Filtering:                                                 │
│  ───────────────                                                 │
│  ✓ src/main.py           → Process (Python file)                │
│  ✓ lib/utils.ts          → Process (TypeScript)                 │
│  ✗ node_modules/foo.js   → Skip (dependencies)                  │
│  ✗ package-lock.json     → Skip (lock file)                     │
│  ✗ image.png             → Skip (binary)                        │
│  ✗ .env                  → Skip (secrets)                       │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  Secret Detection:                                               │
│  ─────────────────                                               │
│  Scan content for patterns:                                      │
│  • API_KEY = "sk-xxxxx"     → SKIP FILE                          │
│  • password = "secret123"   → SKIP FILE                          │
│  • -----BEGIN PRIVATE KEY   → SKIP FILE                          │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  Fallback:                                                       │
│  ─────────                                                       │
│  Nếu AST parse thất bại → Lấy toàn bộ file làm 1 chunk          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 5. Retriever (`src/rag/retriever.py`)

**Mục đích:** Tìm code liên quan và phân loại relationship

```
┌──────────────────────────────────────────────────────────────────┐
│                       RETRIEVER                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  INPUT: Function đang review                                     │
│  "calculate_total" từ file "src/order.py"                        │
│                           │                                       │
│                           ↓                                       │
│  Query Pinecone (exclude current file)                           │
│                           │                                       │
│                           ↓                                       │
│  OUTPUT: Related code with relationship                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ RelatedCode #1                                              │ │
│  │   file: "tests/test_order.py"                               │ │
│  │   name: "test_calculate_total"                              │ │
│  │   relationship: "test"       ← Vì path chứa "test"          │ │
│  │   score: 0.92                                               │ │
│  │   content: "def test_calculate_total(): ..."                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ RelatedCode #2                                              │ │
│  │   file: "src/billing.py"                                    │ │
│  │   name: "compute_total"                                     │ │
│  │   relationship: "similar"    ← Logic tương tự               │ │
│  │   score: 0.85                                               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Relationship Types:                                             │
│  • "test"   - File test cho function này                        │
│  • "callee" - Function đang được gọi                            │
│  • "similar"- Code có logic tương tự                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tổng Kết Module

```
┌─────────────────────────────────────────────────────────────────┐
│   src/ast/         │  src/rag/         │  Integration          │
├────────────────────┼───────────────────┼───────────────────────┤
│                    │                   │                       │
│  models.py         │  config.py        │  webhooks.py          │
│  ├─ CodeChunk      │  ├─ RAGSettings   │  ├─ installation.*    │
│  ├─ ASTInfo        │  ├─ INCLUDE_EXT   │  └─ PR merge handler  │
│  └─ RelatedCode    │  └─ EXCLUDE_PAT   │                       │
│                    │                   │  tasks.py              │
│  parser.py         │  embedder.py      │  ├─ index_install     │
│  └─ CodeParser     │  └─ OpenAI wrap   │  └─ update_rag_index  │
│                    │                   │                       │
│                    │  vector_store.py  │  context_extractor.py │
│                    │  └─ Pinecone ops  │  └─ _enrich_files     │
│                    │                   │                       │
│                    │  chunker.py       │  state.py             │
│                    │  └─ Filter+Parse  │  └─ EnhancedFileChange│
│                    │                   │                       │
│                    │  indexer.py       │                       │
│                    │  └─ Full/Increm.  │                       │
│                    │                   │                       │
│                    │  retriever.py     │                       │
│                    │  └─ Query+Rank    │                       │
│                    │                   │                       │
└────────────────────┴───────────────────┴───────────────────────┘
```
