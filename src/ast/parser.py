"""AST parsing using language plugins.

This module provides tree-sitter based code parsing with language plugin support.
It extracts code chunks (functions, classes, methods) with their imports and calls.

Enhanced for Python 3.13+ with comprehensive extraction for RAG context.
"""

from dataclasses import dataclass
from functools import cache

import structlog
import tree_sitter_language_pack as ts_pack

from src.languages import get_plugin_for_file

from .models import ASTInfo, ClassInfo, CodeChunk, FunctionInfo

log = structlog.get_logger()


@dataclass(slots=True)
class ParseResult:
    """Result of parsing a file."""

    chunks: list[CodeChunk]
    imports: list[str]


class CodeParser:
    """Parse source code using language plugins.

    This parser extracts code chunks (functions, classes) with their
    imports and function calls for relationship-based RAG retrieval.

    Enhanced to extract:
    - Type hints (parameters, return types)
    - Decorators
    - Async function detection
    - Class inheritance
    - Full docstrings
    """

    def parse(self, file_path: str, content: str) -> ParseResult | None:
        """Parse file into chunks with imports and calls.

        Args:
            file_path: Path to the file.
            content: File content.

        Returns:
            ParseResult with chunks and imports, or None if unsupported.
        """
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
        # Get grammar name - use file-specific method if available (e.g., TypeScript)
        grammar_name = (
            plugin.get_grammar_for_file(file_path)
            if hasattr(plugin, "get_grammar_for_file")
            else plugin.tree_sitter_name
        )

        try:
            parser = ts_pack.get_parser(grammar_name)
            tree = parser.parse(content.encode())
            return self._walk_tree(tree.root_node, file_path, content.encode(), plugin)
        except Exception as e:
            log.warning("parse_failed", file=file_path, error=str(e), grammar=grammar_name)
            return []

    def _walk_tree(self, root, file_path: str, content_bytes: bytes, plugin) -> list[CodeChunk]:
        """Walk AST and extract matching nodes."""
        chunks: list[CodeChunk] = []

        def walk(node) -> None:
            if node.type in plugin.extract_node_types:
                if chunk := self._node_to_chunk(node, file_path, content_bytes, plugin):
                    chunks.append(chunk)
            for child in node.children:
                walk(child)

        walk(root)
        return chunks

    def _node_to_chunk(
        self, node, file_path: str, content_bytes: bytes, plugin
    ) -> CodeChunk | None:
        """Convert AST node to CodeChunk."""
        content = content_bytes[node.start_byte : node.end_byte].decode()

        # Extract name
        name = None
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                name = child.text.decode()
                break

        if not name:
            return None

        # Determine chunk type
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

    def parse_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Parse a file and return code chunks.

        Convenience method that returns just the chunks.

        Args:
            file_path: Path to the file.
            content: File content.

        Returns:
            List of CodeChunk objects.
        """
        result = self.parse(file_path, content)
        return result.chunks if result else []

    def detect_language(self, file_path: str) -> str | None:
        """Detect tree-sitter grammar name from file extension.

        Args:
            file_path: Path to the file.

        Returns:
            Tree-sitter grammar name or None if unsupported.
        """
        plugin = get_plugin_for_file(file_path)
        return plugin.tree_sitter_name if plugin else None

    def get_ast_info(self, file_path: str, content: str) -> ASTInfo | None:
        """Get structured AST info for a file.

        Enhanced to extract comprehensive information for RAG context:
        - Type hints (parameters, return types)
        - Decorators
        - Async function detection
        - Class inheritance
        - Full docstrings

        Args:
            file_path: Path to the file.
            content: File content.

        Returns:
            ASTInfo with functions, classes, and imports.
        """
        plugin = get_plugin_for_file(file_path)
        if not plugin:
            return None

        # Get grammar and parse tree
        grammar_name = (
            plugin.get_grammar_for_file(file_path)
            if hasattr(plugin, "get_grammar_for_file")
            else plugin.tree_sitter_name
        )

        try:
            parser = ts_pack.get_parser(grammar_name)
            tree = parser.parse(content.encode())
        except Exception as e:
            log.warning("parse_failed", file=file_path, error=str(e))
            return None

        content_bytes = content.encode()
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []

        # Walk tree and extract enhanced info
        def walk(node) -> None:
            match node.type:
                case "function_definition":
                    if func_info := self._extract_function_info(node, content_bytes, plugin):
                        functions.append(func_info)

                case "class_definition":
                    if class_info := self._extract_class_info(node, content_bytes, plugin):
                        classes.append(class_info)

            for child in node.children:
                walk(child)

        walk(tree.root_node)

        return ASTInfo(
            file_path=file_path,
            language=plugin.name,
            functions=functions,
            classes=classes,
            imports=plugin.parse_imports(content),
        )

    def _extract_function_info(self, node, content_bytes: bytes, plugin) -> FunctionInfo | None:
        """Extract enhanced FunctionInfo from AST node."""
        # Get function name
        name = None
        for child in node.children:
            if child.type == "identifier":
                name = child.text.decode()
                break

        if not name:
            return None

        # Use plugin's enhanced extraction if available
        if hasattr(plugin, "get_function_details"):
            details = plugin.get_function_details(node, content_bytes)
            return FunctionInfo(
                name=name,
                signature=details.get("signature"),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parameters=details.get("parameters", []),
                return_type=details.get("return_type"),
                decorators=details.get("decorators", []),
                is_async=details.get("is_async", False),
                docstring=details.get("docstring"),
            )

        # Fallback for plugins without enhanced extraction
        return FunctionInfo(
            name=name,
            signature=plugin.extract_signature(node, content_bytes),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            docstring=plugin.extract_docstring(node, content_bytes),
        )

    def _extract_class_info(self, node, content_bytes: bytes, plugin) -> ClassInfo | None:
        """Extract enhanced ClassInfo from AST node."""
        # Get class name
        name = None
        for child in node.children:
            if child.type == "identifier":
                name = child.text.decode()
                break

        if not name:
            return None

        # Use plugin's enhanced extraction if available
        if hasattr(plugin, "get_class_details"):
            details = plugin.get_class_details(node, content_bytes)
            return ClassInfo(
                name=name,
                methods=details.get("methods", []),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                base_classes=details.get("base_classes", []),
                decorators=details.get("decorators", []),
                docstring=details.get("docstring"),
                class_variables=details.get("class_variables", []),
            )

        # Fallback for plugins without enhanced extraction
        return ClassInfo(
            name=name,
            methods=[],
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )


@cache
def get_code_parser() -> CodeParser:
    """Factory function to get CodeParser instance (cached)."""
    return CodeParser()


def reset_code_parser() -> None:
    """Reset the cached parser instance (for testing)."""
    get_code_parser.cache_clear()
