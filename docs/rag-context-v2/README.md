# RAG Context v2: Architecture Documentation

## Overview

RAG Context v2 là hệ thống retrieval-augmented generation được thiết kế để cung cấp **context có liên quan rõ ràng** cho AI code reviewer. Khác với v1 sử dụng semantic similarity (dễ gây noise), v2 chỉ sử dụng **explicit relationships**.

## Key Principles

1. **Explicit Relationships Only** - Không có semantic similarity fallback
2. **Plugin Architecture** - Dễ dàng thêm ngôn ngữ mới
3. **Three Relationship Types**: TEST, CALLER, CALLEE

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG Context v2                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Language   │    │     AST      │    │     RAG      │      │
│  │   Plugins    │───▶│    Parser    │───▶│   Retriever  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ - Python     │    │ - ParseResult│    │ - TEST       │      │
│  │ - JavaScript │    │ - CodeChunk  │    │ - CALLER     │      │
│  │ - PHP        │    │ - imports    │    │ - CALLEE     │      │
│  └──────────────┘    │ - calls      │    └──────────────┘      │
│                      └──────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Indexing Flow (Repository Indexing)

```
Repository Clone
      │
      ▼
┌─────────────────┐
│ For each file   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Language Plugin │ ─── Detect language from extension
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   CodeParser    │ ─── Parse with tree-sitter
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────────────┐
│  ParseResult    │────▶│  - chunks: [CodeChunk]   │
└────────┬────────┘     │  - imports: [str]        │
         │              └──────────────────────────┘
         ▼
┌─────────────────┐     ┌──────────────────────────┐
│   CodeChunk     │────▶│  - name: "calculate"     │
│   (enriched)    │     │  - content: "def ..."   │
└────────┬────────┘     │  - imports: ["src.utils"]│
         │              │  - calls: ["helper"]     │
         ▼              └──────────────────────────┘
┌─────────────────┐
│    Indexer      │ ─── Store in Pinecone with metadata
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Vector Store   │ ─── Vectors + imports/calls metadata
└─────────────────┘
```

### 2. Retrieval Flow (During Review)

```
Changed Function
      │
      ▼
┌─────────────────┐
│   Retriever     │
└────────┬────────┘
         │
         ├──────────────────────────────────────────┐
         │                                          │
         ▼                                          ▼
┌─────────────────┐                      ┌─────────────────┐
│  _find_test()   │                      │ _find_callers() │
│                 │                      │                 │
│ Language plugin │                      │ Query metadata: │
│ get_test_patterns()                    │ calls.$in: [fn] │
│ ─▶ "tests/test_{name}.py"              │                 │
│ Query: file_path matches               └────────┬────────┘
└────────┬────────┘                               │
         │                                        │
         ▼                                        ▼
┌─────────────────┐                      ┌─────────────────┐
│  RelatedCode    │                      │  RelatedCode    │
│  relationship:  │                      │  relationship:  │
│  "test"         │                      │  "caller"       │
└─────────────────┘                      └─────────────────┘
         │
         │     ┌─────────────────┐
         │     │ _find_callees() │
         │     │                 │
         │     │ 1. Get fn's calls│
         │     │ 2. Find each    │
         │     │    definition   │
         │     └────────┬────────┘
         │              │
         │              ▼
         │     ┌─────────────────┐
         │     │  RelatedCode    │
         │     │  relationship:  │
         │     │  "callee"       │
         │     └─────────────────┘
         │              │
         ▼──────────────▼
┌─────────────────────────┐
│     Results List        │
│ [test, caller, callee]  │
└─────────────────────────┘
```

---

## Components

### 1. Language Plugins (`src/languages/`)

Plugin interface cho parsing ngôn ngữ-specific:

```python
class LanguagePlugin(ABC):
    @property
    def name(self) -> str: ...           # "python"
    @property
    def extensions(self) -> tuple: ...    # (".py",)
    @property
    def tree_sitter_name(self) -> str: ...
    @property
    def extract_node_types(self) -> set: ...

    def parse_imports(content: str) -> list[str]: ...
    def parse_calls(content: str) -> list[str]: ...
    def get_test_patterns(file_path: str) -> list[str]: ...
```

**Supported Languages:**

- **Python**: `import`, `from X import`, ast-based call detection
- **JavaScript/TypeScript**: ES6 imports, require, tree-sitter calls
- **PHP**: `use` statements, `require/include`, method calls

### 2. AST Parser (`src/ast/parser.py`)

