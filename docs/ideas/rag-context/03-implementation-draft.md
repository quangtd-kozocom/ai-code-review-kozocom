# 03. Implementation Draft

## 📦 New Dependencies

```toml
# pyproject.toml - thêm vào dependencies
"pinecone>=5.0.0",
"tree-sitter>=0.23.0",
"tree-sitter-languages>=1.10.0",
"gitpython>=3.1.0",
```

## ⚙️ New Environment Variables

```bash
# .env
PINECONE_API_KEY=pcsk_xxx
PINECONE_INDEX_NAME=code-reviewer
# PINECONE_ENVIRONMENT không cần nữa với Pinecone v5 (serverless)
```

---

## 🗂️ File Structure

```
src/
├── ast/
│   ├── __init__.py
│   ├── parser.py
│   ├── models.py
│   └── extractors/
│       ├── __init__.py
│       ├── base.py
│       └── python.py
│
└── rag/
    ├── __init__.py
    ├── config.py
    ├── embedder.py
    ├── vector_store.py
    ├── chunker.py
    ├── indexer.py
    └── retriever.py
```

---

## 📄 Draft Code

### `src/rag/config.py`

```python
"""RAG configuration."""
from pydantic_settings import BaseSettings


class RAGSettings(BaseSettings):
    """RAG-related settings."""

    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "code-reviewer"

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1024

    # Chunking
    max_chunk_tokens: int = 500  # Max tokens per chunk

    # Retrieval
    top_k: int = 5  # Number of similar chunks to retrieve

    # Indexing
    batch_size: int = 100  # Vectors per upsert batch

    # File patterns
    include_extensions: list[str] = [
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".go", ".rs", ".java", ".php",
        ".md", ".yaml", ".yml"
    ]
    exclude_patterns: list[str] = [
        "node_modules/*",
        "vendor/*",
        ".venv/*",
        "__pycache__/*",
        "dist/*",
        "build/*",
        ".git/*",
        "*.lock",
        "*.min.js",
        ".env*",
    ]

    class Config:
        env_prefix = ""


rag_settings = RAGSettings()
```

---

### `src/ast/models.py`

```python
"""AST data models."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CodeChunk:
    """Represents a parseable unit of code."""

    chunk_type: Literal["function", "class", "method", "import", "module"]
    name: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str

    # Optional
    signature: str | None = None
    docstring: str | None = None
    dependencies: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Generate unique ID for this chunk."""
        return f"{self.file_path}:{self.name}:{self.start_line}"

    def to_embedding_text(self) -> str:
        """Convert chunk to text for embedding."""
        parts = [f"{self.chunk_type}: {self.name}"]
        if self.signature:
            parts.append(f"Signature: {self.signature}")
        if self.docstring:
            parts.append(f"Docstring: {self.docstring}")
        parts.append(f"Code:\n{self.content}")
        return "\n".join(parts)


@dataclass
class ASTInfo:
    """Parsed AST information for a file."""

    file_path: str
    language: str
    functions: list[dict]  # [{name, signature, start_line, end_line}]
    classes: list[dict]    # [{name, methods, start_line, end_line}]
    imports: list[str]

    # Identified from diff
    changed_entities: list[str] = field(default_factory=list)


@dataclass
class RelatedCode:
    """Related code retrieved from RAG."""

    file_path: str
    name: str
    content: str
    chunk_type: str
    relevance_score: float
    relationship: str  # "caller", "callee", "similar", "test"
```

---

### `src/ast/parser.py`

