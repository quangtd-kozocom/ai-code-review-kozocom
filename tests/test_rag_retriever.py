"""Tests for RAG retriever module."""

from unittest.mock import MagicMock, patch

from src.ast.models import RelatedCode
from src.rag.retriever import get_retriever


class TestRetriever:
    """Tests for Retriever class."""

    def test_retrieve_returns_related_code(self):
        """Test that retrieve returns RelatedCode objects."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.query.return_value = [
                {
                    "id": "test.py:foo:1",
                    "score": 0.9,
                    "metadata": {
                        "file_path": "test.py",
                        "name": "foo",
                        "content": "def foo(): pass",
                        "chunk_type": "function",
                    },
                }
            ]
            mock_store_fn.return_value = mock_store

            with patch("src.rag.retriever.get_embedder") as mock_embedder_fn:
                mock_embedder = MagicMock()
                mock_embedder.embed_single.return_value = [0.1] * 1024
                mock_embedder_fn.return_value = mock_embedder

                retriever = get_retriever()
                results = retriever.retrieve("owner", "repo", "calculate_total")

                assert len(results) == 1
                assert isinstance(results[0], RelatedCode)
                assert results[0].name == "foo"
                assert results[0].relevance_score == 0.9

    def test_retrieve_for_function_builds_query(self):
        """Test that retrieve_for_function builds correct query."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.query.return_value = []
            mock_store_fn.return_value = mock_store

            with patch("src.rag.retriever.get_embedder") as mock_embedder_fn:
                mock_embedder = MagicMock()
                mock_embedder.embed_single.return_value = [0.1] * 1024
                mock_embedder_fn.return_value = mock_embedder

                retriever = get_retriever()
                retriever.retrieve_for_function(
                    owner="test",
                    repo="repo",
                    function_name="calculate",
                    signature="def calculate(x, y):",
                )

                # Check embed was called
                mock_embedder.embed_single.assert_called_once()
                call_args = mock_embedder.embed_single.call_args[0][0]
                assert "function calculate" in call_args
                assert "signature: def calculate(x, y):" in call_args

    def test_infer_relationship_test_file(self):
        """Test relationship inference for test files."""
        with patch("src.rag.retriever.get_vector_store"):
            with patch("src.rag.retriever.get_embedder"):
                retriever = get_retriever()
                relationship = retriever._infer_relationship(
                    query="calculate_total",
                    result_name="test_calculate_total",
                    result_file="tests/test_order.py",
                )
                assert relationship == "test"

    def test_infer_relationship_callee(self):
        """Test relationship inference for callee."""
        with patch("src.rag.retriever.get_vector_store"):
            with patch("src.rag.retriever.get_embedder"):
                retriever = get_retriever()
                relationship = retriever._infer_relationship(
                    query="calculate_total function",
                    result_name="calculate_total",
                    result_file="src/utils.py",
                )
                assert relationship == "callee"

    def test_infer_relationship_similar(self):
        """Test relationship inference defaults to similar."""
        with patch("src.rag.retriever.get_vector_store"):
            with patch("src.rag.retriever.get_embedder"):
                retriever = get_retriever()
                relationship = retriever._infer_relationship(
                    query="calculate_total",
                    result_name="compute_sum",
                    result_file="src/math.py",
                )
                assert relationship == "similar"

    def test_retrieve_handles_errors_gracefully(self):
        """Test that retrieve handles errors gracefully."""
        with patch("src.rag.retriever.get_vector_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.query.side_effect = Exception("Connection error")
            mock_store_fn.return_value = mock_store

            with patch("src.rag.retriever.get_embedder") as mock_embedder_fn:
                mock_embedder = MagicMock()
                mock_embedder.embed_single.return_value = [0.1] * 1024
                mock_embedder_fn.return_value = mock_embedder

                retriever = get_retriever()
                results = retriever.retrieve("owner", "repo", "query")

                # Should return empty list instead of raising
                assert results == []
