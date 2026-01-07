"""Python language plugin.

Provides Python-specific parsing for:
- Import extraction (import X, from X import Y, relative imports)
- Function call detection using AST
- Test file pattern generation (test_*.py, *_test.py)
"""

import ast
import re
from pathlib import Path

from .base import LanguagePlugin


class PythonPlugin(LanguagePlugin):
    """Python language plugin implementation."""

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
        imports = []
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
                match = re.match(r"from\s+([\w.]+)\s+import", line)
                if match:
                    imports.append(match.group(1))

        return list(set(imports))

    def parse_calls(self, content: str) -> list[str]:
        """Parse Python function calls using ast module."""
        calls = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.append(node.func.attr)
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

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract first line as signature."""
        text = content_bytes[node.start_byte : node.end_byte].decode()
        first_line = text.split("\n")[0].strip()
        return first_line if first_line else None

    def extract_docstring(self, node, content_bytes: bytes) -> str | None:
        """Extract docstring from function/class."""
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "string":
                                text = expr.text.decode()
                                # Strip quotes and whitespace
                                return text.strip("\"'").strip()
                break
        return None