```python
"""Tree-sitter based code parser."""
import tree_sitter_languages
from pathlib import Path

from .models import CodeChunk, ASTInfo


class CodeParser:
    """Parse source code using Tree-sitter."""

    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".php": "php",
        ".rb": "ruby",
    }

    def detect_language(self, file_path: str) -> str | None:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext)

    def parse_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Parse a file and extract code chunks."""
        language = self.detect_language(file_path)
        if not language:
            return []

        try:
            parser = tree_sitter_languages.get_parser(language)
            tree = parser.parse(content.encode())

            return self._extract_chunks(tree.root_node, file_path, content, language)
        except Exception as e:
            # Log error but don't fail
            print(f"Failed to parse {file_path}: {e}")
            return []

    def _extract_chunks(
        self,
        node,
        file_path: str,
        content: str,
        language: str
    ) -> list[CodeChunk]:
        """Extract code chunks from AST node."""
        chunks = []

        # Define node types to extract per language
        extract_types = self._get_extract_types(language)

        def walk(node):
            if node.type in extract_types:
                chunk = self._node_to_chunk(node, file_path, content, language)
                if chunk:
                    chunks.append(chunk)

            for child in node.children:
                walk(child)

        walk(node)
        return chunks

    def _get_extract_types(self, language: str) -> set[str]:
        """Get node types to extract for a language."""
        if language == "python":
            return {"function_definition", "class_definition"}
        elif language in ("javascript", "typescript", "tsx"):
            return {"function_declaration", "class_declaration", "arrow_function"}
        elif language == "go":
            return {"function_declaration", "method_declaration"}
        elif language == "php":
            return {"function_definition", "class_declaration", "method_declaration"}
        else:
            return {"function_definition", "class_definition"}

    def _node_to_chunk(
        self,
        node,
        file_path: str,
        content: str,
        language: str
    ) -> CodeChunk | None:
        """Convert AST node to CodeChunk."""
        content_bytes = content.encode()
        chunk_content = content_bytes[node.start_byte:node.end_byte].decode()

        # Extract name
        name = self._extract_name(node, language)
        if not name:
            return None

        # Determine chunk type
        chunk_type = self._determine_chunk_type(node.type)

        # Extract signature (for functions)
        signature = self._extract_signature(node, content_bytes, language)

        # Extract docstring
        docstring = self._extract_docstring(node, content_bytes, language)

        return CodeChunk(
            chunk_type=chunk_type,
            name=name,
            content=chunk_content,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language=language,
            signature=signature,
            docstring=docstring,
        )

    def _extract_name(self, node, language: str) -> str | None:
        """Extract name from node."""
        # Find identifier child
        for child in node.children:
            if child.type == "identifier" or child.type == "name":
                return child.text.decode()
        return None

    def _determine_chunk_type(self, node_type: str) -> str:
        """Map AST node type to chunk type."""
        if "class" in node_type:
            return "class"
        elif "method" in node_type:
            return "method"
        elif "function" in node_type:
            return "function"
        return "function"

    def _extract_signature(self, node, content_bytes: bytes, language: str) -> str | None:
        """Extract function/method signature."""
        # For Python: get first line up to ":"
        if language == "python":
            first_line = content_bytes[node.start_byte:].split(b"\n")[0]
            return first_line.decode().strip()
        return None

    def _extract_docstring(self, node, content_bytes: bytes, language: str) -> str | None:
        """Extract docstring if present."""
        # For Python: look for string as first statement in body
        if language == "python":
            for child in node.children:
                if child.type == "block":
                    for stmt in child.children:
                        if stmt.type == "expression_statement":
                            for expr in stmt.children:
                                if expr.type == "string":
                                    return expr.text.decode().strip('"\' ')
                    break
        return None

    def get_ast_info(self, file_path: str, content: str) -> ASTInfo | None:
        """Get structured AST info for a file."""
        language = self.detect_language(file_path)
        if not language:
            return None

        chunks = self.parse_file(file_path, content)

        functions = []
        classes = []

        for chunk in chunks:
            info = {
                "name": chunk.name,
                "signature": chunk.signature,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
            if chunk.chunk_type in ("function", "method"):
                functions.append(info)
            elif chunk.chunk_type == "class":
                classes.append(info)

        # Extract imports (simplified)
        imports = self._extract_imports(content, language)

        return ASTInfo(
            file_path=file_path,
            language=language,
            functions=functions,
            classes=classes,
            imports=imports,
        )

    def _extract_imports(self, content: str, language: str) -> list[str]:
        """Extract import statements."""
        imports = []
        for line in content.split("\n"):
            line = line.strip()
            if language == "python":
                if line.startswith("import ") or line.startswith("from "):
                    imports.append(line)
            elif language in ("javascript", "typescript"):
                if line.startswith("import "):
                    imports.append(line)
        return imports


# Singleton instance
code_parser = CodeParser()
```

