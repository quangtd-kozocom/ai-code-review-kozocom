# 05. Implementation Roadmap

## 🗺️ Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION PHASES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Phase 1          Phase 2          Phase 3          Phase 4                │
│   TREE-SITTER      RAG SYSTEM       INTEGRATION      OPTIMIZATION           │
│   ──────────►      ──────────►      ──────────►      ──────────►            │
│                                                                              │
│   • Parser         • Chunker        • Update         • Performance          │
│   • Extractors     • Embedder         context_       • Caching              │
│   • Models         • VectorDB         extractor      • Monitoring           │
│                    • Retriever      • Update         • Fine-tuning          │
│                    • Indexer          prompts                               │
│                                                                              │
│   ~1 week          ~1-2 weeks       ~1 week          Ongoing                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Phase 1: Tree-sitter

### Goals

- Parse source code thành AST
- Extract semantic information (functions, classes, imports, calls)
- Support Python trước, mở rộng sau

### Directory Structure

```
src/ast/
├── __init__.py
├── parser.py           # Tree-sitter wrapper
├── models.py           # Data models
└── extractors/
    ├── __init__.py     # Factory
    ├── base.py         # Base class
    └── python.py       # Python extractor
```

### Dependencies

```toml
# pyproject.toml
[project.dependencies]
tree-sitter = "^0.22.0"
tree-sitter-python = "^0.22.0"
tree-sitter-javascript = "^0.22.0"  # Optional, later
```

### Key Tasks

| Task                | Priority | Notes                                      |
| ------------------- | -------- | ------------------------------------------ |
| Setup Tree-sitter   | High     | Install, configure parsers                 |
| Define models       | High     | Symbol, FunctionCall, Import, FileAST      |
| Python extractor    | High     | Extract functions, classes, imports, calls |
| Test with real code | Medium   | Verify extraction accuracy                 |
| JS/TS extractor     | Low      | After Python works                         |

---

## 📦 Phase 2: RAG System

### Goals

- Index codebase vào vector database
- Retrieve related code cho mỗi PR
- Support incremental updates

### Directory Structure

```
src/rag/
├── __init__.py
├── chunker.py          # Code chunking (by function/class)
├── embedder.py         # Text → Vector
├── vector_store.py     # ChromaDB wrapper
├── retriever.py        # Query và retrieve
└── indexer.py          # Full & incremental indexing
```

### Dependencies

```toml
# pyproject.toml
[project.dependencies]
chromadb = "^0.4.0"
sentence-transformers = "^2.2.0"

# Hoặc dùng OpenAI embeddings:
# openai = "^1.0.0"  (đã có trong project)
```

### Key Tasks

| Task                   | Priority | Notes                                  |
| ---------------------- | -------- | -------------------------------------- |
| Setup ChromaDB         | High     | Embedded mode, persist to disk         |
| Implement chunker      | High     | Use Tree-sitter for smart chunking     |
| Implement embedder     | High     | Dùng OpenAI hoặc sentence-transformers |
| Implement retriever    | High     | Query similar code                     |
| Implement indexer      | Medium   | Full & incremental indexing            |
| Test retrieval quality | Medium   | Verify relevant results                |

### Chunking Strategy

```
Option A: Use Tree-sitter (Recommended)
├── Chunk = 1 function/class
├── Accurate boundaries
└── Rich metadata

Option B: Fixed size chunks
├── Chunk = N lines
├── Simple but may split functions
└── Less accurate
```

### Embedding Options

```
Option A: OpenAI (Recommended for quality)
├── text-embedding-3-small: $0.02/1M tokens
├── Highest quality
└── Cần API call

Option B: Local (Recommended for cost)
├── all-MiniLM-L6-v2: Free, fast
├── codeBERT: Better for code
└── No API needed
```

---

## 📦 Phase 3: Integration

### Goals

- Update `context_extractor` to use Tree-sitter + RAG
- Update agent prompts to use enhanced context
- Minimal changes to existing flow

### Files to Modify

