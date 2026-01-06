# 🚀 Advanced Features Plan: Nâng cấp AI Code Review

> **Mục tiêu**: Nâng cấp hệ thống review code từ basic diff analysis lên intelligent, context-aware analysis như CodeRabbit.

---

## 📑 Mục lục

1. [RAG-based Context Retrieval](#1-rag-based-context-retrieval)
2. [Tree-sitter Integration](#2-tree-sitter-integration)
3. [PR Summary Agent](#3-pr-summary-agent)
4. [Implementation Roadmap](#4-implementation-roadmap)

---

## 1. RAG-based Context Retrieval

### 1.1 Vấn đề hiện tại

```
Hiện tại: Mỗi file được review độc lập, không có context từ codebase
→ Bỏ lỡ: patterns, conventions, related code, dependencies
```

### 1.2 Giải pháp: Retrieval-Augmented Generation (RAG)

```
┌─────────────────────────────────────────────────────────────────┐
│                     RAG Pipeline                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐     │
│   │ Codebase │───▶│ Chunking &   │───▶│ Vector Database  │     │
│   │ Files    │    │ Embedding    │    │ (ChromaDB/FAISS) │     │
│   └──────────┘    └──────────────┘    └────────┬─────────┘     │
│                                                 │               │
│   ┌──────────┐    ┌──────────────┐              │               │
│   │ PR Diff  │───▶│ Query        │◀─────────────┘               │
│   │          │    │ Generation   │                              │
│   └──────────┘    └──────┬───────┘                              │
│                          │                                       │
│                          ▼                                       │
│                   ┌──────────────┐    ┌──────────────────┐      │
│                   │ Retrieved    │───▶│ Enhanced Prompt  │      │
│                   │ Context      │    │ for LLM          │      │
│                   └──────────────┘    └──────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Architecture

```
src/
├── rag/
│   ├── __init__.py
│   ├── embedder.py          # Code embedding với code-specific model
│   ├── chunker.py           # Smart code chunking (by function/class)
│   ├── vector_store.py      # ChromaDB/FAISS wrapper
│   ├── retriever.py         # Context retrieval logic
│   └── indexer.py           # Codebase indexing service
```

### 1.4 Core Components

#### 1.4.1 Code Chunker

```python
# src/rag/chunker.py
from dataclasses import dataclass
from enum import Enum

class ChunkType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    IMPORT_BLOCK = "imports"

@dataclass
class CodeChunk:
    content: str
    file_path: str
    chunk_type: ChunkType
    start_line: int
    end_line: int
    name: str  # function/class name
    docstring: str | None
    dependencies: list[str]  # imports used

class CodeChunker:
    """Smart code chunking that preserves semantic boundaries."""

    def chunk_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """
        Chunk code by semantic units:
        - Functions/methods
        - Classes
        - Import blocks
        - Top-level constants
        """
        # Use Tree-sitter to parse and extract semantic units
        pass

    def chunk_with_context(self, chunk: CodeChunk, window: int = 3) -> str:
        """Add surrounding context to chunk for better embedding."""
        pass
```

#### 1.4.2 Embedder

```python
# src/rag/embedder.py
from sentence_transformers import SentenceTransformer

class CodeEmbedder:
    """
    Sử dụng model được train cho code:
    - microsoft/codebert-base
    - Salesforce/codet5-base
    - sentence-transformers/all-MiniLM-L6-v2 (general but fast)
    """

    def __init__(self, model_name: str = "microsoft/codebert-base"):
        self.model = SentenceTransformer(model_name)

    def embed_chunk(self, chunk: CodeChunk) -> list[float]:
        """Embed a code chunk with metadata."""
        # Combine code + metadata for richer embedding
        text = f"""
        File: {chunk.file_path}
        Type: {chunk.chunk_type.value}
        Name: {chunk.name}

        {chunk.content}
        """
        return self.model.encode(text).tolist()

    def embed_query(self, diff: str, context: str) -> list[float]:
        """Embed a query for retrieval."""
        query = f"Find related code for:\n{diff}\n\nContext: {context}"
        return self.model.encode(query).tolist()
```

#### 1.4.3 Vector Store

```python
# src/rag/vector_store.py
import chromadb
from chromadb.config import Settings

class CodeVectorStore:
    """Vector database for code chunks."""

    def __init__(self, persist_dir: str):
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_dir
        ))

    def get_or_create_collection(self, repo_name: str):
        """Each repo has its own collection."""
        return self.client.get_or_create_collection(
            name=f"repo_{repo_name}",
            metadata={"hnsw:space": "cosine"}
        )

    def upsert_chunks(self, repo: str, chunks: list[CodeChunk], embeddings: list):
        collection = self.get_or_create_collection(repo)
        collection.upsert(
            ids=[f"{c.file_path}:{c.name}" for c in chunks],
            embeddings=embeddings,
            documents=[c.content for c in chunks],
            metadatas=[{
                "file_path": c.file_path,
                "chunk_type": c.chunk_type.value,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "name": c.name,
            } for c in chunks]
        )

    def query(self, repo: str, query_embedding: list, top_k: int = 5):
        collection = self.get_or_create_collection(repo)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
```

#### 1.4.4 Retriever (Integration with Review)

```python
# src/rag/retriever.py
class ContextRetriever:
    """Retrieve relevant context for code review."""

    def __init__(self, embedder: CodeEmbedder, store: CodeVectorStore):
        self.embedder = embedder
        self.store = store

    def get_context_for_diff(
        self,
        repo: str,
        file_path: str,
        diff: str,
        top_k: int = 5
    ) -> list[RetrievedContext]:
        """
        Get relevant context for a diff.

        Strategy:
        1. Extract key elements from diff (function names, imports, etc.)
        2. Query vector store for similar code
        3. Filter out the file being reviewed
        4. Return ranked context
        """
        # Generate query
        query_text = self._build_query(file_path, diff)
        query_embedding = self.embedder.embed_query(diff, query_text)

        # Retrieve
        results = self.store.query(repo, query_embedding, top_k=top_k + 5)

        # Filter & rank
        contexts = []
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            # Skip same file
            if meta["file_path"] == file_path:
                continue

            contexts.append(RetrievedContext(
                content=doc,
                file_path=meta["file_path"],
                relevance_score=1 - distance,  # Convert distance to similarity
                chunk_type=meta["chunk_type"],
            ))

        return contexts[:top_k]
```

### 1.5 Integration với Review Flow

```python
# src/agents/nodes/base_agent.py (updated)

async def analyze_file(file: FileChange) -> list[ReviewComment]:
    # NEW: Retrieve context
    context = retriever.get_context_for_diff(
        repo=f"{state['context'].owner}/{state['context'].repo}",
        file_path=file.filename,
        diff=file.patch
    )

    # Enhanced prompt with context
    prompt = _build_prompt_with_context(
        template=prompt_template,
        filename=file.filename,
        diff=file.patch,
        retrieved_context=context,  # NEW
    )

    # ... rest of analysis
```

---

## 2. Tree-sitter Integration

### 2.1 Vấn đề hiện tại

```
Hiện tại: Chỉ nhìn diff như text thuần
→ Không hiểu: scope, types, function calls, data flow
```

### 2.2 Giải pháp: AST-Aware Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│                  Tree-sitter Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐     │
│   │ Source   │───▶│ Tree-sitter  │───▶│ AST              │     │
│   │ Code     │    │ Parser       │    │ (Syntax Tree)    │     │
│   └──────────┘    └──────────────┘    └────────┬─────────┘     │
│                                                 │               │
│                                                 ▼               │
│                                        ┌──────────────────┐    │
│                                        │ Extract:         │    │
│                                        │ - Functions      │    │
│                                        │ - Classes        │    │
│                                        │ - Imports        │    │
│                                        │ - Call sites     │    │
│                                        │ - Variables      │    │
│                                        └────────┬─────────┘    │
│                                                 │               │
│                                                 ▼               │
│   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐    │
│   │ Enhanced │◀───│ Semantic     │◀───│ Structured       │    │
│   │ Review   │    │ Analysis     │    │ Code Info        │    │
│   └──────────┘    └──────────────┘    └──────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Architecture

```
src/
├── ast/
│   ├── __init__.py
│   ├── parser.py            # Tree-sitter wrapper
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py          # Base extractor
│   │   ├── python.py        # Python-specific extraction
│   │   ├── javascript.py    # JS/TS extraction
│   │   └── php.py           # PHP extraction
│   ├── models.py            # Data models for AST info
│   └── analyzer.py          # High-level analysis
```

### 2.4 Core Components

#### 2.4.1 AST Models

```python
# src/ast/models.py
from dataclasses import dataclass, field
from enum import Enum

class SymbolType(Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    VARIABLE = "variable"
    IMPORT = "import"
    CONSTANT = "constant"

@dataclass
class Symbol:
    """A code symbol (function, class, variable, etc.)"""
    name: str
    type: SymbolType
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None
    parent: str | None = None  # e.g., class name for methods

@dataclass
class FunctionCall:
    """A function/method call site."""
    name: str
    line: int
    arguments: list[str]
    receiver: str | None = None  # e.g., obj.method() -> receiver = "obj"

@dataclass
class Import:
    """An import statement."""
    module: str
    names: list[str]  # specific imports
    alias: str | None = None
    line: int

@dataclass
class FileAST:
    """Parsed AST information for a file."""
    file_path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    function_calls: list[FunctionCall] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)

    def get_symbol_at_line(self, line: int) -> Symbol | None:
        """Get the symbol containing a specific line."""
        for sym in self.symbols:
            if sym.start_line <= line <= sym.end_line:
                return sym
        return None

    def get_functions(self) -> list[Symbol]:
        return [s for s in self.symbols if s.type in (SymbolType.FUNCTION, SymbolType.METHOD)]

    def get_classes(self) -> list[Symbol]:
        return [s for s in self.symbols if s.type == SymbolType.CLASS]
```

#### 2.4.2 Tree-sitter Parser

```python
# src/ast/parser.py
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

class TreeSitterParser:
    """Multi-language parser using Tree-sitter."""

    LANGUAGES = {
        "python": tspython.language(),
        "javascript": tsjavascript.language(),
        "typescript": tsjavascript.language(),  # TS grammar
    }

    def __init__(self):
        self.parsers: dict[str, Parser] = {}
        for lang, grammar in self.LANGUAGES.items():
            parser = Parser()
            parser.language = Language(grammar)
            self.parsers[lang] = parser

    def parse(self, code: str, language: str) -> tree_sitter.Tree:
        """Parse code and return AST."""
        parser = self.parsers.get(language)
        if not parser:
            raise ValueError(f"Unsupported language: {language}")
        return parser.parse(bytes(code, "utf8"))

    def parse_file(self, file_path: str) -> tree_sitter.Tree:
        """Parse a file, auto-detecting language."""
        language = self._detect_language(file_path)
        with open(file_path) as f:
            code = f.read()
        return self.parse(code, language)

    def _detect_language(self, file_path: str) -> str:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "text"
```

#### 2.4.3 Python Extractor

```python
# src/ast/extractors/python.py
from ..models import Symbol, SymbolType, FunctionCall, Import, FileAST

class PythonExtractor:
    """Extract semantic information from Python AST."""

    def extract(self, tree: tree_sitter.Tree, file_path: str) -> FileAST:
        result = FileAST(file_path=file_path, language="python")

        # Extract all relevant nodes
        self._extract_functions(tree.root_node, result)
        self._extract_classes(tree.root_node, result)
        self._extract_imports(tree.root_node, result)
        self._extract_calls(tree.root_node, result)

        return result

    def _extract_functions(self, node, result: FileAST, parent: str = None):
        """Extract function definitions."""
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")

            result.symbols.append(Symbol(
                name=name_node.text.decode(),
                type=SymbolType.METHOD if parent else SymbolType.FUNCTION,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=self._build_signature(name_node, params_node),
                docstring=self._extract_docstring(node),
                parent=parent,
            ))

        # Recurse
        for child in node.children:
            self._extract_functions(child, result, parent)

    def _extract_classes(self, node, result: FileAST):
        """Extract class definitions."""
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = name_node.text.decode()

            result.symbols.append(Symbol(
                name=class_name,
                type=SymbolType.CLASS,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                docstring=self._extract_docstring(node),
            ))

            # Extract methods
            body = node.child_by_field_name("body")
            if body:
                self._extract_functions(body, result, parent=class_name)

        for child in node.children:
            self._extract_classes(child, result)

    def _extract_calls(self, node, result: FileAST):
        """Extract function calls."""
        if node.type == "call":
            func = node.child_by_field_name("function")
            args = node.child_by_field_name("arguments")

            if func.type == "attribute":
                # obj.method() call
                receiver = func.child_by_field_name("object").text.decode()
                name = func.child_by_field_name("attribute").text.decode()
            else:
                receiver = None
                name = func.text.decode()

            result.function_calls.append(FunctionCall(
                name=name,
                line=node.start_point[0] + 1,
                arguments=self._extract_arguments(args),
                receiver=receiver,
            ))

        for child in node.children:
            self._extract_calls(child, result)
```

### 2.5 Integration với Review

```python
# src/agents/nodes/context_extractor.py (enhanced)

from ...ast.parser import TreeSitterParser
from ...ast.extractors import get_extractor

async def run(state: GraphState) -> dict:
    parser = TreeSitterParser()

    enhanced_files = []
    for file in state["files"]:
        if not file.patch:
            enhanced_files.append(file)
            continue

        # Parse full file content (fetch from GitHub if needed)
        full_content = await fetch_file_content(state["context"], file.filename)

        try:
            tree = parser.parse(full_content, file.language)
            extractor = get_extractor(file.language)
            ast_info = extractor.extract(tree, file.filename)

            # Enhance file with AST info
            enhanced_file = EnhancedFileChange(
                **file.dict(),
                ast=ast_info,
                changed_functions=get_changed_functions(file.patch, ast_info),
                affected_calls=get_affected_calls(file.patch, ast_info),
            )
            enhanced_files.append(enhanced_file)
        except Exception as e:
            log.warning("ast.parse_failed", file=file.filename, error=str(e))
            enhanced_files.append(file)

    return {"files": enhanced_files}
```

---

## 3. PR Summary Agent

### 3.1 Vấn đề hiện tại

```
Hiện tại: Chỉ có line-level comments
→ Thiếu: High-level overview, change impact, architecture insights
```

### 3.2 Giải pháp: Dedicated Summary Agent

```
┌─────────────────────────────────────────────────────────────────┐
│                  PR Summary Agent                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────────────────────────────────────────────┐     │
│   │ Inputs:                                               │     │
│   │ - All file changes (diffs)                           │     │
│   │ - AST analysis results                               │     │
│   │ - Retrieved context                                  │     │
│   │ - PR metadata (title, description, linked issues)    │     │
│   └──────────────────────────────────────────────────────┘     │
│                          │                                       │
│                          ▼                                       │
│   ┌──────────────────────────────────────────────────────┐     │
│   │ Analysis:                                             │     │
│   │ 1. Categorize changes (feature/fix/refactor/docs)    │     │
│   │ 2. Identify key modifications                        │     │
│   │ 3. Detect patterns/anti-patterns                     │     │
│   │ 4. Assess risk areas                                 │     │
│   │ 5. Generate visual diagrams                          │     │
│   └──────────────────────────────────────────────────────┘     │
│                          │                                       │
│                          ▼                                       │
│   ┌──────────────────────────────────────────────────────┐     │
│   │ Outputs:                                              │     │
│   │ - Executive summary                                  │     │
│   │ - Change breakdown by category                       │     │
│   │ - Risk assessment                                    │     │
│   │ - Mermaid diagrams (sequence/flow)                   │     │
│   │ - Review checklist                                   │     │
│   └──────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Architecture

```
src/agents/
├── nodes/
│   ├── ...
│   └── summary_agent.py     # NEW: PR Summary Agent
├── prompts/
│   ├── ...
│   └── summary.py           # NEW: Summary prompt
```

### 3.4 Implementation

#### 3.4.1 Summary Models

```python
# src/agents/models.py (additions)

class ChangeCategory(str, Enum):
    FEATURE = "feature"
    FIX = "fix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"
    SECURITY = "security"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PRSummary(BaseModel):
    """High-level summary of PR changes."""

    title: str
    category: ChangeCategory
    summary: str  # 2-3 sentences

    key_changes: list[str]  # Bullet points
    files_changed: int
    lines_added: int
    lines_removed: int

    risk_level: RiskLevel
    risk_areas: list[str]

    testing_notes: list[str]  # What should be tested
    review_checklist: list[str]  # Key things to verify

    diagram: str | None = None  # Mermaid diagram

class DiagramType(str, Enum):
    SEQUENCE = "sequence"
    FLOWCHART = "flowchart"
    CLASS = "class"
    NONE = "none"
```

#### 3.4.2 Summary Prompt

```python
# src/agents/prompts/summary.py

PROMPT = """You are a senior tech lead reviewing a pull request.

## PR Information
- Title: {pr_title}
- Author: {pr_author}
- Description: {pr_description}

## Files Changed ({file_count} files, +{additions}/-{deletions})
{file_list}

## Detailed Changes
{changes}

## Your Task
Provide a comprehensive summary of this PR that helps reviewers understand:
1. What this PR does (high-level)
2. Key changes to be aware of
3. Potential risks or areas needing careful review
4. What testing is recommended

## Output (JSON)
{{
    "title": "<concise PR title suggestion if current is unclear>",
    "category": "<feature|fix|refactor|docs|test|chore|security>",
    "summary": "<2-3 sentence executive summary>",
    "key_changes": [
        "<key change 1>",
        "<key change 2>"
    ],
    "risk_level": "<low|medium|high|critical>",
    "risk_areas": [
        "<risk area 1 with explanation>",
        "<risk area 2 with explanation>"
    ],
    "testing_notes": [
        "<what to test 1>",
        "<what to test 2>"
    ],
    "review_checklist": [
        "<thing to verify 1>",
        "<thing to verify 2>"
    ],
    "diagram_type": "<sequence|flowchart|class|none>",
    "diagram_description": "<what the diagram should show, if applicable>"
}}
"""
```

#### 3.4.3 Summary Agent Implementation

````python
# src/agents/nodes/summary_agent.py

import structlog
from ..models import PRSummary, DiagramType
from ..prompts import summary as summary_prompt
from ...core.llm import get_structured_llm

log = structlog.get_logger()

async def run(state: GraphState) -> dict:
    """Generate high-level PR summary."""
    context = state["context"]
    files = state["files"]

    log.info("summary_agent.started", files=len(files))

    # Prepare file list
    file_list = "\n".join([
        f"- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})"
        for f in files
    ])

    # Prepare detailed changes (truncate if too long)
    changes = []
    for f in files:
        if f.patch:
            truncated = f.patch[:2000] + "..." if len(f.patch) > 2000 else f.patch
            changes.append(f"### {f.filename}\n```diff\n{truncated}\n```")

    prompt = summary_prompt.PROMPT.format(
        pr_title=context.title,
        pr_author=context.author,
        pr_description=state.get("pr_description", "No description"),
        file_count=len(files),
        additions=sum(f.additions for f in files),
        deletions=sum(f.deletions for f in files),
        file_list=file_list,
        changes="\n\n".join(changes),
    )

    try:
        llm = get_structured_llm(PRSummary)
        result = await llm.ainvoke(prompt)

        # Generate diagram if needed
        diagram = None
        if result.diagram_type != DiagramType.NONE:
            diagram = await generate_mermaid_diagram(
                result.diagram_type,
                result.diagram_description,
                files
            )

        log.info(
            "summary_agent.completed",
            category=result.category,
            risk=result.risk_level
        )

        return {
            "pr_summary": result,
            "summary_diagram": diagram,
        }

    except Exception as e:
        log.error("summary_agent.failed", error=str(e))
        return {"pr_summary": None, "summary_diagram": None}


async def generate_mermaid_diagram(
    diagram_type: DiagramType,
    description: str,
    files: list
) -> str:
    """Generate a Mermaid diagram for the PR."""

    if diagram_type == DiagramType.SEQUENCE:
        prompt = f"""Generate a Mermaid sequence diagram for:
{description}

Files involved: {[f.filename for f in files]}

Return ONLY the Mermaid code, no explanation.
Example format:
```mermaid
sequenceDiagram
    participant A
    participant B
    A->>B: Message
````

"""
elif diagram_type == DiagramType.FLOWCHART:
prompt = f"""Generate a Mermaid flowchart for:
{description}

Return ONLY the Mermaid code.
"""
else:
return None

    # Call LLM to generate diagram
    llm = get_llm()
    result = await llm.ainvoke(prompt)

    # Extract mermaid code
    if "```mermaid" in result:
        start = result.find("```mermaid") + 10
        end = result.find("```", start)
        return result[start:end].strip()

    return result

````

#### 3.4.4 Updated Graph

```python
# src/agents/graph.py (updated)

from .nodes import (
    acknowledger,
    aggregator,
    context_extractor,
    github_publisher,
    logic_agent,
    security_agent,
    slack_reporter,
    style_agent,
    summary_agent,  # NEW
)

def create_graph() -> StateGraph:
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("acknowledge", acknowledger.run)
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("summary", summary_agent.run)  # NEW
    g.add_node("aggregate", aggregator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)

    # Flow
    g.set_entry_point("acknowledge")
    g.add_edge("acknowledge", "extract")

    # Parallel agents (fan-out)
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")
    g.add_edge("extract", "summary")  # NEW: Runs in parallel

    # Fan-in to aggregator
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")
    g.add_edge("summary", "aggregate")  # NEW

    # Rest of flow...
    g.add_edge("aggregate", "publish")
    g.add_edge("publish", "notify")
    g.add_edge("notify", END)

    return g.compile()
````

### 3.5 Sample Output

````markdown
## 🤖 AI Code Review Summary

### 📋 Overview

**Category**: Feature  
**Risk Level**: 🟡 Medium

This PR introduces a new payment gateway integration using the Strategy pattern.
It adds support for Stripe and PayPal payment processing with a common interface.

### 🔑 Key Changes

- Added `PaymentGateway` abstract base class
- Implemented `StripeGateway` with webhook handling
- Implemented `PayPalGateway` with OAuth flow
- Updated `OrderService` to use dependency injection
- Added payment configuration to settings

### ⚠️ Risk Areas

- **Error Handling**: `StripeGateway.charge()` doesn't handle network timeouts
- **Security**: PayPal OAuth tokens stored in session without encryption
- **Testing**: No unit tests for webhook signature verification

### 📝 Testing Notes

- [ ] Test Stripe payment with test card numbers
- [ ] Verify PayPal OAuth redirect works correctly
- [ ] Test webhook signature validation
- [ ] Check error handling for declined cards

### 🔍 Review Checklist

- [ ] Verify API keys are loaded from environment
- [ ] Check idempotency key handling for retries
- [ ] Confirm PCI compliance requirements

### 📊 Architecture

```mermaid
sequenceDiagram
    participant Client
    participant OrderService
    participant PaymentGateway
    participant Stripe

    Client->>OrderService: createOrder(items)
    OrderService->>PaymentGateway: charge(amount)
    PaymentGateway->>Stripe: create_payment_intent()
    Stripe-->>PaymentGateway: payment_intent
    PaymentGateway-->>OrderService: PaymentResult
    OrderService-->>Client: Order confirmation
```
````

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

| Task                                 | Priority | Effort |
| ------------------------------------ | -------- | ------ |
| Set up Tree-sitter parser            | High     | 2 days |
| Create Python extractor              | High     | 2 days |
| Create JS/TS extractor               | Medium   | 2 days |
| Integrate AST into context_extractor | High     | 1 day  |
| Unit tests for parsers               | Medium   | 1 day  |

### Phase 2: RAG System (Week 2-3)

| Task                       | Priority | Effort |
| -------------------------- | -------- | ------ |
| Set up ChromaDB            | High     | 1 day  |
| Implement CodeChunker      | High     | 2 days |
| Implement CodeEmbedder     | High     | 1 day  |
| Implement ContextRetriever | High     | 2 days |
| Integrate RAG into agents  | High     | 2 days |
| Codebase indexing service  | Medium   | 2 days |

### Phase 3: Summary Agent (Week 3-4)

| Task                         | Priority | Effort |
| ---------------------------- | -------- | ------ |
| Create PRSummary models      | High     | 1 day  |
| Implement summary prompt     | High     | 1 day  |
| Implement summary_agent.py   | High     | 2 days |
| Add diagram generation       | Medium   | 2 days |
| Integrate into graph         | High     | 1 day  |
| Update publisher for summary | Medium   | 1 day  |

### Phase 4: Polish & Testing (Week 4-5)

| Task                     | Priority | Effort |
| ------------------------ | -------- | ------ |
| End-to-end testing       | High     | 2 days |
| Performance optimization | Medium   | 2 days |
| Documentation            | Medium   | 1 day  |
| Monitoring & logging     | Medium   | 1 day  |

---

## 📚 Dependencies to Add

```toml
# pyproject.toml additions

[project.dependencies]
# Tree-sitter
tree-sitter = "^0.22.0"
tree-sitter-python = "^0.22.0"
tree-sitter-javascript = "^0.22.0"
tree-sitter-typescript = "^0.22.0"

# RAG / Embeddings
chromadb = "^0.4.0"
sentence-transformers = "^2.2.0"

# Optional: Better code embeddings
# transformers = "^4.35.0"
# torch = "^2.1.0"
```

---

## 🎯 Success Metrics

| Metric               | Current         | Target                    |
| -------------------- | --------------- | ------------------------- |
| Context awareness    | 0% (no context) | 80% (related code found)  |
| False positive rate  | ~30%            | <15%                      |
| Review completeness  | Line-level only | Line + Summary + Diagrams |
| Cross-file detection | No              | Yes                       |
| User satisfaction    | Basic           | Premium feel              |

---

## 📌 Next Steps

1. **Bắt đầu với Tree-sitter** - Foundation cho mọi thứ khác
2. **Implement Python extractor** - Language chính của dự án
3. **Set up ChromaDB** - Chuẩn bị cho RAG
4. **Summary Agent** - Quick win, visible improvement

Bạn muốn bắt đầu implement phần nào trước?