---

### `src/rag/embedder.py`

```python
"""Embedding service using OpenAI."""
from openai import OpenAI

from .config import rag_settings


class Embedder:
    """Generate embeddings using OpenAI API."""

    def __init__(self):
        self.client = OpenAI()
        self.model = rag_settings.embedding_model
        self.dimensions = rag_settings.embedding_dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )

        return [item.embedding for item in response.data]

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]


# Singleton instance
embedder = Embedder()
```

---

### `src/rag/vector_store.py`

```python
"""Pinecone vector store wrapper."""
from pinecone import Pinecone, ServerlessSpec

from .config import rag_settings


class VectorStore:
    """Pinecone vector store operations."""

    def __init__(self):
        self.pc = Pinecone(api_key=rag_settings.pinecone_api_key)
        self.index_name = rag_settings.pinecone_index_name
        self._index = None

    @property
    def index(self):
        """Get or create Pinecone index."""
        if self._index is None:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                # Create index
                self.pc.create_index(
                    name=self.index_name,
                    dimension=rag_settings.embedding_dimensions,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )

            self._index = self.pc.Index(self.index_name)

        return self._index

    def upsert(
        self,
        vectors: list[dict],
        namespace: str
    ) -> None:
        """Upsert vectors to index.

        Args:
            vectors: List of {"id": str, "values": list[float], "metadata": dict}
            namespace: Namespace (repo identifier)
        """
        # Batch upsert
        batch_size = rag_settings.batch_size
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=namespace)

    def query(
        self,
        vector: list[float],
        namespace: str,
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list[dict]:
        """Query similar vectors.

        Returns:
            List of matches with scores and metadata
        """
        results = self.index.query(
            vector=vector,
            namespace=namespace,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
        )

        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata,
            }
            for match in results.matches
        ]

    def delete_by_file(self, namespace: str, file_path: str) -> None:
        """Delete all vectors for a specific file."""
        # Pinecone doesn't support delete by metadata directly in serverless
        # We need to query first, then delete by IDs
        # Alternative: Use file_path as prefix in ID

        # For now, we'll use the ID prefix strategy:
        # ID format: "file_path:name:line"
        self.index.delete(
            filter={"file_path": {"$eq": file_path}},
            namespace=namespace,
        )

    def delete_namespace(self, namespace: str) -> None:
        """Delete entire namespace (all vectors for a repo)."""
        self.index.delete(delete_all=True, namespace=namespace)


# Singleton instance
vector_store = VectorStore()
```

---

### `src/rag/chunker.py`

