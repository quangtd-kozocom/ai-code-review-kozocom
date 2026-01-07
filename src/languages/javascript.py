"""JavaScript/TypeScript language plugin.

Provides JS/TS-specific parsing for:
- Import extraction (ES6 imports, require, dynamic imports)
- Function call detection using tree-sitter
- Test file pattern generation (*.test.js, *.spec.js, __tests__/*)
"""

import re
from pathlib import Path

from .base import LanguagePlugin


class JavaScriptPlugin(LanguagePlugin):
    """JavaScript/TypeScript language plugin implementation."""

    # Functions to filter from calls
    NOISE_FUNCTIONS = frozenset(
        {
            "console",
            "log",
            "error",
            "warn",
            "info",
            "debug",
            "trace",
            "require",
            "import",
            "parseInt",
            "parseFloat",
            "String",
            "Number",
            "Boolean",
            "Array",
            "Object",
            "Date",
            "Math",
            "JSON",
            "RegExp",
            "Error",
            "Promise",
            "Symbol",
            "setTimeout",
            "setInterval",
            "clearTimeout",
            "clearInterval",
            "encodeURI",
            "decodeURI",
            "encodeURIComponent",
            "decodeURIComponent",
            "isNaN",
            "isFinite",
            "eval",
            "undefined",
            "null",
            "then",
            "catch",
            "finally",
            "resolve",
            "reject",
            "length",
            "push",
            "pop",
            "shift",
            "unshift",
            "slice",
            "splice",
            "map",
            "filter",
            "reduce",
            "forEach",
            "find",
            "findIndex",
            "includes",
            "indexOf",
            "join",
            "split",
            "concat",
        }
    )

    @property
    def name(self) -> str:
        return "javascript"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".js", ".jsx", ".ts", ".tsx")

    @property
    def tree_sitter_name(self) -> str:
        # Basic javascript grammar works for most parsing
        return "javascript"

    @property
    def extract_node_types(self) -> set[str]:
        return {
            "function_declaration",
            "class_declaration",
            "arrow_function",
            "method_definition",
        }

    def parse_imports(self, content: str) -> list[str]:
        """Parse JS/TS imports.

        Handles:
        - import { foo } from './utils'
        - import * as lib from 'library'
        - import foo from './bar'
        - const x = require('./helper')
        - import type { X } from './types'
        - import('./dynamic')
        """
        imports = []
        patterns = [
            # ES6 imports: import {...}, import *, import default
            r"import\s+(?:type\s+)?(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
            # Dynamic imports: import('...')
            r"import\s*\(\s*['\"]([^'\"]+)['\"]",
            # CommonJS: require('...')
            r"require\s*\(\s*['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            imports.extend(re.findall(pattern, content))

        return list(set(imports))

    def parse_calls(self, content: str) -> list[str]:
        """Parse JS/TS function calls."""
        calls = []

        try:
            import tree_sitter_language_pack as ts_pack

            parser = ts_pack.get_parser("javascript")
            tree = parser.parse(content.encode())

            def walk(node):
                if node.type == "call_expression":
                    func = node.child_by_field_name("function")
                    if func:
                        if func.type == "identifier":
                            calls.append(func.text.decode())
                        elif func.type == "member_expression":
                            prop = func.child_by_field_name("property")
                            if prop:
                                calls.append(prop.text.decode())
                for child in node.children:
                    walk(child)

            walk(tree.root_node)
        except Exception:
            # Fall back to regex
            pattern = r"(\w+)\s*\("
            calls = re.findall(pattern, content)

        return [c for c in set(calls) if c not in self.NOISE_FUNCTIONS]

    def get_test_patterns(self, file_path: str) -> list[str]:
        """Generate test file patterns for JS/TS.

        Conventions:
        - __tests__/{name}.test.{ext}
        - __tests__/{name}.spec.{ext}
        - {name}.test.{ext}
        - {name}.spec.{ext}
        - tests/{name}.test.{ext}
        - test/{name}.test.{ext}
        """
        path = Path(file_path)
        stem = path.stem
        ext = path.suffix

        # Handle .tsx -> .tsx, .ts -> .ts, .jsx -> .jsx, .js -> .js
        # But also allow cross-extension (e.g., .ts file with .test.ts)

        return [
            f"__tests__/{stem}.test{ext}",
            f"__tests__/{stem}.spec{ext}",
            f"{stem}.test{ext}",
            f"{stem}.spec{ext}",
            f"tests/{stem}.test{ext}",
            f"test/{stem}.test{ext}",
        ]

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        """Extract function signature."""
        text = content_bytes[node.start_byte : node.end_byte].decode()

        # For arrow functions, find the variable declaration
        first_line = text.split("\n")[0].strip()

        # Truncate at opening brace if present
        if "{" in first_line:
            first_line = first_line[: first_line.index("{")].strip()

        return first_line if first_line else None
