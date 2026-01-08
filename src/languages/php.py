"""PHP language plugin.

Provides PHP-specific parsing for:
- Import extraction (use statements, require/include)
- Function/method call detection
- Test file pattern generation (PHPUnit conventions: *Test.php)
"""

import re
from pathlib import Path

from .base import LanguagePlugin


class PHPPlugin(LanguagePlugin):
    """PHP language plugin implementation."""

    # Functions to filter from calls
    NOISE_FUNCTIONS = frozenset(
        {
            "echo",
            "print",
            "die",
            "exit",
            "isset",
            "empty",
            "array",
            "function",
            "if",
            "for",
            "foreach",
            "while",
            "switch",
            "case",
            "return",
            "throw",
            "try",
            "catch",
            "finally",
            "new",
            "class",
            "public",
            "private",
            "protected",
            "static",
            "const",
            "var",
            "true",
            "false",
            "null",
            "self",
            "parent",
            "this",
            "strlen",
            "strpos",
            "substr",
            "strlen",
            "trim",
            "ltrim",
            "rtrim",
            "count",
            "sizeof",
            "is_array",
            "is_string",
            "is_int",
            "is_null",
            "array_push",
            "array_pop",
            "array_shift",
            "array_unshift",
            "array_merge",
            "array_keys",
            "array_values",
            "in_array",
            "implode",
            "explode",
            "json_encode",
            "json_decode",
            "sprintf",
            "printf",
            "var_dump",
            "print_r",
        }
    )

    @property
    def name(self) -> str:
        return "php"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".php",)

    @property
    def tree_sitter_name(self) -> str:
        return "php"

    @property
    def extract_node_types(self) -> set[str]:
        return {"function_definition", "class_declaration", "method_declaration"}

    def parse_imports(self, content: str) -> list[str]:
        """Parse PHP imports.

        Handles:
        - use App\\Models\\User;
        - use App\\Services\\OrderService as Service;
        - require_once 'helper.php';
        - include 'config.php';
        """
        imports = []
        patterns = [
            # Use statements: use Namespace\Class;
            r"use\s+([\w\\\\]+)(?:\s+as\s+\w+)?;",
            # Require/include: require('file.php'), require_once "file.php"
            r"(?:require|include)(?:_once)?\s*\(?['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            imports.extend(re.findall(pattern, content))

        # Normalize PHP namespaces: App\\Models\\User → App/Models/User
        normalized = []
        for imp in imports:
            # Handle double backslashes from regex and single backslashes
            normalized.append(imp.replace("\\\\", "/").replace("\\", "/"))

        return list(set(normalized))

    def parse_calls(self, content: str) -> list[str]:
        """Parse PHP function/method calls."""
        calls = []
        patterns = [
            # Function calls: functionName(...)
            r"(\w+)\s*\(",
            # Method calls: $obj->method(...)
            r"\$\w+->([\w]+)\s*\(",
            # Static self calls: self::method(...)
            r"self::([\w]+)\s*\(",
            # Static class calls: ClassName::method(...)
            r"\w+::([\w]+)\s*\(",
        ]

        for pattern in patterns:
            calls.extend(re.findall(pattern, content))

        return [c for c in set(calls) if c not in self.NOISE_FUNCTIONS]

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns for PHP.

        PHPUnit conventions:
        - tests/{Name}Test.php
        - tests/Unit/{Name}Test.php
        - tests/Feature/{Name}Test.php
        """
        path = Path(file_path)
        stem = path.stem
        parent = str(path.parent)

        # Capitalize first letter for PHPUnit convention
        cap_stem = stem[0].upper() + stem[1:] if stem else stem

        # Normalize parent path
        if parent == ".":
            parent = ""

        patterns = [
            f"tests/{cap_stem}Test.php",
            f"tests/Unit/{cap_stem}Test.php",
            f"tests/Feature/{cap_stem}Test.php",
        ]

        if parent:
            patterns.append(f"tests/{parent}/{cap_stem}Test.php")

        return patterns

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract function/method signature."""
        text = content_bytes[node.start_byte : node.end_byte].decode()
        first_line = text.split("\n")[0].strip()

        # Truncate at opening brace if present
        if "{" in first_line:
            first_line = first_line[: first_line.index("{")].strip()

        return first_line if first_line else None
