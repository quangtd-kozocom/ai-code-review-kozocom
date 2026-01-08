"""JavaScript language plugin."""

import re
from pathlib import Path

from .base import LanguagePlugin


class JavaScriptPlugin(LanguagePlugin):
    """JavaScript plugin for .js and .jsx files."""

    NOISE_FUNCTIONS = frozenset({
        "console", "log", "error", "warn", "info", "debug", "trace",
        "require", "import", "parseInt", "parseFloat",
        "String", "Number", "Boolean", "Array", "Object", "Date", "Math", "JSON",
        "RegExp", "Error", "Promise", "Symbol", "Map", "Set",
        "setTimeout", "setInterval", "clearTimeout", "clearInterval",
        "encodeURI", "decodeURI", "encodeURIComponent", "decodeURIComponent",
        "isNaN", "isFinite", "eval", "undefined", "null",
        "then", "catch", "finally", "resolve", "reject",
        "length", "push", "pop", "shift", "unshift", "slice", "splice",
        "map", "filter", "reduce", "forEach", "find", "findIndex",
        "includes", "indexOf", "join", "split", "concat", "some", "every", "flat", "flatMap",
        "keys", "values", "entries", "assign",
    })

    @property
    def name(self) -> str:
        return "javascript"

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".js", ".jsx")

    @property
    def tree_sitter_name(self) -> str:
        return "javascript"

    @property
    def extract_node_types(self) -> set[str]:
        return {
            "function_declaration", "arrow_function", "method_definition", "function_expression",
            "class_declaration", "variable_declaration", "lexical_declaration",
            "export_statement", "assignment_expression",
        }

    def parse_imports(self, content: str) -> list[str]:
        patterns = [
            r"import\s+(?:type\s+)?(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
            r"import\s*\(\s*['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]",
        ]
        imports = []
        for pattern in patterns:
            imports.extend(re.findall(pattern, content))
        return list(set(imports))

    def parse_calls(self, content: str) -> list[str]:
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
            calls = re.findall(r"(\w+)\s*\(", content)
        return [c for c in set(calls) if c not in self.NOISE_FUNCTIONS]

    def get_test_patterns(self, file_path: str) -> list[str]:
        path = Path(file_path)
        stem, ext = path.stem, path.suffix
        return [
            f"__tests__/{stem}.test{ext}", f"__tests__/{stem}.spec{ext}",
            f"{stem}.test{ext}", f"{stem}.spec{ext}",
            f"tests/{stem}.test{ext}", f"test/{stem}.test{ext}",
        ]

    def extract_signature(self, node, content_bytes: bytes) -> str | None:
        text = content_bytes[node.start_byte:node.end_byte].decode()
        first_line = text.split("\n")[0].strip()
        if "{" in first_line:
            first_line = first_line[:first_line.index("{")].strip()
        return first_line or None

    def extract_docstring(self, node, content_bytes: bytes) -> str | None:
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment = content_bytes[node.prev_sibling.start_byte:node.prev_sibling.end_byte].decode()
            if comment.strip().startswith("/**"):
                return comment.strip()
        return None

    def extract_express_routes(self, content: str) -> list[dict]:
        pattern = r"(?:app|router)\.(get|post|put|delete|patch|options|head|use)\s*\(\s*['\"]([^'\"]+)['\"]"
        return [{"method": m.group(1).upper(), "path": m.group(2)} for m in re.finditer(pattern, content, re.IGNORECASE)]
