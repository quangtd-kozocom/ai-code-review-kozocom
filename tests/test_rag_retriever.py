"""Tests for RAG retriever module (v2)."""

from unittest.mock import MagicMock, patch

from src.ast.models import RelatedCode
from src.rag.retriever import get_retriever


class TestRetriever:
    """Tests for Retriever class."""

    def test_retrieve_returns_related_code(self):
        """Test that retrieve returns RelatedCode objects."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            # Mock _find_test, _find_callers, _find_callees via query_by_metadata
            mock_store.query_by_metadata.return_value = [
                {
                    "metadata": {
                        "file_path": "tests/test_calc.py",
                        "name": "test_calculate",
                        "content": "def test_calculate(): pass",
                        "chunk_type": "function",
                    },
                }
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
            mock_store.query_by_metadata.return_value = []
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

    def test_find_test_finds_matching_test(self):
        """Test _find_test finds test matching function name."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.query_by_metadata.return_value = [
                {
                    "metadata": {
                        "file_path": "tests/test_utils.py",
                        "name": "test_calculate_total",
                        "content": "def test_calculate_total(): ...",
                        "chunk_type": "function",
                    }
                }
            ]
            mock_store_fn.return_value = mock_store

            from src.languages.python import PythonPlugin

            retriever = get_retriever()
            result = retriever._find_test(
                namespace="owner/repo",
                file_path="src/utils.py",
                function_name="calculate_total",
                plugin=PythonPlugin(),
            )

            assert result is not None
            assert result.relationship == "test"
            assert result.name == "test_calculate_total"

    def test_find_callers_finds_functions_calling_target(self):
        """Test _find_callers finds functions that call target."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.query_by_metadata.return_value = [
                {
                    "metadata": {
                        "file_path": "src/order.py",
                        "name": "process_order",
                        "content": "def process_order(): calculate_total()",
                        "chunk_type": "function",
                    }
                }
            ]
            mock_store_fn.return_value = mock_store

            retriever = get_retriever()
            results = retriever._find_callers(
                namespace="owner/repo",
                file_path="src/utils.py",
                function_name="calculate_total",
            )

            assert len(results) == 1
            assert results[0].relationship == "caller"
            assert results[0].name == "process_order"

    def test_find_callees_finds_called_functions(self):
        """Test _find_callees finds functions called by target."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            # First call: get current function with calls
            # Second call: find the called function
            mock_store.query_by_metadata.side_effect = [
                [{"metadata": {"calls": ["get_items", "apply_discount"]}}],
                [
                    {
                        "metadata": {
                            "file_path": "src/items.py",
                            "name": "get_items",
                            "content": "def get_items(): ...",
                            "chunk_type": "function",
                        }
                    }
                ],
                [],  # apply_discount not found
            ]
            mock_store_fn.return_value = mock_store

            retriever = get_retriever()
            results = retriever._find_callees(
                namespace="owner/repo",
                file_path="src/utils.py",
                function_name="calculate_total",
            )

            assert len(results) == 1
            assert results[0].relationship == "callee"
            assert results[0].name == "get_items"

    def test_retrieve_handles_errors_gracefully(self):
        """Test that retrieve handles errors gracefully."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.query_by_metadata.side_effect = Exception("Connection error")
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
