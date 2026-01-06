# 🧠 RAG Context-Aware Code Review

## 📋 Overview

Feature này sẽ enrich context cho LLM khi review code bằng cách:

1. **Tree-sitter**: Parse AST để hiểu structure của code
2. **RAG (Retrieval-Augmented Generation)**: Tìm related code từ codebase

## 🎯 Mục tiêu

| Before                         | After                                                |
| ------------------------------ | ---------------------------------------------------- |
| LLM chỉ thấy diff text         | LLM hiểu code structure (functions, classes, params) |
| Không biết context từ codebase | Biết related code, callers, tests                    |
| False positives cao            | Giảm false positives nhờ context                     |

## 📁 Documentation Structure

```
docs/ideas/rag-context/
├── README.md                    # This file
├── 01-architecture.md           # High-level architecture
├── 02-data-flow.md              # Data flow & lifecycle
├── 03-implementation-draft.md   # Draft code implementation
├── 04-integration-plan.md       # How to integrate with existing code
├── 05-data-examples.md          # Concrete examples of AST & Vector DB data
└── 06-implementation-checklist.md  # Step-by-step implementation guide
```

## 🛠️ Tech Stack

| Component      | Choice                                    | Why                                    |
| -------------- | ----------------------------------------- | -------------------------------------- |
| **Vector DB**  | Pinecone                                  | Free tier 100K vectors, managed        |
| **Embedding**  | OpenAI text-embedding-3-small (1024 dims) | Quality + supports dimension reduction |
| **AST Parser** | tree-sitter-languages                     | Pre-built, multi-language support      |
| **Git Ops**    | GitPython                                 | Clone/fetch repos                      |

## 📊 Dependencies mới

```toml
# pyproject.toml
"pinecone>=5.0.0",
"tree-sitter>=0.23.0",
"tree-sitter-languages>=1.10.0",
"gitpython>=3.1.0",
```

## ⚙️ Environment Variables mới

```bash
# .env
PINECONE_API_KEY=pcsk_xxx
PINECONE_INDEX_NAME=code-reviewer
```

## 🔗 Related Documents

- [Architecture](./01-architecture.md)
- [Data Flow](./02-data-flow.md)
- [Implementation Draft](./03-implementation-draft.md)
- [Integration Plan](./04-integration-plan.md)
- [Data Examples](./05-data-examples.md) ← Đọc file này để hiểu cụ thể data
- [Implementation Checklist](./06-implementation-checklist.md) ← ⭐ **BẮT ĐẦU TỪ ĐÂY**
