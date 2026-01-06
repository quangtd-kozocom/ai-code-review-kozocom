"""Tests for AST parser module."""


from src.ast.models import CodeChunk
from src.ast.parser import get_code_parser


class TestCodeParser:
    """Tests for CodeParser class."""

    def test_detect_language_python(self):
        """Test Python language detection."""
        parser = get_code_parser()
        assert parser.detect_language("test.py") == "python"
        assert parser.detect_language("src/utils/helper.py") == "python"

    def test_detect_language_javascript(self):
        """Test JavaScript language detection."""
        parser = get_code_parser()
        assert parser.detect_language("test.js") == "javascript"
        assert parser.detect_language("test.jsx") == "javascript"

    def test_detect_language_typescript(self):
        """Test TypeScript language detection."""
        parser = get_code_parser()
        assert parser.detect_language("test.ts") == "typescript"
        assert parser.detect_language("test.tsx") == "tsx"

    def test_detect_language_unsupported(self):
        """Test unsupported file types return None."""
        parser = get_code_parser()
        assert parser.detect_language("test.txt") is None
        assert parser.detect_language("test.md") is None

    def test_parse_python_function(self):
        """Test parsing a simple Python function."""
        content = '''def calculate_total(items, discount=0):
    """Calculate total price."""
    return sum(i.price for i in items) * (1 - discount)
'''
        parser = get_code_parser()
        chunks = parser.parse_file("test.py", content)

        assert len(chunks) == 1
        assert chunks[0].name == "calculate_total"
        assert chunks[0].chunk_type == "function"
        assert chunks[0].language == "python"
        assert chunks[0].start_line == 1

    def test_parse_python_class(self):
        """Test parsing a Python class."""
        content = '''class OrderService:
    """Service for handling orders."""

    def __init__(self, db):
        self.db = db

    def create_order(self, user_id, items):
        """Create a new order."""
        pass
'''
        parser = get_code_parser()
        chunks = parser.parse_file("test.py", content)

        # Should find class and methods
        assert len(chunks) >= 1
        class_chunk = next((c for c in chunks if c.chunk_type == "class"), None)
        assert class_chunk is not None
        assert class_chunk.name == "OrderService"

    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        parser = get_code_parser()
        chunks = parser.parse_file("test.py", "")
        assert chunks == []

    def test_parse_unsupported_language(self):
        """Test parsing unsupported file type."""
        parser = get_code_parser()
        chunks = parser.parse_file("test.md", "# Header")
        assert chunks == []

    def test_get_ast_info_python(self):
        """Test getting AST info for Python file."""
        content = """import os
from typing import List

def foo():
    pass

class Bar:
    def baz(self):
        pass
"""
        parser = get_code_parser()
        ast_info = parser.get_ast_info("test.py", content)

        assert ast_info is not None
        assert ast_info.language == "python"
        assert len(ast_info.functions) >= 1
        assert any(f.name == "foo" for f in ast_info.functions)
        assert len(ast_info.classes) == 1
        assert ast_info.classes[0].name == "Bar"
        assert len(ast_info.imports) == 2


class TestCodeChunk:
    """Tests for CodeChunk model."""

    def test_chunk_id(self):
        """Test chunk ID generation."""
        chunk = CodeChunk(
            chunk_type="function",
            name="test_func",
            content="def test_func(): pass",
            file_path="src/utils.py",
            start_line=10,
            end_line=12,
            language="python",
        )

        assert chunk.id == "src/utils.py:test_func:10"

    def test_to_embedding_text(self):
        """Test embedding text generation."""
        chunk = CodeChunk(
            chunk_type="function",
            name="calculate",
            content="def calculate(x, y): return x + y",
            file_path="math.py",
            start_line=1,
            end_line=1,
            language="python",
            signature="def calculate(x, y):",
            docstring="Add two numbers.",
        )

        text = chunk.to_embedding_text()
        assert "function: calculate" in text
        assert "Signature: def calculate(x, y):" in text
        assert "Docstring: Add two numbers." in text
        assert "Code:" in text