```python
"""Code chunking logic."""
from pathlib import Path
import fnmatch
import re

from src.ast.parser import code_parser
from src.ast.models import CodeChunk
from .config import rag_settings


class Chunker:
    """Smart code chunking using AST."""

    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed."""
        # Check extension
        ext = Path(file_path).suffix.lower()
        if ext not in [f".{e.lstrip('.')}" for e in rag_settings.include_extensions]:
            return False

        # Check exclude patterns
        for pattern in rag_settings.exclude_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return False

        return True

    def has_secrets(self, content: str) -> bool:
        """Check if content contains potential secrets."""
        secret_patterns = [
            r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][^'\"]{10,}['\"]",
            r"(?i)(secret|password|token|credential)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
            r"(?i)bearer\s+[a-zA-Z0-9\-_.]+",
        ]
        for pattern in secret_patterns:
            if re.search(pattern, content):
                return True
        return False

    def chunk_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Chunk a single file into semantic units."""
        if not self.should_process_file(file_path):
            return []

        if self.has_secrets(content):
            print(f"Skipping {file_path}: potential secrets detected")
            return []

        chunks = code_parser.parse_file(file_path, content)

        # If no chunks extracted (parsing failed or unsupported),
        # fall back to whole file as single chunk
        if not chunks:
            chunks = [
                CodeChunk(
                    chunk_type="module",
                    name=Path(file_path).stem,
                    content=content[:5000],  # Limit size
                    file_path=file_path,
                    start_line=1,
                    end_line=content.count("\n") + 1,
                    language=code_parser.detect_language(file_path) or "unknown",
                )
            ]

        return chunks

    def chunk_directory(self, root_path: str, files: dict[str, str]) -> list[CodeChunk]:
        """Chunk all files in a directory.

        Args:
            root_path: Root path for relative file paths
            files: Dict of {relative_path: content}

        Returns:
            List of all chunks
        """
        all_chunks = []

        for file_path, content in files.items():
            chunks = self.chunk_file(file_path, content)
            all_chunks.extend(chunks)

        return all_chunks


# Singleton instance
chunker = Chunker()
```

---

### `src/rag/indexer.py`

```python
"""Codebase indexing orchestrator."""
import tempfile
import shutil
from pathlib import Path

from git import Repo

from src.app.services.github import GitHubService
from .chunker import chunker
from .embedder import embedder
from .vector_store import vector_store
from .config import rag_settings


class Indexer:
    """Orchestrate codebase indexing."""

    def __init__(self, github: GitHubService):
        self.github = github

    async def index_repository(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        installation_id: int | None = None,
    ) -> dict:
        """Index an entire repository.

        Returns:
            Stats about indexing: files_processed, chunks_created, etc.
        """
        namespace = f"{owner}/{repo}"
        stats = {
            "files_processed": 0,
            "chunks_created": 0,
            "files_skipped": 0,
        }

        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="rag_index_")

        try:
            # Clone repository (shallow)
            clone_url = await self._get_clone_url(owner, repo, installation_id)
            repo_path = Path(temp_dir) / repo

            Repo.clone_from(
                clone_url,
                repo_path,
                depth=1,
                branch=branch,
            )

            # Collect files
            files = {}
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(repo_path))

                    if not chunker.should_process_file(relative_path):
                        stats["files_skipped"] += 1
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8")
                        files[relative_path] = content
                        stats["files_processed"] += 1
                    except (UnicodeDecodeError, IOError):
                        stats["files_skipped"] += 1

            # Chunk all files
            chunks = chunker.chunk_directory(str(repo_path), files)
            stats["chunks_created"] = len(chunks)

            # Embed and store
            await self._embed_and_store(chunks, namespace)

        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

        return stats

    async def update_files(
        self,
        owner: str,
        repo: str,
        files: list[dict],  # [{filename, status, content}]
    ) -> dict:
        """Incrementally update index for changed files.

        Args:
            files: List of {filename, status: added|modified|removed, content}
        """
        namespace = f"{owner}/{repo}"
        stats = {"added": 0, "modified": 0, "removed": 0}

        for file_info in files:
            filename = file_info["filename"]
            status = file_info["status"]
            content = file_info.get("content")

            if status == "removed":
                # Delete vectors for this file
                vector_store.delete_by_file(namespace, filename)
                stats["removed"] += 1

            elif status in ("added", "modified"):
                # For modified files, delete old vectors first
                if status == "modified":
                    vector_store.delete_by_file(namespace, filename)

                # Parse and index new content
                if content:
                    chunks = chunker.chunk_file(filename, content)
                    await self._embed_and_store(chunks, namespace)
                    stats[status] += 1

        return stats

    async def _embed_and_store(
        self,
        chunks: list,
        namespace: str
    ) -> None:
        """Embed chunks and store in vector DB."""
        if not chunks:
            return

        # Prepare texts for embedding
        texts = [chunk.to_embedding_text() for chunk in chunks]

        # Batch embed
        batch_size = rag_settings.batch_size
        all_vectors = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_chunks = chunks[i:i + batch_size]

            embeddings = embedder.embed(batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings):
                all_vectors.append({
                    "id": chunk.id,
                    "values": embedding,
                    "metadata": {
                        "file_path": chunk.file_path,
                        "name": chunk.name,
                        "chunk_type": chunk.chunk_type,
                        "content": chunk.content[:1000],  # Truncate for metadata
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "language": chunk.language,
                    }
                })

        # Upsert to Pinecone
        vector_store.upsert(all_vectors, namespace)

    async def _get_clone_url(
        self,
        owner: str,
        repo: str,
        installation_id: int | None
    ) -> str:
        """Get authenticated clone URL."""
        if installation_id:
            token = await self.github.get_installation_token(installation_id)
            return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        return f"https://github.com/{owner}/{repo}.git"


# Factory function
def create_indexer(github: GitHubService) -> Indexer:
    return Indexer(github)
```

