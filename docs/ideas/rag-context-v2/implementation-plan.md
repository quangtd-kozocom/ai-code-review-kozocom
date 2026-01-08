# RAG Context v2: Implementation Plan

## Objective

Implement a quality-first RAG system that provides **explicitly related code** to LLM during code review.

## Key Principles

1. **Explicit relationships only** - No semantic "similarity" fallback
2. **Plugin architecture** - Easy to add new languages
3. **Three relationship types**: TEST, CALLER, CALLEE

---

## Current State

The project has existing RAG code in:

- `src/ast/` - AST parsing with tree-sitter
- `src/rag/` - Vector store, indexer, retriever
- `src/core/constants.py` - Language mappings

**Problem:** Current implementation uses semantic similarity which produces noise.

---

## Target Architecture

```
src/
├── languages/                 # NEW: Language plugins
│   ├── __init__.py           # Registry
│   ├── base.py               # Plugin interface
│   ├── python.py             # Python implementation
│   ├── javascript.py         # JS/TS implementation
│   └── php.py                # PHP implementation
│
├── ast/                       # REFACTOR
│   ├── models.py             # Add imports, calls fields
│   └── parser.py             # Use language plugins
│
└── rag/                       # REFACTOR
    ├── retriever.py          # Smart retrieval (TEST/CALLER/CALLEE)
    └── indexer.py            # Store imports/calls metadata
```

---

## Implementation Tasks

### Task 1: Create Language Plugin System

**Files to create:**

#### 1.1 `src/languages/base.py`

```python
"""Language plugin interface."""

from abc import ABC, abstractmethod


class LanguagePlugin(ABC):
    """Base class for language-specific parsing."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Language name: 'python', 'javascript', 'php'."""
        ...

    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        """File extensions: ('.py',) or ('.js', '.jsx', '.ts', '.tsx')."""
        ...

    @property
    @abstractmethod
    def tree_sitter_name(self) -> str:
        """Tree-sitter grammar name."""
        ...

    @property
    @abstractmethod
    def extract_node_types(self) -> set[str]:
        """AST node types to extract as chunks."""
        ...

    @abstractmethod
    def parse_imports(self, content: str) -> list[str]:
        """Extract imported modules/files from source code."""
        ...

    @abstractmethod
    def parse_calls(self, content: str) -> list[str]:
        """Extract function/method calls from source code."""
        ...

    @abstractmethod
    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate possible test file paths for a source file."""
        ...

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract function signature from AST node. Optional override."""
        return None

    def extract_docstring(self, node, content_bytes: bytes) -> str | None:
        """Extract docstring from AST node. Optional override."""
        return None
```

#### 1.2 `src/languages/__init__.py`

```python
"""Language plugin registry."""

from pathlib import Path

from .base import LanguagePlugin

_PLUGINS: dict[str, LanguagePlugin] = {}
_EXT_MAP: dict[str, str] = {}


def register(plugin: LanguagePlugin) -> None:
    """Register a language plugin."""
    _PLUGINS[plugin.name] = plugin
    for ext in plugin.extensions:
        _EXT_MAP[ext] = plugin.name


def get_plugin(language: str) -> LanguagePlugin | None:
    """Get plugin by language name."""
    return _PLUGINS.get(language)


def get_plugin_for_file(file_path: str) -> LanguagePlugin | None:
    """Get plugin for file based on extension."""
    ext = Path(file_path).suffix.lower()
    lang = _EXT_MAP.get(ext)
    return _PLUGINS.get(lang) if lang else None


def get_supported_extensions() -> frozenset[str]:
    """Get all supported file extensions."""
    return frozenset(_EXT_MAP.keys())


# Import and register plugins
from .python import PythonPlugin
from .javascript import JavaScriptPlugin
from .php import PHPPlugin

register(PythonPlugin())
register(JavaScriptPlugin())
register(PHPPlugin())
```

---

### Task 2: Implement Python Plugin

**File:** `src/languages/python.py`

