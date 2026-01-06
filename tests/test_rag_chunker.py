"""Tests for RAG chunker module."""


from src.ast.models import CodeChunk
from src.rag.chunker import get_chunker


class TestChunker:
    """Tests for Chunker class."""

    def test_should_process_file_python(self):
        """Test that Python files are processed."""
        chunker = get_chunker()
        assert chunker.should_process_file("test.py") is True
        assert chunker.should_process_file("src/utils/helper.py") is True

    def test_should_process_file_excluded_patterns(self):
        """Test that excluded patterns are not processed."""
        chunker = get_chunker()
        assert chunker.should_process_file("node_modules/foo.js") is False
        assert chunker.should_process_file("vendor/package.php") is False
        assert chunker.should_process_file(".venv/lib/site.py") is False
        assert chunker.should_process_file("__pycache__/foo.py") is False

    def test_should_process_file_unsupported(self):
        """Test that unsupported file types are not processed."""
        chunker = get_chunker()
        assert chunker.should_process_file("image.png") is False
        assert chunker.should_process_file("data.csv") is False

    def test_has_secrets_api_key(self):
        """Test detection of API keys."""
        chunker = get_chunker()

        content_with_secret = """
api_key = "sk_live_12345678901234567890"
"""
        assert chunker.has_secrets(content_with_secret) is True

    def test_has_secrets_private_key(self):
        """Test detection of private keys."""
        chunker = get_chunker()

        content_with_key = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----
"""
        assert chunker.has_secrets(content_with_key) is True

    def test_has_secrets_clean_code(self):
        """Test that clean code doesn't trigger false positives."""
        chunker = get_chunker()

        clean_code = """
def calculate_total(items):
    return sum(item.price for item in items)
"""
        assert chunker.has_secrets(clean_code) is False

    def test_chunk_file_python(self):
        """Test chunking a Python file."""
        chunker = get_chunker()

        content = """def foo():
    pass

def bar():
    pass
"""
        chunks = chunker.chunk_file("test.py", content)

        assert len(chunks) >= 1
        assert all(isinstance(c, CodeChunk) for c in chunks)

    def test_chunk_file_with_secrets_skipped(self):
        """Test that files with secrets are skipped."""
        chunker = get_chunker()

        content_with_secret = """
API_KEY = "sk_live_12345678901234567890"

def foo():
    pass
"""
        chunks = chunker.chunk_file("config.py", content_with_secret)
        assert chunks == []

    def test_chunk_file_unsupported_fallback(self):
        """Test fallback for unsupported but included files."""
        chunker = get_chunker()

        # YAML is in include_extensions but doesn't have AST support
        content = """
name: test
version: 1.0
"""
        chunks = chunker.chunk_file("config.yaml", content)

        # Should fall back to module-level chunk
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "module"

    def test_chunk_directory(self):
        """Test chunking multiple files."""
        chunker = get_chunker()

        files = {
            "utils.py": "def helper(): pass",
            "main.py": "def main(): pass",
        }

        chunks = chunker.chunk_directory("/project", files)
        assert len(chunks) >= 2
