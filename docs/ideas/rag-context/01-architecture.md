# 01. Architecture

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RAG-ENHANCED REVIEW SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  LAYER 1: INDEXING (Background - On Installation & After Merge)       ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                        ║  │
│  ║   GitHub ──▶ GitPython ──▶ Tree-sitter ──▶ OpenAI ──▶ Pinecone       ║  │
│  ║   (clone)    (files)       (parse AST)     (embed)    (store)         ║  │
│  ║                                                                        ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  LAYER 2: RETRIEVAL (Per PR Review)                                   ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                        ║  │
│  ║   PR Diff ──▶ Tree-sitter ──▶ OpenAI ──▶ Pinecone ──▶ Context        ║  │
│  ║              (extract names)  (embed)    (search)     (for LLM)       ║  │
│  ║                                                                        ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  LAYER 3: REVIEW (Existing - Enhanced with Context)                   ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                        ║  │
│  ║   EnhancedContext ──▶ Security Agent ──▶                              ║  │
│  ║   (diff + AST +       ──▶ Logic Agent   ──▶ Aggregator ──▶ GitHub    ║  │
│  ║    RAG context)       ──▶ Style Agent   ──▶                           ║  │
│  ║                                                                        ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 New Directory Structure

```
src/
├── agents/                      # Existing - sẽ modify prompts
│   ├── nodes/
│   │   └── context_extractor.py # MODIFY: Thêm RAG context
│   └── prompts/
│       └── *.py                 # MODIFY: Thêm context sections
│
├── rag/                         # NEW MODULE
│   ├── __init__.py
│   ├── config.py                # RAG configuration
│   ├── embedder.py              # OpenAI embedding wrapper
│   ├── vector_store.py          # Pinecone wrapper
│   ├── chunker.py               # Code chunking logic
│   ├── indexer.py               # Indexing orchestrator
│   └── retriever.py             # Context retrieval
│
├── ast/                         # NEW MODULE
│   ├── __init__.py
│   ├── parser.py                # Tree-sitter wrapper
│   ├── models.py                # AST data models
│   └── extractors/
│       ├── __init__.py
│       ├── base.py              # Base extractor
│       ├── python.py            # Python-specific
│       ├── javascript.py        # JS/TS-specific
│       └── php.py               # PHP-specific
│
└── workers/
    └── tasks.py                 # MODIFY: Thêm indexing tasks
```

---

## 🔄 Component Responsibilities

### 1. AST Module (`src/ast/`)

**Mục đích**: Parse code thành structured data

```
Input:  Raw source code (string)
Output: List[CodeChunk] với metadata

CodeChunk:
- type: "function" | "class" | "method" | "import"
- name: "calculate_total"
- signature: "def calculate_total(items: list, discount: float = 0) -> float"
- content: Full code của chunk
- start_line, end_line
- docstring (nếu có)
- dependencies: ["OrderService", "apply_discount"]  # imports/calls
```

**Tại sao cần module riêng?**

- Tree-sitter syntax khác nhau per language
- Cần abstract away language-specific logic
- Có thể extend thêm languages dễ dàng

### 2. RAG Module (`src/rag/`)

**Mục đích**: Index và retrieve related code

**Sub-components:**

| Component         | Responsibility                              |
| ----------------- | ------------------------------------------- |
| `embedder.py`     | Wrap OpenAI embeddings API                  |
| `chunker.py`      | Orchestrate AST → chunks với smart chunking |
| `vector_store.py` | Wrap Pinecone operations                    |
| `indexer.py`      | Orchestrate full indexing flow              |
| `retriever.py`    | Query Pinecone và format context            |

**Tại sao tách riêng modules?**

- Single Responsibility Principle
- Dễ test từng component
- Có thể swap implementation (e.g., đổi Pinecone → Qdrant)

### 3. Modified Existing Components

**`context_extractor.py` (existing)**