```python
"""Python language plugin."""

import ast
import re
from pathlib import Path

from .base import LanguagePlugin


class PythonPlugin(LanguagePlugin):

    @property
    def name(self) -> str:
        return "python"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".py",)

    @property
    def tree_sitter_name(self) -> str:
        return "python"

    @property
    def extract_node_types(self) -> set[str]:
        return {"function_definition", "class_definition"}

    def parse_imports(self, content: str) -> list[str]:
        """Parse Python imports.

        Handles:
        - import os
        - import os, sys
        - from typing import List
        - from src.utils import helper
        - from .models import User (relative)
        """
        imports = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                continue
            if line.startswith("import "):
                parts = line[7:].split(",")
                for part in parts:
                    module = part.strip().split()[0].split(".")[0]
                    if module:
                        imports.append(module)
            elif line.startswith("from "):
                match = re.match(r"from\s+([\w.]+)\s+import", line)
                if match:
                    imports.append(match.group(1))
        return list(set(imports))

    def parse_calls(self, content: str) -> list[str]:
        """Parse Python function calls using ast module."""
        calls = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.append(node.func.attr)
        except SyntaxError:
            pass

        builtins = {"print", "len", "range", "str", "int", "float", "list", "dict", "set", "tuple", "open", "type"}
        return [c for c in set(calls) if c not in builtins]

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns for Python."""
        path = Path(file_path)
        stem = path.stem
        parent = str(path.parent)
        return [
            f"tests/test_{stem}.py",
            f"tests/{parent}/test_{stem}.py",
            f"test_{stem}.py",
            f"{parent}/test_{stem}.py",
        ]

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract first line as signature."""
        text = content_bytes[node.start_byte:node.end_byte].decode()
        first_line = text.split("\n")[0].strip()
        return first_line if first_line else None

    def extract_docstring(self, node, content_bytes: bytes) -> str | None:
        """Extract docstring from function/class."""
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "string":
                                text = expr.text.decode()
                                return text.strip("\"'").strip()
                break
        return None
```

---

### Task 3: Implement JavaScript/TypeScript Plugin

**File:** `src/languages/javascript.py`

```python
"""JavaScript/TypeScript language plugin."""

import re
from pathlib import Path

import tree_sitter_language_pack as ts_pack

from .base import LanguagePlugin


class JavaScriptPlugin(LanguagePlugin):

    @property
    def name(self) -> str:
        return "javascript"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".js", ".jsx", ".ts", ".tsx")

    @property
    def tree_sitter_name(self) -> str:
        return "javascript"  # Works for basic parsing

    @property
    def extract_node_types(self) -> set[str]:
        return {"function_declaration", "class_declaration", "arrow_function", "method_definition"}

    def parse_imports(self, content: str) -> list[str]:
        """Parse JS/TS imports.

        Handles:
        - import { foo } from './utils'
        - import * as lib from 'library'
        - import foo from './bar'
        - const x = require('./helper')
        - import type { X } from './types'
        """
        imports = []
        patterns = [
            r"import\s+(?:type\s+)?(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
            r"import\s*\(\s*['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, content))
        return list(set(imports))

    def parse_calls(self, content: str) -> list[str]:
        """Parse JS/TS function calls."""
        calls = []
        try:
            parser = ts_pack.get_parser("javascript")
            tree = parser.parse(content.encode())

            def walk(node):
                if node.type == "call_expression":
                    func = node.child_by_field_name("function")
                    if func:
                        if func.type == "identifier":
                            calls.append(func.text.decode())
                        elif func.type == "member_expression":
                            prop = func.child_by_field_name("property")
                            if prop:
                                calls.append(prop.text.decode())
                for child in node.children:
                    walk(child)

            walk(tree.root_node)
        except Exception:
            pattern = r"(\w+)\s*\("
            calls = re.findall(pattern, content)

        noise = {"console", "log", "error", "warn", "require", "import", "parseInt", "parseFloat"}
        return [c for c in set(calls) if c not in noise]

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns for JS/TS."""
        path = Path(file_path)
        stem = path.stem
        ext = path.suffix
        return [
            f"__tests__/{stem}.test{ext}",
            f"__tests__/{stem}.spec{ext}",
            f"{stem}.test{ext}",
            f"{stem}.spec{ext}",
            f"tests/{stem}.test{ext}",
            f"test/{stem}.test{ext}",
        ]
```