Parse source code thành chunks với relationship data:

```python
@dataclass
class ParseResult:
    chunks: list[CodeChunk]
    imports: list[str]

@dataclass
class CodeChunk:
    name: str
    content: str
    chunk_type: str       # "function", "class", "method"
    file_path: str
    imports: list[str]    # File-level imports
    calls: list[str]      # Function calls in this chunk
```

### 3. Retriever (`src/rag/retriever.py`)

Tìm related code qua explicit relationships:

```python
class Retriever:
    def retrieve(owner, repo, file_path, function_name) -> list[RelatedCode]:
        # 1. Find TEST - matching test file/function
        # 2. Find CALLERS - functions that call this
        # 3. Find CALLEES - functions this calls
```

### 4. Vector Store (`src/rag/vector_store.py`)

Pinecone wrapper với metadata query support:

```python
def query_by_metadata(namespace, filter, top_k) -> list[dict]:
    # Query by metadata filter (no vector similarity)
    # Used for explicit relationship lookups
```

---

## Relationship Types

### TEST

- **Definition**: Test function/file cho source function
- **Detection**: Language-specific test patterns
- **Example**: `src/utils.py:calculate` → `tests/test_utils.py:test_calculate`

### CALLER

- **Definition**: Function gọi target function
- **Detection**: Query `calls` metadata array
- **Example**: `src/order.py:process` calls `calculate` → caller

### CALLEE

- **Definition**: Function được target function gọi
- **Detection**: Get target's `calls`, find definitions
- **Example**: `calculate` calls `validate` → callee

---

## Integration with Review Workflow

```
PR Opened
    │
    ▼
context_extractor.run()
    │
    ├─► get_code_parser()
    │       │
    │       ▼
    │   parser.get_ast_info()
    │       │
    │       ▼
    │   Identify changed functions
    │
    ├─► get_retriever()
    │       │
    │       ▼
    │   retriever.retrieve_for_function()
    │       │
    │       ▼
    │   [RelatedCode] with relationships
    │
    ▼
Review with context
```

---

## File Structure

```
src/
├── languages/                 # Language plugins
│   ├── __init__.py           # Registry
│   ├── base.py               # Plugin interface
│   ├── python.py             # Python implementation
│   ├── javascript.py         # JS/TS implementation
│   └── php.py                # PHP implementation
│
├── ast/
│   ├── models.py             # CodeChunk, RelatedCode, etc.
│   └── parser.py             # Tree-sitter parser
│
└── rag/
    ├── indexer.py            # Repository indexing
    ├── retriever.py          # Explicit relationship retrieval
    └── vector_store.py       # Pinecone wrapper
```

---

## Comparison: v1 vs v2

| Aspect               | v1 (Semantic)     | v2 (Explicit)                 |
| -------------------- | ----------------- | ----------------------------- |
| **Retrieval**        | Vector similarity | Metadata queries              |
| **Relationships**    | Inferred          | Explicit (TEST/CALLER/CALLEE) |
| **Accuracy**         | May have noise    | High precision                |
| **Context Quality**  | Variable          | Guaranteed relevance          |
| **Language Support** | Limited           | Plugin-based, extensible      |

---

## Adding New Languages

1. Create `src/languages/{language}.py`:

```python
from .base import LanguagePlugin

class GoPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "go"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".go",)

    @property
    def tree_sitter_name(self) -> str:
        return "go"

    @property
    def extract_node_types(self) -> set[str]:
        return {"function_declaration", "method_declaration"}

    def parse_imports(self, content: str) -> list[str]:
        # Parse Go imports
        ...

    def parse_calls(self, content: str) -> list[str]:
        # Parse Go function calls
        ...

    def get_test_patterns(self, file_path: str) -> list[str]:
        # Go test convention: *_test.go
        ...
```

2. Register in `src/languages/__init__.py`:

```python
from .go import GoPlugin
register(GoPlugin())
```

---

## Testing

```bash
# Unit tests
uv run pytest tests/test_languages.py -v
uv run pytest tests/test_ast_parser.py -v
uv run pytest tests/test_rag_retriever.py -v

# Integration test
uv run python -c "
from src.ast.parser import get_code_parser
parser = get_code_parser()
result = parser.parse('test.py', '''
from src.utils import helper

def calculate(x, y):
    return helper(x) + y
''')
print('Imports:', result.imports)
print('Calls:', result.chunks[0].calls)
"
# Expected:
# Imports: ['src.utils']
# Calls: ['helper']
```
