"""AST-based code analyzer using Tree-sitter.

Provides deterministic code analysis for extracting function definitions,
signatures, and call sites without relying on vector embeddings.

This is a self-contained module that doesn't depend on external language plugins.
"""

from dataclasses import dataclass, field
from functools import cache

import structlog
import tree_sitter_language_pack as ts_pack

from .models import (
    ClassInfo,
    FunctionInfo,
    ParameterInfo,
    ASTInfo,
    detect_language,
    get_grammar_name,
)

log = structlog.get_logger()


@dataclass(slots=True)
class FunctionDefinition:
    """Complete function definition with metadata."""
    
    name: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    content: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    docstring: str | None = None
    calls: list[str] = field(default_factory=list)
    
    @property
    def qualified_name(self) -> str:
        """Get fully qualified name including file path."""
        return f"{self.file_path}::{self.name}"


@dataclass(slots=True)
class CallSite:
    """A location where a function is called."""
    
    function_name: str
    file_path: str
    line: int
    column: int
    caller_function: str | None = None
    context_code: str = ""


# Node types for function definitions across languages
FUNCTION_NODE_TYPES = frozenset({
    "function_definition",      # Python
    "function_declaration",     # JS/TS/C/Go
    "method_definition",        # Ruby
    "arrow_function",           # JS/TS
    "method_declaration",       # Java
    "function_item",            # Rust
})

CLASS_NODE_TYPES = frozenset({
    "class_definition",         # Python
    "class_declaration",        # JS/TS/Java
    "class",                    # Ruby
    "struct_item",              # Rust
    "interface_declaration",    # TS/Java
})

CALL_NODE_TYPES = frozenset({
    "call",                     # Python
    "call_expression",          # JS/TS/Go
    "method_invocation",        # Java
    "function_call_expression", # PHP
})

IDENTIFIER_NODE_TYPES = frozenset({
    "identifier",
    "name", 
    "property_identifier",
    "field_identifier",
})