---

### Task 4: Implement PHP Plugin

**File:** `src/languages/php.py`

```python
"""PHP language plugin."""

import re
from pathlib import Path

from .base import LanguagePlugin


class PHPPlugin(LanguagePlugin):

    @property
    def name(self) -> str:
        return "php"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".php",)

    @property
    def tree_sitter_name(self) -> str:
        return "php"

    @property
    def extract_node_types(self) -> set[str]:
        return {"function_definition", "class_declaration", "method_declaration"}

    def parse_imports(self, content: str) -> list[str]:
        """Parse PHP imports.

        Handles:
        - use App\\Models\\User;
        - use App\\Services\\OrderService as Service;
        - require_once 'helper.php';
        - include 'config.php';
        """
        imports = []
        patterns = [
            r"use\s+([\w\\\\]+)(?:\s+as\s+\w+)?;",
            r"(?:require|include)(?:_once)?\s*\(?['\"]([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, content))

        # Normalize PHP namespaces: App\\Models\\User → App/Models/User
        normalized = [imp.replace("\\\\", "/").replace("\\", "/") for imp in imports]
        return list(set(normalized))

    def parse_calls(self, content: str) -> list[str]:
        """Parse PHP function/method calls."""
        calls = []
        patterns = [
            r"(\w+)\s*\(",
            r"\$\w+->(\w+)\s*\(",
            r"self::(\w+)\s*\(",
            r"\w+::(\w+)\s*\(",
        ]
        for pattern in patterns:
            calls.extend(re.findall(pattern, content))

        noise = {"echo", "print", "die", "exit", "isset", "empty", "array", "function", "if", "for", "foreach", "while"}
        return [c for c in set(calls) if c not in noise]

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns for PHP."""
        path = Path(file_path)
        stem = path.stem
        parent = str(path.parent)
        cap_stem = stem[0].upper() + stem[1:] if stem else stem
        return [
            f"tests/{cap_stem}Test.php",
            f"tests/{parent}/{cap_stem}Test.php",
            f"tests/Unit/{cap_stem}Test.php",
            f"tests/Feature/{cap_stem}Test.php",
        ]
```

---

### Task 5: Update AST Models

**File:** `src/ast/models.py`

Update `CodeChunk` to include new fields:

```python
@dataclass
class CodeChunk:
    """Represents a parseable unit of code."""

    chunk_type: Literal["function", "class", "method", "module"]
    name: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str

    signature: str | None = None
    docstring: str | None = None

    # Relationship data (NEW)
    imports: list[str] = field(default_factory=list)   # File-level imports
    calls: list[str] = field(default_factory=list)     # Function calls in this chunk
```

---

### Task 6: Refactor AST Parser

**File:** `src/ast/parser.py`

Replace current implementation to use language plugins:

