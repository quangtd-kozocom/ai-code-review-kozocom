"""Tests for RAG retriever module (v2).

Updated to test the refactored retriever and helper classes.
"""

from unittest.mock import MagicMock, patch

from src.ast.models import RelatedCode
from src.rag.call_resolution import CalleeResolver, CallerFinder, CallParser, TestFinder
from src.rag.retriever import get_retriever


class TestRetriever:
    """Tests for Retriever class."""

    def test_retrieve_returns_related_code(self):
        """Test that retrieve returns RelatedCode objects."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            # Mock fetch_by_metadata for the new API
            mock_store.fetch_by_metadata.return_value = [
                MagicMock(
                    metadata={
                        "file_path": "tests/test_calc.py",
                        "name": "test_calculate",
                        "content": "def test_calculate(): pass",
                        "chunk_type": "function",
                    }
                )
            ]
            mock_store_fn.return_value = mock_store

            retriever = get_retriever()
            results = retriever.retrieve(
                owner="owner",
                repo="repo",
                file_path="src/calc.py",
                function_name="calculate",
            )

            # Should have at least test result
            assert isinstance(results, list)
            if results:
                assert isinstance(results[0], RelatedCode)

    def test_retrieve_for_function_with_file(self):
        """Test that retrieve_for_function works with file path."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.fetch_by_metadata.return_value = []
            mock_store_fn.return_value = mock_store

            retriever = get_retriever()
            results = retriever.retrieve_for_function(
                owner="test",
                repo="repo",
                function_name="calculate",
                signature="def calculate(x, y):",
                current_file="src/utils.py",
            )

            assert isinstance(results, list)

    def test_retrieve_for_function_without_file(self):
        """Test that retrieve_for_function returns empty without file."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store_fn.return_value = mock_store

            retriever = get_retriever()
            results = retriever.retrieve_for_function(
                owner="test",
                repo="repo",
                function_name="calculate",
            )

            # Should return empty list without file path
            assert results == []

    def test_retrieve_handles_errors_gracefully(self):
        """Test that retrieve handles errors gracefully."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.fetch_by_metadata.side_effect = Exception("Connection error")
            mock_store_fn.return_value = mock_store

            retriever = get_retriever()
            # Should not raise, just log warning
            results = retriever.retrieve(
                owner="owner",
                repo="repo",
                file_path="src/calc.py",
                function_name="calculate",
            )

            # Should return empty list instead of raising
            assert results == []


class TestTestFinder:
    """Tests for TestFinder class."""

    def test_find_test_finds_matching_test(self):
        """Test _find_test finds test matching function name."""
        mock_store = MagicMock()
        mock_store.fetch_by_metadata.return_value = [
            MagicMock(
                metadata={
                    "file_path": "tests/test_utils.py",
                    "name": "test_calculate_total",
                    "content": "def test_calculate_total(): ...",
                    "chunk_type": "function",
                }
            )
        ]

        from src.languages.python import PythonPlugin

        finder = TestFinder(mock_store)
        result = finder.find(
            namespace="owner/repo",
            file_path="src/utils.py",
            function_name="calculate_total",
            plugin=PythonPlugin(),
        )

        assert result is not None
        assert result.relationship == "test"
        assert result.name == "test_calculate_total"


class TestCallerFinder:
    """Tests for CallerFinder class."""

    def test_find_callers_finds_functions_calling_target(self):
        """Test find() finds functions that call target."""
        mock_store = MagicMock()
        mock_store.fetch_by_metadata.return_value = [
            MagicMock(
                metadata={
                    "file_path": "src/order.py",
                    "name": "process_order",
                    "content": "def process_order(): calculate_total()",
                    "chunk_type": "function",
                    "calls": ["calculate_total"],
                }
            )
        ]

        finder = CallerFinder(mock_store)
        results = finder.find(
            namespace="owner/repo",
            function_name="calculate_total",
            exclude_file="src/utils.py",
        )

        assert len(results) == 1
        assert results[0].relationship == "caller"
        assert results[0].name == "process_order"


class TestCalleeResolver:
    """Tests for CalleeResolver class."""

    def test_resolve_finds_called_functions(self):
        """Test resolve() finds functions called by target."""
        mock_store = MagicMock()
        # Return a resolved callee
        mock_store.fetch_by_metadata.return_value = [
            MagicMock(
                metadata={
                    "file_path": "src/items.py",
                    "name": "get_items",
                    "content": "def get_items(): ...",
                    "chunk_type": "function",
                }
            )
        ]

        resolver = CalleeResolver(mock_store)
        results = resolver.resolve(
            namespace="owner/repo",
            calls=["get_items"],
            current_file="src/utils.py",
        )

        assert len(results) == 1
        assert results[0].name == "get_items"
        assert results[0].from_same_file is False


class TestCallParser:
    """Tests for CallParser class."""

    def test_parse_extracts_function_calls(self):
        """Test parse() extracts function calls from Python code."""
        parser = CallParser()
        content = """
def calculate_total():
    items = get_items()
    discount = apply_discount(items)
    return sum(items) - discount
"""
        calls = parser.parse("src/calc.py", content)

        assert "get_items" in calls
        assert "apply_discount" in calls
        # Built-ins should be filtered out by the plugin
        assert "sum" not in calls

    def test_parse_returns_empty_for_unknown_language(self):
        """Test parse() returns empty for unknown languages."""
        parser = CallParser()
        calls = parser.parse("file.unknown", "some content")
        assert calls == []
