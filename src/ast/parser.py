"""Tree-sitter based code parser."""

import structlog
import tree_sitter_language_pack as ts_pack

from ..core.constants import get_treesitter_language
from .models import ASTInfo, ClassInfo, CodeChunk, FunctionInfo

log = structlog.get_logger()


class CodeParser:
    """Parse source code using Tree-sitter."""

    def detect_language(self, file_path: str) -> str | None:
        """Detect tree-sitter grammar name from file extension."""
        return get_treesitter_language(file_path)

    def parse_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Parse a file and extract code chunks."""
        language = self.detect_language(file_path)
        if not language:
            return []

        try:
            parser = ts_pack.get_parser(language)
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
        language: str,
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

    # AST node types to extract per language
    EXTRACT_TYPES: dict[str, set[str]] = {
        "python": {"function_definition", "class_definition"},
        "javascript": {
            "function_declaration",
            "class_declaration",
            "arrow_function",
            "method_definition",
        },
        "typescript": {
            "function_declaration",
            "class_declaration",
            "arrow_function",
            "method_definition",
        },
        "tsx": {"function_declaration", "class_declaration", "arrow_function", "method_definition"},
        "go": {"function_declaration", "method_declaration", "type_declaration"},
        "rust": {"function_item", "impl_item", "struct_item", "enum_item"},
        "java": {"method_declaration", "class_declaration", "interface_declaration"},
        "kotlin": {"function_declaration", "class_declaration"},
        "scala": {"function_definition", "class_definition", "object_definition"},
        "php": {"function_definition", "class_declaration", "method_declaration"},
        "ruby": {"method", "class", "module"},
        "c": {"function_definition", "struct_specifier"},
        "cpp": {"function_definition", "class_specifier", "struct_specifier"},
        "swift": {"function_declaration", "class_declaration", "struct_declaration"},
    }

    # Default fallback for unsupported languages
    DEFAULT_EXTRACT_TYPES: set[str] = {
        "function_definition",
        "function_declaration",
        "class_definition",
        "class_declaration",
        "method_definition",
        "method_declaration",
    }

    def _get_extract_types(self, language: str) -> set[str]:
        """Get node types to extract for a language."""
        return self.EXTRACT_TYPES.get(language, self.DEFAULT_EXTRACT_TYPES)

    def _node_to_chunk(
        self,
        node,
        file_path: str,
        content: str,
        language: str,
    ) -> CodeChunk | None:
        """Convert AST node to CodeChunk."""
        content_bytes = content.encode()
        chunk_content = content_bytes[node.start_byte : node.end_byte].decode()

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
            first_line = content_bytes[node.start_byte :].split(b"\n")[0]
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
                                    return expr.text.decode().strip("\"' ")
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
                functions.append(
                    FunctionInfo(
                        name=chunk.name,
                        signature=chunk.signature,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                    )
                )
            elif chunk.chunk_type == "class":
                classes.append(
                    ClassInfo(
                        name=chunk.name,
                        methods=[],  # Could be populated by further parsing
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                    )
                )

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