```python
"""AST parsing using language plugins."""

from dataclasses import dataclass

import structlog
import tree_sitter_language_pack as ts_pack

from src.languages import get_plugin_for_file

from .models import CodeChunk

log = structlog.get_logger()


@dataclass
class ParseResult:
    """Result of parsing a file."""
    chunks: list[CodeChunk]
    imports: list[str]


class CodeParser:
    """Parse source code using language plugins."""

    def parse(self, file_path: str, content: str) -> ParseResult | None:
        """Parse file into chunks with imports and calls."""
        plugin = get_plugin_for_file(file_path)
        if not plugin:
            return None

        # File-level imports
        imports = plugin.parse_imports(content)

        # Parse AST chunks
        chunks = self._parse_chunks(file_path, content, plugin)

        # Attach imports and parse calls for each chunk
        for chunk in chunks:
            chunk.imports = imports
            if chunk.chunk_type in ("function", "method"):
                chunk.calls = plugin.parse_calls(chunk.content)

        return ParseResult(chunks=chunks, imports=imports)

    def _parse_chunks(self, file_path: str, content: str, plugin) -> list[CodeChunk]:
        """Extract chunks using tree-sitter."""
        try:
            parser = ts_pack.get_parser(plugin.tree_sitter_name)
            tree = parser.parse(content.encode())
            return self._walk_tree(tree.root_node, file_path, content.encode(), plugin)
        except Exception as e:
            log.warning("parse_failed", file=file_path, error=str(e))
            return []

    def _walk_tree(self, root, file_path: str, content_bytes: bytes, plugin) -> list[CodeChunk]:
        """Walk AST and extract matching nodes."""
        chunks = []

        def walk(node):
            if node.type in plugin.extract_node_types:
                chunk = self._node_to_chunk(node, file_path, content_bytes, plugin)
                if chunk:
                    chunks.append(chunk)
            for child in node.children:
                walk(child)

        walk(root)
        return chunks

    def _node_to_chunk(self, node, file_path: str, content_bytes: bytes, plugin) -> CodeChunk | None:
        """Convert AST node to CodeChunk."""
        content = content_bytes[node.start_byte:node.end_byte].decode()

        # Extract name
        name = None
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                name = child.text.decode()
                break

        if not name:
            return None

        chunk_type = "class" if "class" in node.type else "function"

        return CodeChunk(
            chunk_type=chunk_type,
            name=name,
            content=content,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language=plugin.name,
            signature=plugin.extract_signature(node, content_bytes),
            docstring=plugin.extract_docstring(node, content_bytes),
            imports=[],
            calls=[],
        )


_parser: CodeParser | None = None


def get_code_parser() -> CodeParser:
    global _parser
    if _parser is None:
        _parser = CodeParser()
    return _parser
```

---

### Task 7: Update RAG Indexer

**File:** `src/rag/indexer.py`

Update metadata storage to include imports and calls:

```python
# In _embed_and_store method, update metadata:
"metadata": {
    "file_path": chunk.file_path,
    "name": chunk.name,
    "chunk_type": chunk.chunk_type,
    "content": chunk.content[:1000],
    "start_line": chunk.start_line,
    "end_line": chunk.end_line,
    "language": chunk.language,
    # NEW
    "imports": chunk.imports,
    "calls": chunk.calls,
}
```

---

### Task 8: Implement Smart Retriever

**File:** `src/rag/retriever.py`

Replace current retriever with explicit relationship lookup:

