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
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """RAG-related settings."""

    # Pinecone
    pinecone_api_key: str = ""
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

    model_config = SettingsConfigDict(env_file=".env", env_prefix="")


@lru_cache
def get_rag_settings() -> RAGSettings:
    """Factory function to get RAG settings (cached)."""
    return RAGSettings()
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
class FunctionInfo:
    """Information about a function/method."""

    name: str
    signature: str | None
    start_line: int
    end_line: int


@dataclass
class ClassInfo:
    """Information about a class."""

    name: str
    methods: list[str]
    start_line: int
    end_line: int


@dataclass
class ASTInfo:
    """Parsed AST information for a file."""

    file_path: str
    language: str
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
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
import structlog
import tree_sitter_languages
from pathlib import Path

from .models import CodeChunk, ASTInfo, FunctionInfo, ClassInfo

log = structlog.get_logger()


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
            log.warning("failed_to_parse_file", file_path=file_path, error=str(e))
            return []

    def _extract_chunks(
        self,
        node,
        file_path: str,
        content: str,
        language: str
    ) -> list[CodeChunk]:
        """Extract code chunks from AST node."""
        chunks: list[CodeChunk] = []

        # Define node types to extract per language
        extract_types = self._get_extract_types(language)

        def walk(node) -> None:
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

        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []

        for chunk in chunks:
            if chunk.chunk_type in ("function", "method"):
                functions.append(FunctionInfo(
                    name=chunk.name,
                    signature=chunk.signature,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                ))
            elif chunk.chunk_type == "class":
                classes.append(ClassInfo(
                    name=chunk.name,
                    methods=[],  # Could be populated by further parsing
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                ))

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
        imports: list[str] = []
        for line in content.split("\n"):
            line = line.strip()
            if language == "python":
                if line.startswith("import ") or line.startswith("from "):
                    imports.append(line)
            elif language in ("javascript", "typescript"):
                if line.startswith("import "):
                    imports.append(line)
        return imports


def get_code_parser() -> CodeParser:
    """Factory function to get CodeParser instance."""
    return CodeParser()
```

---

### `src/rag/embedder.py`

```python
"""Embedding service using OpenAI."""
import structlog
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APIError

from .config import get_rag_settings

log = structlog.get_logger()


class Embedder:
    """Generate embeddings using OpenAI API."""

    def __init__(self) -> None:
        settings = get_rag_settings()
        if not settings.pinecone_api_key:
            log.warning("openai_api_key_not_configured")
        self.client = OpenAI()
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=lambda retry_state: log.warning(
            "embedding_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
        ),
    )
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
        result = self.embed([text])
        if not result:
            raise ValueError("Failed to generate embedding")
        return result[0]


def get_embedder() -> Embedder:
    """Factory function to get Embedder instance."""
    return Embedder()
```

---

### `src/rag/vector_store.py`

```python
"""Pinecone vector store wrapper."""
import structlog
from pinecone import Pinecone, ServerlessSpec

from .config import get_rag_settings

log = structlog.get_logger()


class VectorStore:
    """Pinecone vector store operations."""

    def __init__(self) -> None:
        settings = get_rag_settings()
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self._index = None
        self._settings = settings

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
                    dimension=self._settings.embedding_dimensions,
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
        batch_size = self._settings.batch_size
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
        """Delete all vectors for a specific file.

        Note: Pinecone serverless doesn't support delete by metadata filter.
        We use ID prefix strategy instead: ID format is "file_path:name:line"
        """
        # Query to find all vector IDs for this file
        # Then delete by IDs
        try:
            # List vectors with the file_path prefix
            # Since IDs start with file_path, we can use prefix deletion
            prefix = f"{file_path}:"
            self.index.delete(
                ids=[],  # Empty - will use filter below
                namespace=namespace,
                filter={"file_path": {"$eq": file_path}},
            )
        except Exception as e:
            # Fallback: If filter delete not supported, log warning
            # In production, implement ID-based deletion by querying first
            log.warning(
                "delete_by_filter_not_supported",
                namespace=namespace,
                file_path=file_path,
                error=str(e),
            )
            # Alternative approach: query and delete by IDs
            self._delete_by_file_via_query(namespace, file_path)

    def _delete_by_file_via_query(self, namespace: str, file_path: str) -> None:
        """Fallback: Delete vectors by querying first then deleting by IDs."""
        # This is a workaround for Pinecone serverless limitations
        # In practice, you might want to maintain a separate index of file -> vector IDs
        log.info("delete_by_file_via_query", namespace=namespace, file_path=file_path)
        # Implementation would query vectors and delete by ID batches

    def delete_namespace(self, namespace: str) -> None:
        """Delete entire namespace (all vectors for a repo)."""
        self.index.delete(delete_all=True, namespace=namespace)


