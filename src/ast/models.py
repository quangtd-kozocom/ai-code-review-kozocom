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

    # Optional metadata
    signature: str | None = None
    docstring: str | None = None
    dependencies: list[str] = field(default_factory=list)

    # Relationship data for RAG v2
    imports: list[str] = field(default_factory=list)  # File-level imports
    calls: list[str] = field(default_factory=list)  # Function calls in this chunk

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
