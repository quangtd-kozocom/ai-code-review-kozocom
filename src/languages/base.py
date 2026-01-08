"""Language plugin interface.

This module defines the base class for language-specific parsing plugins.
Each supported programming language implements this interface to provide:
- File extension mapping
- AST node extraction types
- Import parsing
- Function call parsing
- Test file pattern generation
"""

from abc import ABC, abstractmethod


class LanguagePlugin(ABC):
    """Base class for language-specific parsing.

    Subclasses must implement all abstract methods to provide
    language-specific parsing capabilities for the RAG system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Language name: 'python', 'javascript', 'php'.

        Returns:
            Lowercase language identifier string.
        """
        ...

    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        """File extensions: ('.py',) or ('.js', '.jsx', '.ts', '.tsx').

        Returns:
            Tuple of file extensions including the leading dot.
        """
        ...

    @property
    @abstractmethod
    def tree_sitter_name(self) -> str:
        """Tree-sitter grammar name.

        Returns:
            Grammar name for tree-sitter-language-pack.
        """
        ...

    @property
    @abstractmethod
    def extract_node_types(self) -> set[str]:
        """AST node types to extract as chunks.

        Returns:
            Set of tree-sitter node type names to extract.
        """
        ...

    @abstractmethod
    def parse_imports(self, content: str) -> list[str]:
        """Extract imported modules/files from source code.

        Args:
            content: Complete source file content.

        Returns:
            List of imported module/file names.
        """
        ...

    @abstractmethod
    def parse_calls(self, content: str) -> list[str]:
        """Extract function/method calls from source code.

        Args:
            content: Source code (can be a chunk or full file).

        Returns:
            List of called function/method names.
        """
        ...

    @abstractmethod
    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate possible test file paths for a source file.

        Args:
            file_path: Path to the source file.

        Returns:
            List of potential test file paths to search.
        """
        ...

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract function signature from AST node.

        Optional override for language-specific signature extraction.

        Args:
            node: Tree-sitter AST node.
            content_bytes: File content as bytes.

        Returns:
            Function signature string or None.
        """
        return None

    def extract_docstring(self, node, content_bytes: bytes) -> str | None:
        """Extract docstring from AST node.

        Optional override for language-specific docstring extraction.

        Args:
            node: Tree-sitter AST node.
            content_bytes: File content as bytes.

        Returns:
            Docstring content or None.
        """
        return None
