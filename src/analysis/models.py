"""Data models for code analysis.

Consolidated models for AST analysis, replacing the old src.ast.models module.
"""

from dataclasses import dataclass, field
from typing import Literal

type ChunkType = Literal["function", "class", "method", "import", "module", "module_header"]


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


# Language detection mapping
LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".php": "php",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "c_sharp",
}


def detect_language(file_path: str) -> str | None:
    """Detect language from file extension."""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(ext)


def get_grammar_name(file_path: str) -> str | None:
    """Get tree-sitter grammar name for a file."""
    lang = detect_language(file_path)
    if not lang:
        return None
    
    # Map common language names to tree-sitter grammar names
    grammar_map = {
        "javascript": "javascript",
        "typescript": "typescript",
        "tsx": "tsx",
        "python": "python",
        "php": "php",
        "ruby": "ruby",
        "go": "go",
        "rust": "rust",
        "java": "java",
        "kotlin": "kotlin",
        "swift": "swift",
        "c": "c",
        "cpp": "cpp",
        "c_sharp": "c_sharp",
    }
    return grammar_map.get(lang, lang)
