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


@dataclass(slots=True)
class ParameterInfo:
    """Information about a function parameter."""

    name: str
    type_hint: str | None = None
    default_value: str | None = None
    is_variadic: bool = False  # *args
    is_keyword: bool = False  # **kwargs


@dataclass(slots=True)
class FunctionInfo:
    """Information about a function/method.

    Enhanced with Python 3.13 features for comprehensive AST extraction.
    """

    name: str
    signature: str | None
    start_line: int
    end_line: int

    # Enhanced fields for RAG context
    parameters: list[ParameterInfo] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    docstring: str | None = None

    def format_for_context(self) -> str:
        """Format function info for LLM context."""
        parts = [f"{'async ' if self.is_async else ''}def {self.name}"]

        if self.parameters:
            params = ", ".join(
                f"{p.name}: {p.type_hint}" if p.type_hint else p.name for p in self.parameters
            )
            parts.append(f"({params})")
        else:
            parts.append("()")

        if self.return_type:
            parts.append(f" -> {self.return_type}")

        return "".join(parts)


@dataclass(slots=True)
class ClassInfo:
    """Information about a class.

    Enhanced with inheritance and decorator info for RAG context.
    """

    name: str
    methods: list[str]
    start_line: int
    end_line: int

    # Enhanced fields
    base_classes: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    class_variables: list[str] = field(default_factory=list)

    def format_for_context(self) -> str:
        """Format class info for LLM context."""
        parts = [f"class {self.name}"]

        if self.base_classes:
            parts.append(f"({', '.join(self.base_classes)})")

        return "".join(parts)


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
    start_line: int = 0
    end_line: int = 0