```python
# Before
async def extract(pr_data) -> list[FileChange]:
    return [FileChange(filename, patch)]

# After
async def extract(pr_data) -> list[EnhancedFileChange]:
    return [EnhancedFileChange(
        filename=filename,
        patch=patch,
        ast_info=ast_parser.parse(content),      # NEW
        related_context=retriever.retrieve(...)   # NEW
    )]
```

---

## 🗃️ Data Models

### CodeChunk (AST output)

```python
@dataclass
class CodeChunk:
    """Represents a parseable unit of code"""
    chunk_type: Literal["function", "class", "method", "import", "module"]
    name: str
    signature: str | None          # For functions/methods
    content: str                   # Full source code
    file_path: str
    start_line: int
    end_line: int
    docstring: str | None
    dependencies: list[str]        # Imported/called names
    language: str                  # "python", "javascript", etc.
```

### VectorRecord (Pinecone storage)

```python
@dataclass
class VectorRecord:
    """What we store in Pinecone"""
    id: str                        # "owner/repo:path/file.py:function_name"
    embedding: list[float]         # 1024 dimensions
    metadata: dict                 # chunk_type, name, content, file_path, etc.
```

### EnhancedFileChange (Review input)

```python
@dataclass
class EnhancedFileChange:
    """Enhanced file change with context"""
    filename: str
    patch: str                     # Original diff
    full_content: str | None       # Full file content (for new files)

    # NEW: AST info
    ast_info: ASTInfo | None

    # NEW: RAG context
    related_context: list[RelatedCode]

@dataclass
class ASTInfo:
    """Parsed AST information"""
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[str]
    changed_entities: list[str]    # Names of changed functions/classes

@dataclass
class RelatedCode:
    """Related code from RAG"""
    file_path: str
    name: str
    content: str
    relevance_score: float
    relationship: str              # "caller", "callee", "similar", "test"
```

---

## 🔐 Pinecone Namespace Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PINECONE INDEX STRUCTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Index: "code-reviewer" (single index for all)                              │
│                                                                              │
│  ├── Namespace: "github/octocat/hello-world"                                │
│  │   └── Vectors for this repo                                              │
│  │                                                                           │
│  ├── Namespace: "github/acme/backend-api"                                   │
│  │   └── Vectors for this repo                                              │
│  │                                                                           │
│  └── Namespace: "github/acme/frontend-app"                                  │
│      └── Vectors for this repo                                              │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│  Benefits:                                                                   │
│  • Isolation: Queries only search within repo namespace                     │
│  • Cleanup: Delete namespace = delete all repo vectors                      │
│  • Free tier: 100K vectors shared across all namespaces                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Design Decisions & Trade-offs

### Decision 1: Single Pinecone Index vs Multiple

**Chọn: Single Index với Namespaces**

| Option              | Pros                 | Cons                              |
| ------------------- | -------------------- | --------------------------------- |
| Multiple indexes    | Full isolation       | Pinecone free tier = 1 index only |
| Single + namespaces | Works with free tier | Shared capacity                   |

### Decision 2: Embedding Dimension 1024 vs 1536

**Chọn: 1024 dimensions**

- Pinecone free tier limit
- OpenAI supports dimension reduction
- Minimal quality loss

### Decision 3: Index Timing

**Chọn: On Installation + After Merge**

| Trigger                        | What happens                |
| ------------------------------ | --------------------------- |
| `installation.created`         | Full index của tất cả repos |
| `pull_request.closed` (merged) | Incremental update          |

### Decision 4: Clone Strategy

**Chọn: Shallow clone với depth=1**

```bash
git clone --depth 1 --branch main https://github.com/owner/repo.git
```

- Nhanh hơn nhiều so với full clone
- Đủ để index current state
- Không cần history

---

## 🔜 Next: Data Flow

Xem [02-data-flow.md](./02-data-flow.md) để hiểu chi tiết các flows.