```python
"""Smart context retrieval with explicit relationships."""

import structlog

from src.ast.models import RelatedCode
from src.languages import get_plugin_for_file

from .config import get_rag_settings
from .vector_store import get_vector_store

log = structlog.get_logger()


class SmartRetriever:
    """Retrieve related code using explicit relationships only."""

    def __init__(self) -> None:
        self._store = get_vector_store()
        self._settings = get_rag_settings()

    def retrieve(
        self,
        owner: str,
        repo: str,
        file_path: str,
        function_name: str,
    ) -> list[RelatedCode]:
        """Retrieve explicitly related code.

        Returns:
            List of RelatedCode with relationship: 'test', 'caller', or 'callee'
        """
        namespace = f"{owner}/{repo}"
        plugin = get_plugin_for_file(file_path)
        results: list[RelatedCode] = []

        # 1. Find TEST
        if plugin:
            test = self._find_test(namespace, file_path, function_name, plugin)
            if test:
                results.append(test)

        # 2. Find CALLERS (functions that call this function)
        callers = self._find_callers(namespace, file_path, function_name)
        results.extend(callers[:2])

        # 3. Find CALLEES (functions this function calls)
        callees = self._find_callees(namespace, file_path, function_name)
        results.extend(callees[:2])

        log.info("retriever.complete", file=file_path, func=function_name, count=len(results))
        return results

    def _find_test(self, namespace: str, file_path: str, function_name: str, plugin) -> RelatedCode | None:
        """Find test file/function using patterns."""
        test_paths = plugin.get_test_patterns(file_path)

        for test_path in test_paths:
            results = self._store.query_by_metadata(
                namespace=namespace,
                filter={"file_path": test_path},
                top_k=10,
            )
            if not results:
                continue

            # Look for test function matching the source function
            for r in results:
                name = r["metadata"].get("name", "")
                if function_name.lower() in name.lower():
                    return RelatedCode(
                        file_path=r["metadata"]["file_path"],
                        name=name,
                        content=r["metadata"].get("content", ""),
                        chunk_type=r["metadata"].get("chunk_type", "function"),
                        relevance_score=1.0,
                        relationship="test",
                    )
        return None

    def _find_callers(self, namespace: str, file_path: str, function_name: str) -> list[RelatedCode]:
        """Find functions that call this function."""
        results = self._store.query_by_metadata(
            namespace=namespace,
            filter={
                "calls": {"$in": [function_name]},
                "file_path": {"$ne": file_path},
            },
            top_k=5,
        )
        return [
            RelatedCode(
                file_path=r["metadata"]["file_path"],
                name=r["metadata"]["name"],
                content=r["metadata"].get("content", ""),
                chunk_type=r["metadata"].get("chunk_type", "function"),
                relevance_score=1.0,
                relationship="caller",
            )
            for r in results
        ]

    def _find_callees(self, namespace: str, file_path: str, function_name: str) -> list[RelatedCode]:
        """Find functions that this function calls."""
        # Get current function's calls
        current = self._store.query_by_metadata(
            namespace=namespace,
            filter={"file_path": file_path, "name": function_name},
            top_k=1,
        )
        if not current:
            return []

        called = current[0]["metadata"].get("calls", [])
        if not called:
            return []

        callees = []
        for name in called[:5]:
            results = self._store.query_by_metadata(
                namespace=namespace,
                filter={"name": name, "file_path": {"$ne": file_path}},
                top_k=1,
            )
            if results:
                r = results[0]
                callees.append(RelatedCode(
                    file_path=r["metadata"]["file_path"],
                    name=r["metadata"]["name"],
                    content=r["metadata"].get("content", ""),
                    chunk_type=r["metadata"].get("chunk_type", "function"),
                    relevance_score=1.0,
                    relationship="callee",
                ))
        return callees


def get_retriever() -> SmartRetriever:
    return SmartRetriever()
```

---

### Task 9: Add Vector Store Method

**File:** `src/rag/vector_store.py`

Add metadata-only query method:

```python
def query_by_metadata(
    self,
    namespace: str,
    filter: dict,
    top_k: int = 10,
) -> list[dict]:
    """Query by metadata filter (without vector similarity)."""
    if self.pc is None:
        return []
    try:
        dummy = [0.0] * self._settings.embedding_dimensions
        results = self.index.query(
            namespace=namespace,
            vector=dummy,
            filter=filter,
            top_k=top_k,
            include_metadata=True,
        )
        return [{"id": m.id, "score": m.score, "metadata": m.metadata} for m in results.matches]
    except Exception as e:
        log.warning("query_by_metadata_failed", error=str(e))
        return []
```

---

## Execution Order

1. Create `src/languages/base.py`
2. Create `src/languages/python.py`
3. Create `src/languages/javascript.py`
4. Create `src/languages/php.py`
5. Create `src/languages/__init__.py`
6. Update `src/ast/models.py` - add `imports`, `calls` fields
7. Replace `src/ast/parser.py` - use language plugins
8. Update `src/rag/vector_store.py` - add `query_by_metadata`
9. Update `src/rag/indexer.py` - store imports/calls
10. Replace `src/rag/retriever.py` - smart retrieval
11. Delete old code in `src/core/constants.py` related to language maps
12. Run tests and fix issues

---

## Testing

After implementation, verify:

```bash
# Unit tests
uv run pytest tests/test_ast_parser.py -v
uv run pytest tests/test_rag_*.py -v

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
```

Expected:

```
Imports: ['src.utils']
Calls: ['helper']
```
