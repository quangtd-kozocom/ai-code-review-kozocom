"""Python language plugin.

Provides Python-specific parsing for:
- Import extraction (import X, from X import Y, relative imports)
- Function call detection using AST
- Type hints extraction (parameters, return types)
- Decorator extraction
- Async function detection
- Test file pattern generation (test_*.py, *_test.py)

Enhanced for Python 3.13+ with modern syntax and comprehensive AST extraction.
"""

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .base import LanguagePlugin

if TYPE_CHECKING:
    from src.ast.models import ParameterInfo


class PythonPlugin(LanguagePlugin):
    """Python language plugin implementation.

    Enhanced with comprehensive extraction for RAG context:
    - Type hints (parameters, return types)
    - Decorators (@property, @staticmethod, etc.)
    - Async functions
    - Class inheritance
    - Full docstrings
    """

    # Built-in functions to filter from calls
    BUILTINS = frozenset(
        {
            "print",
            "len",
            "range",
            "str",
            "int",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "open",
            "type",
            "isinstance",
            "issubclass",
            "hasattr",
            "getattr",
            "setattr",
            "delattr",
            "callable",
            "super",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "enumerate",
            "all",
            "any",
            "min",
            "max",
            "sum",
            "abs",
            "round",
            "pow",
            "divmod",
            "hex",
            "oct",
            "bin",
            "chr",
            "ord",
            "repr",
            "hash",
            "id",
            "bool",
            "bytes",
            "bytearray",
            "memoryview",
            "complex",
            "frozenset",
            "object",
            "property",
            "staticmethod",
            "classmethod",
            "vars",
            "dir",
            "locals",
            "globals",
            "exec",
            "eval",
            "compile",
            "input",
            "format",
            "iter",
            "next",
            "slice",
            "ascii",
            "breakpoint",
        }
    )

    @property
    def name(self) -> str:
        return "python"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".py",)

    @property
    def tree_sitter_name(self) -> str:
        return "python"

    @property
    def extract_node_types(self) -> set[str]:
        return {"function_definition", "class_definition"}

    def parse_imports(self, content: str) -> list[str]:
        """Parse Python imports.

        Handles:
        - import os
        - import os, sys
        - from typing import List
        - from src.utils import helper
        - from .models import User (relative)
        """
        imports: list[str] = []
        for line in content.split("\n"):
            line = line.strip()

            # Skip comments
            if line.startswith("#"):
                continue

            # Handle "import X" or "import X, Y"
            if line.startswith("import "):
                parts = line[7:].split(",")
                for part in parts:
                    module = part.strip().split()[0].split(".")[0]
                    if module:
                        imports.append(module)

            # Handle "from X import Y"
            elif line.startswith("from "):
                if match := re.match(r"from\s+([\w.]+)\s+import", line):
                    imports.append(match.group(1))

        return list(set(imports))

    def parse_calls(self, content: str) -> list[str]:
        """Parse Python function calls using ast module."""
        calls: list[str] = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    match node.func:
                        case ast.Name(id=name):
                            calls.append(name)
                        case ast.Attribute(attr=attr):
                            calls.append(attr)
        except SyntaxError:
            # Fall back to regex for invalid syntax
            pattern = r"(\w+)\s*\("
            calls = re.findall(pattern, content)

        return [c for c in set(calls) if c not in self.BUILTINS]

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns for Python.

        Conventions:
        - tests/test_{name}.py
        - tests/{parent}/test_{name}.py
        - test_{name}.py
        - {parent}/test_{name}.py
        """
        path = Path(file_path)
        stem = path.stem
        parent = str(path.parent)

        # Normalize parent path
        if parent == ".":
            parent = ""

        patterns = [
            f"tests/test_{stem}.py",
            f"test_{stem}.py",
        ]

        if parent:
            patterns.extend(
                [
                    f"tests/{parent}/test_{stem}.py",
                    f"{parent}/test_{stem}.py",
                ]
            )

        return patterns

    # =========================================================================
    # Enhanced extraction methods for RAG context
    # =========================================================================

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract complete function/class signature including decorators."""
        lines: list[str] = []
        text = content_bytes[node.start_byte : node.end_byte].decode()

        # Get parent node to check for decorators
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                lines.append(stripped)
                break
            if stripped.startswith("class "):
                lines.append(stripped)
                break

        return lines[0] if lines else None

    def extract_docstring(self, node, content_bytes: bytes) -> str | None:
        """Extract FULL docstring from function/class.

        Properly handles triple-quoted strings and multiline docstrings.
        Handles both expression_statement wrapped and direct string nodes.
        """
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    # Direct string node (tree-sitter may parse docstrings directly)
                    if stmt.type == "string":
                        text = stmt.text.decode()
                        return self._clean_docstring(text)

                    # expression_statement wrapper (older tree-sitter versions)
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "string":
                                text = expr.text.decode()
                                return self._clean_docstring(text)
                        # If first statement is not a docstring, break
                        break

                    # If first non-trivial statement is not string/expression, no docstring
                    if stmt.type not in ("comment", "newline"):
                        break
                break
        return None

    def _clean_docstring(self, text: str) -> str:
        """Clean docstring by removing quotes and normalizing whitespace."""
        # Handle triple-quoted strings
        if text.startswith('"""') and text.endswith('"""'):
            return text[3:-3].strip()
        if text.startswith("'''") and text.endswith("'''"):
            return text[3:-3].strip()
        # Handle single-quoted strings
        if text.startswith('"') and text.endswith('"'):
            return text[1:-1].strip()
        if text.startswith("'") and text.endswith("'"):
            return text[1:-1].strip()
        return text.strip()

    def extract_decorators(self, node, content_bytes: bytes) -> list[str]:
        """Extract decorator names from function/class node.

        Returns list of decorator names without @ symbol.
        """
        decorators: list[str] = []

        for child in node.children:
            if child.type == "decorator":
                decorator_text = content_bytes[child.start_byte : child.end_byte].decode()
                # Clean up decorator: remove @ and arguments
                clean = decorator_text.strip().lstrip("@")
                # Remove arguments if present: @decorator(args) -> decorator
                if "(" in clean:
                    clean = clean[: clean.index("(")]
                decorators.append(clean.strip())

        return decorators

    def extract_parameters(self, node, content_bytes: bytes) -> list["ParameterInfo"]:
        """Extract function parameters with type hints.

        Returns list of ParameterInfo with name, type_hint, and flags.
        """
        from src.ast.models import ParameterInfo

        parameters: list[ParameterInfo] = []

        # Find parameters node
        params_node = None
        for child in node.children:
            if child.type == "parameters":
                params_node = child
                break

        if not params_node:
            return parameters

        for child in params_node.children:
            param = self._parse_single_parameter(child, content_bytes)
            if param:
                parameters.append(param)

        return parameters

    def _parse_single_parameter(self, node, content_bytes: bytes) -> "ParameterInfo | None":
        """Parse a single parameter node into ParameterInfo."""
        from src.ast.models import ParameterInfo

        match node.type:
            case "identifier":
                name = node.text.decode()
                if name in ("self", "cls"):
                    return None
                return ParameterInfo(name=name)

            case "typed_parameter":
                name = None
                type_hint = None
                for child in node.children:
                    match child.type:
                        case "identifier":
                            name = child.text.decode()
                        case "type":
                            type_hint = child.text.decode()
                if name and name not in ("self", "cls"):
                    return ParameterInfo(name=name, type_hint=type_hint)

            case "default_parameter":
                name = None
                type_hint = None
                default_value = None
                for child in node.children:
                    match child.type:
                        case "identifier":
                            name = child.text.decode()
                        case "type":
                            type_hint = child.text.decode()
                        case _:
                            if child.type not in ("=", "typed_parameter"):
                                default_value = child.text.decode()
                if name and name not in ("self", "cls"):
                    return ParameterInfo(
                        name=name, type_hint=type_hint, default_value=default_value
                    )

            case "typed_default_parameter":
                name = None
                type_hint = None
                default_value = None
                for child in node.children:
                    match child.type:
                        case "identifier":
                            name = child.text.decode()
                        case "type":
                            type_hint = child.text.decode()
                        case _ if child.type not in (":", "="):
                            default_value = child.text.decode()
                if name and name not in ("self", "cls"):
                    return ParameterInfo(
                        name=name, type_hint=type_hint, default_value=default_value
                    )

            case "list_splat_pattern":
                # *args
                for child in node.children:
                    if child.type == "identifier":
                        return ParameterInfo(name=child.text.decode(), is_variadic=True)

            case "dictionary_splat_pattern":
                # **kwargs
                for child in node.children:
                    if child.type == "identifier":
                        return ParameterInfo(name=child.text.decode(), is_keyword=True)

        return None

    def extract_return_type(self, node, content_bytes: bytes) -> str | None:
        """Extract return type annotation from function."""
        for child in node.children:
            if child.type == "type":
                return child.text.decode()
        return None

    def is_async_function(self, node) -> bool:
        """Check if function is async."""
        # Check node text starts with 'async'
        if hasattr(node, "text"):
            text = node.text.decode() if isinstance(node.text, bytes) else node.text
            return text.strip().startswith("async ")
        return False

    def extract_base_classes(self, node, content_bytes: bytes) -> list[str]:
        """Extract base classes from class definition."""
        base_classes: list[str] = []

        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        base_classes.append(arg.text.decode())
                    elif arg.type == "attribute":
                        base_classes.append(content_bytes[arg.start_byte : arg.end_byte].decode())
        return base_classes

    def extract_class_variables(self, node, content_bytes: bytes) -> list[str]:
        """Extract class-level variable assignments."""
        variables: list[str] = []

        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "assignment":
                                for target in expr.children:
                                    if target.type == "identifier":
                                        variables.append(target.text.decode())
                                        break
        return variables

    def extract_method_names(self, node, content_bytes: bytes) -> list[str]:
        """Extract method names from class definition."""
        methods: list[str] = []

        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "function_definition":
                        for subchild in stmt.children:
                            if subchild.type == "identifier":
                                methods.append(subchild.text.decode())
                                break
        return methods

    def get_function_details(self, node, content_bytes: bytes) -> dict:
        """Extract comprehensive function details for RAG context.

        Returns dict with all extracted information for FunctionInfo.
        """
        return {
            "decorators": self.extract_decorators(node, content_bytes),
            "parameters": self.extract_parameters(node, content_bytes),
            "return_type": self.extract_return_type(node, content_bytes),
            "is_async": self.is_async_function(node),
            "docstring": self.extract_docstring(node, content_bytes),
            "signature": self.extract_signature(node, content_bytes),
        }

    def get_class_details(self, node, content_bytes: bytes) -> dict:
        """Extract comprehensive class details for RAG context.

        Returns dict with all extracted information for ClassInfo.
        """
        return {
            "decorators": self.extract_decorators(node, content_bytes),
            "base_classes": self.extract_base_classes(node, content_bytes),
            "docstring": self.extract_docstring(node, content_bytes),
            "methods": self.extract_method_names(node, content_bytes),
            "class_variables": self.extract_class_variables(node, content_bytes),
        }
