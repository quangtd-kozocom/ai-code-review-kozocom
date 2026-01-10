"""AST data models."""

import json
from dataclasses import dataclass, field
from typing import Literal

type ChunkType = Literal["function", "class", "method", "import", "module", "module_header"]
type RelationshipType = Literal["caller", "callee", "similar", "test", "sibling", "transitive"]


@dataclass(slots=True)
class CodeChunk:
    """Represents a parseable unit of code."""

    chunk_type: ChunkType
    name: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str

    signature: str | None = field(default=None, kw_only=True)
    docstring: str | None = field(default=None, kw_only=True)
    dependencies: list[str] = field(default_factory=list, kw_only=True)
    parameters: list["ParameterInfo"] = field(default_factory=list, kw_only=True)
    imports: list[str] = field(default_factory=list, kw_only=True)
    calls: list[str] = field(default_factory=list, kw_only=True)

    @property
    def id(self) -> str:
        """Generate unique ID for this chunk."""
        return f"{self.file_path}:{self.name}:{self.start_line}"

    @property
    def parameters_json(self) -> str | None:
        """Serialize parameters to JSON string."""
        if not self.parameters:
            return None
        return json.dumps(
            [
                {
                    "name": p.name,
                    "type_hint": p.type_hint,
                    "default_value": p.default_value,
                    "is_variadic": p.is_variadic,
                    "is_keyword": p.is_keyword,
                }
                for p in self.parameters
            ]
        )

    def to_context_text(self) -> str:
        """Convert chunk to text for LLM context."""
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
    """Information about a function/method."""

    name: str
    signature: str | None
    start_line: int
    end_line: int

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
    """Information about a class."""

    name: str
    methods: list[str]
    start_line: int
    end_line: int

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
    changed_entities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RelatedCode:
    """Related code retrieved from RAG."""

    file_path: str
    name: str
    content: str
    chunk_type: str
    relevance_score: float
    relationship: RelationshipType
    start_line: int = 0
    end_line: int = 0