```
src/agents/
├── nodes/
│   └── context_extractor.py    # MAJOR CHANGES
│       ├── Add: fetch full file content
│       ├── Add: Tree-sitter parsing
│       └── Add: RAG retrieval
│
├── prompts/
│   ├── logic.py                # ADD: context sections
│   ├── security.py             # ADD: context sections
│   └── style.py                # ADD: context sections
│
└── state.py                    # ADD: EnhancedFileChange model
```

### Updated State Model

```
GraphState:
  files: list[FileChange]        # Current
         ↓
  files: list[EnhancedFileChange]  # New

EnhancedFileChange = FileChange + {
  ast_info: FileAST           # From Tree-sitter
  related_context: Context     # From RAG
}
```

### Updated Prompt Structure

```
Current:
├── File info
├── Diff
└── Instructions

Enhanced:
├── File info
├── Diff
├── AST Context (NEW)
│   ├── Changed functions
│   ├── Function signatures
│   └── Imports
├── Codebase Context (NEW)
│   ├── Callers
│   ├── Similar code
│   └── Related tests
└── Instructions
```

---

## 📦 Phase 4: Optimization

### Performance

```
Concerns:
├── Tree-sitter parsing: ~10-50ms per file ✓ Fast
├── RAG query: ~200-500ms per query
├── Full file fetch: ~100-200ms per file
└── Total added latency: ~500-1000ms per file

Optimizations:
├── Parallel processing (already doing)
├── Cache parsed AST
├── Batch RAG queries
└── Limit context size
```

### Caching Strategy

```
Level 1: In-memory (per review)
├── Parsed AST for files
└── RAG results

Level 2: Persistent (across reviews)
├── Vector embeddings (ChromaDB)
└── File content hashes
```

### Monitoring

```
Metrics to track:
├── Retrieval latency
├── Retrieval quality (precision@k)
├── False positive rate change
├── Review quality scores
└── Token usage (if using OpenAI embeddings)
```

---

## 📋 Implementation Checklist

### Week 1: Tree-sitter

- [ ] Install tree-sitter dependencies
- [ ] Create `src/ast/` directory structure
- [ ] Implement `models.py`
- [ ] Implement `parser.py`
- [ ] Implement Python extractor
- [ ] Write tests for extraction

### Week 2: RAG Core

- [ ] Setup ChromaDB
- [ ] Implement `chunker.py` (using Tree-sitter)
- [ ] Implement `embedder.py`
- [ ] Implement `vector_store.py`
- [ ] Implement `retriever.py`

### Week 3: RAG + Integration

- [ ] Implement `indexer.py`
- [ ] Create indexing script/command
- [ ] Update `context_extractor.py`
- [ ] Update `state.py` with new models
- [ ] Update prompts

### Week 4: Testing & Polish

- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Documentation
- [ ] Monitoring setup

---

## 🔧 Quick Start Commands

```bash
# Install dependencies
pip install tree-sitter tree-sitter-python chromadb sentence-transformers

# Or add to pyproject.toml and:
pip install -e ".[dev]"
```

---

## 💡 Tips

### Start Small

```
1. Implement Tree-sitter cho Python trước
2. Test với 1-2 files
3. Sau đó mới add RAG
4. Sau đó mới integrate
```

### Validate Each Step

```
1. Tree-sitter: Verify AST extraction accuracy
2. Chunker: Check chunk quality
3. Embedder: Check similarity makes sense
4. Retriever: Check relevant results
5. Integration: Compare review quality
```

### Fallback Strategy

```
If Tree-sitter fails → Use file without AST info
If RAG fails → Use file without related context
→ System vẫn hoạt động, chỉ less context
```

---

## 📚 Resources

### Tree-sitter

- [Tree-sitter docs](https://tree-sitter.github.io/tree-sitter/)
- [py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter)

### RAG

- [ChromaDB docs](https://docs.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)

### Code Intelligence

- [CodeBERT](https://huggingface.co/microsoft/codebert-base)
- [CodeRabbit blog](https://www.coderabbit.ai/blog) - Inspiration