---

### `src/rag/retriever.py`

```python
"""Context retrieval from RAG."""
from src.ast.models import RelatedCode
from .embedder import embedder
from .vector_store import vector_store
from .config import rag_settings


class Retriever:
    """Retrieve related code context from indexed codebase."""

    def retrieve(
        self,
        owner: str,
        repo: str,
        query: str,
        exclude_file: str | None = None,
        top_k: int | None = None,
    ) -> list[RelatedCode]:
        """Retrieve related code for a query.

        Args:
            owner: Repo owner
            repo: Repo name
            query: Search query (function signature, code snippet, etc.)
            exclude_file: File to exclude from results (usually the file being reviewed)
            top_k: Number of results to return

        Returns:
            List of related code chunks
        """
        namespace = f"{owner}/{repo}"
        top_k = top_k or rag_settings.top_k

        # Embed query
        query_embedding = embedder.embed_single(query)

        # Build filter
        filter_dict = None
        if exclude_file:
            filter_dict = {"file_path": {"$ne": exclude_file}}

        # Query Pinecone
        results = vector_store.query(
            vector=query_embedding,
            namespace=namespace,
            top_k=top_k,
            filter=filter_dict,
        )

        # Convert to RelatedCode
        related = []
        for result in results:
            metadata = result["metadata"]

            # Infer relationship
            relationship = self._infer_relationship(
                query=query,
                result_name=metadata.get("name", ""),
                result_file=metadata.get("file_path", ""),
            )

            related.append(RelatedCode(
                file_path=metadata.get("file_path", ""),
                name=metadata.get("name", ""),
                content=metadata.get("content", ""),
                chunk_type=metadata.get("chunk_type", ""),
                relevance_score=result["score"],
                relationship=relationship,
            ))

        return related

    def retrieve_for_function(
        self,
        owner: str,
        repo: str,
        function_name: str,
        signature: str | None = None,
        current_file: str | None = None,
    ) -> list[RelatedCode]:
        """Retrieve context for a specific function."""
        # Build rich query
        query_parts = [f"function {function_name}"]
        if signature:
            query_parts.append(f"signature: {signature}")

        query = " ".join(query_parts)

        return self.retrieve(
            owner=owner,
            repo=repo,
            query=query,
            exclude_file=current_file,
        )

    def _infer_relationship(
        self,
        query: str,
        result_name: str,
        result_file: str
    ) -> str:
        """Infer the relationship between query and result."""
        # Check if it's a test file
        if "test" in result_file.lower():
            return "test"

        # Check if names match (caller/callee)
        query_lower = query.lower()
        if result_name.lower() in query_lower:
            return "callee"

        # Default to similar
        return "similar"


# Singleton instance
retriever = Retriever()
```

---

## 🔜 Next: Integration Plan

Xem [04-integration-plan.md](./04-integration-plan.md) để hiểu cách integrate vào existing code.