class ASTAnalyzer:
    """Tree-sitter based code analysis.
    
    Extracts code structure and relationships using AST parsing,
    providing accurate and deterministic results without embeddings.
    """
    
    def __init__(self) -> None:
        self._parsers: dict[str, object] = {}
    
    def _get_parser(self, language: str):
        """Get or create parser for language."""
        if language not in self._parsers:
            try:
                self._parsers[language] = ts_pack.get_parser(language)
            except Exception as e:
                log.warning("ast_analyzer.parser_failed", language=language, error=str(e))
                return None
        return self._parsers[language]
    
    def extract_functions(
        self,
        file_path: str,
        content: str,
    ) -> list[FunctionDefinition]:
        """Extract all function definitions from a file.
        
        Args:
            file_path: Path to the file.
            content: File content.
            
        Returns:
            List of FunctionDefinition objects.
        """
        grammar_name = get_grammar_name(file_path)
        if not grammar_name:
            return []
        
        parser = self._get_parser(grammar_name)
        if not parser:
            return []
        
        try:
            tree = parser.parse(content.encode())
            return self._walk_for_functions(
                tree.root_node,
                file_path,
                content.encode(),
                detect_language(file_path) or "unknown",
            )
        except Exception as e:
            log.warning("ast_analyzer.extract_failed", file=file_path, error=str(e))
            return []
    
    def _walk_for_functions(
        self,
        root,
        file_path: str,
        content_bytes: bytes,
        language: str,
    ) -> list[FunctionDefinition]:
        """Walk AST tree and extract function definitions."""
        functions: list[FunctionDefinition] = []
        
        def walk(node, parent_class: str | None = None) -> None:
            if node.type in FUNCTION_NODE_TYPES:
                if func := self._extract_function(
                    node, file_path, content_bytes, language, parent_class
                ):
                    functions.append(func)
            elif node.type in CLASS_NODE_TYPES:
                class_name = self._get_node_name(node)
                for child in node.children:
                    walk(child, class_name)
                return  # Don't walk children again
            
            for child in node.children:
                walk(child, parent_class)
        
        walk(root)
        return functions
    
    def _extract_function(
        self,
        node,
        file_path: str,
        content_bytes: bytes,
        language: str,
        parent_class: str | None,
    ) -> FunctionDefinition | None:
        """Extract function definition from AST node."""
        name = self._get_node_name(node)
        if not name:
            return None
        
        content = content_bytes[node.start_byte:node.end_byte].decode()
        
        # Extract signature and other details
        signature = self._extract_signature(node, content_bytes, language)
        docstring = self._extract_docstring(node, content_bytes, language)
        parameters = self._extract_parameters(node, content_bytes, language)
        decorators = self._extract_decorators(node, content_bytes, language)
        is_async = self._is_async_function(node, content)
        calls = self._parse_calls(content, language)
        
        return FunctionDefinition(
            name=name,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
            content=content,
            parameters=parameters,
            return_type=self._extract_return_type(node, content_bytes, language),
            decorators=decorators,
            is_async=is_async,
            is_method=parent_class is not None,
            docstring=docstring,
            calls=calls,
        )
    
    def _extract_signature(
        self,
        node,
        content_bytes: bytes,
        language: str,
    ) -> str:
        """Extract function signature."""
        # Get the first line up to the colon or opening brace
        content = content_bytes[node.start_byte:node.end_byte].decode()
        first_line = content.split("\n")[0]
        
        # Remove trailing colon/brace
        for end in (":", "{", "=>"):
            if end in first_line:
                first_line = first_line.split(end)[0].strip()
                break
        
        return first_line
    
    def _extract_docstring(
        self,
        node,
        content_bytes: bytes,
        language: str,
    ) -> str | None:
        """Extract docstring if present."""
        for child in node.children:
            if child.type == "block":
                for block_child in child.children:
                    if block_child.type in ("expression_statement", "string"):
                        text = content_bytes[block_child.start_byte:block_child.end_byte].decode()
                        if text.startswith(('"""', "'''", '"', "'")):
                            return text.strip("\"'").strip()
                break
        return None
    
    def _extract_parameters(
        self,
        node,
        content_bytes: bytes,
        language: str,
    ) -> list[ParameterInfo]:
        """Extract function parameters."""
        params: list[ParameterInfo] = []
        
        for child in node.children:
            if child.type in ("parameters", "formal_parameters", "parameter_list"):
                for param in child.children:
                    if param.type in ("identifier", "typed_parameter", "parameter", 
                                      "typed_default_parameter", "default_parameter"):
                        param_info = self._parse_parameter(param, content_bytes)
                        if param_info:
                            params.append(param_info)
        
        return params
    
    def _parse_parameter(
        self,
        node,
        content_bytes: bytes,
    ) -> ParameterInfo | None:
        """Parse a single parameter node."""
        text = content_bytes[node.start_byte:node.end_byte].decode()
        
        match node.type:
            case "identifier":
                return ParameterInfo(name=text)
            case "typed_parameter" | "typed_default_parameter":
                # name: type or name: type = default
                parts = text.split(":")
                name = parts[0].strip()
                type_hint = None
                default = None
                if len(parts) > 1:
                    rest = parts[1]
                    if "=" in rest:
                        type_part, default = rest.split("=", 1)
                        type_hint = type_part.strip()
                        default = default.strip()
                    else:
                        type_hint = rest.strip()
                return ParameterInfo(
                    name=name,
                    type_hint=type_hint,
                    default_value=default,
                )
            case "default_parameter":
                parts = text.split("=")
                return ParameterInfo(
                    name=parts[0].strip(),
                    default_value=parts[1].strip() if len(parts) > 1 else None,
                )
            case _:
                # Try to get identifier
                for child in node.children:
                    if child.type in IDENTIFIER_NODE_TYPES:
                        return ParameterInfo(name=child.text.decode())
        
        return None
    
    def _extract_decorators(
        self,
        node,
        content_bytes: bytes,
        language: str,
    ) -> list[str]:
        """Extract decorators from function."""
        decorators: list[str] = []
        
        # Look for decorator nodes before the function
        prev = node.prev_sibling
        while prev:
            if prev.type == "decorator":
                text = content_bytes[prev.start_byte:prev.end_byte].decode()
                decorators.insert(0, text.strip())
            elif prev.type not in ("comment", "decorator"):
                break
            prev = prev.prev_sibling
        
        return decorators
    
    def _extract_return_type(
        self,
        node,
        content_bytes: bytes,
        language: str,
    ) -> str | None:
        """Extract return type annotation."""
        for child in node.children:
            if child.type in ("return_type", "type_annotation"):
                text = content_bytes[child.start_byte:child.end_byte].decode()
                return text.lstrip("->:").strip()
        return None
    
    def _is_async_function(self, node, content: str) -> bool:
        """Check if function is async."""
        return content.strip().startswith("async ") or node.type == "async_function_definition"
    
    def _parse_calls(self, content: str, language: str) -> list[str]:
        """Parse function calls from code content."""
        import re
        
        # Extract function name from the first line (def function_name(...))
        # to exclude self-references
        function_name = None
        lines = content.split('\n')
        if lines:
            first_line = lines[0].strip()
            # Match: def function_name( or async def function_name(
            func_def_match = re.match(r'(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', first_line)
            if func_def_match:
                function_name = func_def_match.group(1)
        
        # Simple regex for function calls
        # Matches: func_name( but not class definitions, etc.
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        
        # Process line by line to exclude function definition lines
        matches = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are function/class definitions
            if stripped.startswith(('def ', 'async def ', 'class ')):
                continue
            # Find matches in this line
            matches.extend(re.findall(pattern, line))
        
        # Filter out keywords and common constructs
        keywords = {
            "if", "else", "elif", "while", "for", "def", "class", "return",
            "import", "from", "try", "except", "finally", "with", "as",
            "function", "const", "let", "var", "new", "async", "await",
            "print", "len", "str", "int", "float", "bool", "list", "dict",
            "set", "tuple", "range", "enumerate", "zip", "map", "filter",
        }
        
        # Filter and deduplicate
        filtered = [m for m in matches if m not in keywords]
        
        # Exclude the function's own name (self-reference)
        if function_name:
            filtered = [m for m in filtered if m != function_name]
        
        # Deduplicate while preserving order
        seen = set()
        result = []
        for call in filtered:
            if call not in seen:
                seen.add(call)
                result.append(call)
        
        log.debug(
            "ast_analyzer.parse_calls",
            function=function_name,
            total_matches=len(matches),
            filtered_count=len(result),
            calls=result[:10],  # Log first 10 for debugging
        )
        
        return result
    
    def find_call_sites(
        self,
        file_path: str,
        content: str,
        target_function: str,
    ) -> list[CallSite]:
        """Find all locations where a function is called.
        
        Args:
            file_path: Path to the file to search.
            content: File content.
            target_function: Name of function to find calls to.
            
        Returns:
            List of CallSite objects where function is called.
        """
        grammar_name = get_grammar_name(file_path)
        if not grammar_name:
            return []
        
        parser = self._get_parser(grammar_name)
        if not parser:
            return []
        
        try:
            tree = parser.parse(content.encode())
            return self._find_calls_in_tree(
                tree.root_node,
                file_path,
                content,
                target_function,
            )
        except Exception as e:
            log.warning("ast_analyzer.find_calls_failed", file=file_path, error=str(e))
            return []
    
    def _find_calls_in_tree(
        self,
        root,
        file_path: str,
        content: str,
        target_function: str,
    ) -> list[CallSite]:
        """Find call sites in AST tree."""
        call_sites: list[CallSite] = []
        lines = content.split("\n")
        
        current_function: str | None = None
        
        def walk(node) -> None:
            nonlocal current_function
            
            # Track which function we're inside
            if node.type in FUNCTION_NODE_TYPES:
                old_function = current_function
                current_function = self._get_node_name(node)
                for child in node.children:
                    walk(child)
                current_function = old_function
                return
            
            if node.type in CALL_NODE_TYPES:
                called_name = self._get_call_name(node)
                if called_name == target_function:
                    line_num = node.start_point[0]
                    context = self._get_context_lines(lines, line_num, 2)
                    call_sites.append(CallSite(
                        function_name=target_function,
                        file_path=file_path,
                        line=line_num + 1,
                        column=node.start_point[1],
                        caller_function=current_function,
                        context_code=context,
                    ))
            
            for child in node.children:
                walk(child)
        
        walk(root)
        return call_sites
    
    def compare_functions(
        self,
        old_content: str,
        new_content: str,
        file_path: str,
    ) -> dict[str, dict]:
        """Compare function definitions between two versions.
        
        Args:
            old_content: Content from base branch.
            new_content: Content from head branch.
            file_path: File path for language detection.
            
        Returns:
            Dict mapping function names to change info.
        """
        old_funcs = {f.name: f for f in self.extract_functions(file_path, old_content)}
        new_funcs = {f.name: f for f in self.extract_functions(file_path, new_content)}
        
        changes: dict[str, dict] = {}
        
        all_names = set(old_funcs) | set(new_funcs)
        for name in all_names:
            old_func = old_funcs.get(name)
            new_func = new_funcs.get(name)
            
            match (old_func, new_func):
                case (None, func) if func:
                    changes[name] = {
                        "type": "added",
                        "new": func,
                    }
                case (func, None) if func:
                    changes[name] = {
                        "type": "deleted",
                        "old": func,
                    }
                case (old, new) if old and new:
                    if old.content != new.content:
                        changes[name] = {
                            "type": "modified",
                            "old": old,
                            "new": new,
                            "signature_changed": old.signature != new.signature,
                        }
        
        return changes
    
    def get_ast_info(
        self,
        file_path: str,
        content: str,
    ) -> ASTInfo | None:
        """Get full AST information for a file.
        
        Args:
            file_path: Path to the file.
            content: File content.
            
        Returns:
            ASTInfo with functions, classes, imports.
        """
        language = detect_language(file_path)
        if not language:
            return None
        
        functions = self.extract_functions(file_path, content)
        
        func_infos = [
            FunctionInfo(
                name=f.name,
                signature=f.signature,
                start_line=f.start_line,
                end_line=f.end_line,
                parameters=f.parameters,
                return_type=f.return_type,
                decorators=f.decorators,
                is_async=f.is_async,
                is_method=f.is_method,
                docstring=f.docstring,
            )
            for f in functions
        ]
        
        # Extract imports using simple pattern matching
        imports = self._extract_imports(content, language)
        
        return ASTInfo(
            file_path=file_path,
            language=language,
            functions=func_infos,
            classes=[],  # TODO: Implement class extraction if needed
            imports=imports,
        )
    
    def _extract_imports(self, content: str, language: str) -> list[str]:
        """Extract import statements from code."""
        import re
        
        imports: list[str] = []
        
        match language:
            case "python":
                # from x import y / import x
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        imports.append(line)
            
            case "javascript" | "typescript" | "tsx":
                # import x from 'y' / require('x')
                import_pattern = r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"
                require_pattern = r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
                imports.extend(re.findall(import_pattern, content))
                imports.extend(re.findall(require_pattern, content))
            
            case "go":
                # import "x" / import ( "x" "y" )
                import_pattern = r'import\s*(?:\(\s*([^)]+)\s*\)|"([^"]+)")'
                for match in re.finditer(import_pattern, content):
                    if match.group(1):
                        imports.extend(re.findall(r'"([^"]+)"', match.group(1)))
                    elif match.group(2):
                        imports.append(match.group(2))
            
            case _:
                # Generic: look for import/require statements
                for line in content.split("\n"):
                    line = line.strip()
                    if "import" in line.lower() or "require" in line.lower():
                        imports.append(line)
        
        return imports
    
    def _get_node_name(self, node) -> str | None:
        """Extract name from AST node."""
        for child in node.children:
            if child.type in IDENTIFIER_NODE_TYPES:
                return child.text.decode()
        return None
    
    def _get_call_name(self, node) -> str | None:
        """Extract function name from call node."""
        for child in node.children:
            if child.type in IDENTIFIER_NODE_TYPES:
                return child.text.decode()
            if child.type in ("attribute", "member_expression"):
                # Get the method name (last identifier)
                for subchild in child.children:
                    if subchild.type in IDENTIFIER_NODE_TYPES:
                        return subchild.text.decode()
        return None
    
    def _get_context_lines(
        self,
        lines: list[str],
        line_num: int,
        context: int,
    ) -> str:
        """Get lines around a specific line number."""
        start = max(0, line_num - context)
        end = min(len(lines), line_num + context + 1)
        return "\n".join(lines[start:end])


@cache
def get_ast_analyzer() -> ASTAnalyzer:
    """Get cached AST analyzer instance."""
    return ASTAnalyzer()