def get_vector_store() -> VectorStore:
    """Factory function to get VectorStore instance."""
    return VectorStore()
```

---

### `src/rag/chunker.py`

```python
"""Code chunking logic."""
import fnmatch
import re
import structlog
from pathlib import Path

from src.ast.parser import get_code_parser
from src.ast.models import CodeChunk
from .config import get_rag_settings

log = structlog.get_logger()


class Chunker:
    """Smart code chunking using AST."""

    def __init__(self) -> None:
        self._settings = get_rag_settings()
        self._parser = get_code_parser()

    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed."""
        # Check extension
        ext = Path(file_path).suffix.lower()
        # Normalize extensions (handle both ".py" and "py" formats)
        allowed_extensions = {
            ext if ext.startswith(".") else f".{ext}"
            for ext in self._settings.include_extensions
        }
        if ext not in allowed_extensions:
            return False

        # Check exclude patterns
        for pattern in self._settings.exclude_patterns:
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
            log.warning("skipping_file_with_secrets", file_path=file_path)
            return []

        chunks = self._parser.parse_file(file_path, content)

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
                    language=self._parser.detect_language(file_path) or "unknown",
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
        all_chunks: list[CodeChunk] = []

        for file_path, content in files.items():
            chunks = self.chunk_file(file_path, content)
            all_chunks.extend(chunks)

        return all_chunks


def get_chunker() -> Chunker:
    """Factory function to get Chunker instance."""
    return Chunker()
```

---

### `src/rag/indexer.py`

```python
"""Codebase indexing orchestrator."""
import asyncio
import shutil
import structlog
import tempfile
from pathlib import Path

from git import Repo

from src.app.services.github import GitHubService
from .chunker import get_chunker
from .embedder import get_embedder
from .vector_store import get_vector_store
from .config import get_rag_settings

log = structlog.get_logger()


class Indexer:
    """Orchestrate codebase indexing."""

    def __init__(self, github: GitHubService) -> None:
        self.github = github
        self._chunker = get_chunker()
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._settings = get_rag_settings()

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
            # Clone repository (shallow) - use asyncio.to_thread for blocking I/O
            clone_url = await self._get_clone_url(owner, repo, installation_id)
            repo_path = Path(temp_dir) / repo

            await asyncio.to_thread(
                Repo.clone_from,
                clone_url,
                repo_path,
                depth=1,
                branch=branch,
            )

            # Collect files
            files: dict[str, str] = {}
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(repo_path))

                    if not self._chunker.should_process_file(relative_path):
                        stats["files_skipped"] += 1
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8")
                        files[relative_path] = content
                        stats["files_processed"] += 1
                    except (UnicodeDecodeError, IOError):
                        stats["files_skipped"] += 1

            # Chunk all files
            chunks = self._chunker.chunk_directory(str(repo_path), files)
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
                self._vector_store.delete_by_file(namespace, filename)
                stats["removed"] += 1

            elif status in ("added", "modified"):
                # For modified files, delete old vectors first
                if status == "modified":
                    self._vector_store.delete_by_file(namespace, filename)

                # Parse and index new content
                if content:
                    chunks = self._chunker.chunk_file(filename, content)
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
        batch_size = self._settings.batch_size
        all_vectors: list[dict] = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_chunks = chunks[i:i + batch_size]

            embeddings = self._embedder.embed(batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings, strict=True):
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
        self._vector_store.upsert(all_vectors, namespace)

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


def create_indexer(github: GitHubService) -> Indexer:
    """Factory function to create Indexer instance."""
    return Indexer(github)
```

---

### `src/rag/retriever.py`

```python
"""Context retrieval from RAG."""
from src.ast.models import RelatedCode
from .embedder import get_embedder
from .vector_store import get_vector_store
from .config import get_rag_settings


class Retriever:
    """Retrieve related code context from indexed codebase."""

    def __init__(self) -> None:
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._settings = get_rag_settings()

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
        top_k = top_k or self._settings.top_k

        # Embed query
        query_embedding = self._embedder.embed_single(query)

        # Build filter
        filter_dict = None
        if exclude_file:
            filter_dict = {"file_path": {"$ne": exclude_file}}

        # Query Pinecone
        results = self._vector_store.query(
            vector=query_embedding,
            namespace=namespace,
            top_k=top_k,
            filter=filter_dict,
        )

        # Convert to RelatedCode
        related: list[RelatedCode] = []
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


def get_retriever() -> Retriever:
    """Factory function to get Retriever instance."""
    return Retriever()
```

---

## 🔜 Next: Integration Plan

Xem [04-integration-plan.md](./04-integration-plan.md) để hiểu cách integrate vào existing code.
