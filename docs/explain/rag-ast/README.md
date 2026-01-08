# RAG & AST Context-Aware Code Review

## Tính năng này làm gì?

Giúp AI Reviewer **hiểu code tốt hơn** bằng cách cung cấp context từ codebase:

| Không có RAG                       | Có RAG                            |
| ---------------------------------- | --------------------------------- |
| LLM chỉ thấy diff                  | LLM thấy diff + code liên quan    |
| Không biết function được gọi ở đâu | Biết callers, tests, similar code |
| Review chung chung                 | Review chính xác hơn              |

---

## Documentation

| File                                       | Nội dung                                 |
| ------------------------------------------ | ---------------------------------------- |
| [01-architecture.md](./01-architecture.md) | Kiến trúc chi tiết với diagrams          |
| [02-setup-guide.md](./02-setup-guide.md)   | **Hướng dẫn setup + test với repo thật** |

---

## Quick Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         RAG FLOW                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│    │  Codebase    │  →   │   Indexing   │  →   │  Vector DB   │ │
│    │  (GitHub)    │      │  (AST Parse) │      │  (Pinecone)  │ │
│    └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                       ↓          │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│    │   LLM gets   │  ←   │  Retrieval   │  ←   │  PR Review   │ │
│    │   context    │      │  (Query)     │      │  (diff)      │ │
│    └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cách sử dụng

### Bước 1: Cấu hình

```bash
# Thêm vào .env
PINECONE_API_KEY=pcsk_xxx   # Lấy từ pinecone.io (free)
PINECONE_INDEX_NAME=code-reviewer
```

### Bước 2: Cài GitHub App

Khi cài App vào repo → Tự động index toàn bộ codebase

### Bước 3: Tạo PR

Khi review PR → LLM nhận được:

- Diff của file
- Related code từ codebase (tests, callers, similar functions)

---

## Supported Languages

Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, Scala, PHP, Ruby, C, C++, Swift

---

## File Structure

```
src/
├── ast/                    # Parse code → chunks
│   ├── models.py          # CodeChunk, ASTInfo, RelatedCode
│   └── parser.py          # Tree-sitter wrapper
│
├── rag/                    # Vector DB operations
│   ├── config.py          # Settings
│   ├── embedder.py        # OpenAI embeddings
│   ├── vector_store.py    # Pinecone CRUD
│   ├── chunker.py         # Filter + parse files
│   ├── indexer.py         # Full/incremental indexing
│   └── retriever.py       # Query similar code
│
└── integration points:
    ├── webhooks.py        # Handle installation events
    ├── tasks.py           # Celery tasks for indexing
    └── context_extractor.py # Enrich PR files with RAG
```

---

## Chi tiết

Đọc [01-architecture.md](./01-architecture.md) để hiểu luồng hoạt động.

Đọc [02-setup-guide.md](./02-setup-guide.md) để test với repo thật.
