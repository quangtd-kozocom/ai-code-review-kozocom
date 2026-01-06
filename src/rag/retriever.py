"""Context retrieval from RAG."""

import structlog

from src.ast.models import RelatedCode

from .config import get_rag_settings
from .embedder import get_embedder
from .vector_store import get_vector_store

log = structlog.get_logger()


class Retriever:
    """Retrieve related code context from indexed codebase."""

    def __init__(self) -> None:
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._settings = get_rag_settings()

    def retrieve(
        self,
        owner: str,
        repo: str,
        query: str,
        exclude_file: str | None = None,
        top_k: int | None = None,
    ) -> list[RelatedCode]:
        """Retrieve related code for a query.

        Args:
            owner: Repo owner
            repo: Repo name
            query: Search query (function signature, code snippet, etc.)
            exclude_file: File to exclude from results (usually the file being reviewed)
            top_k: Number of results to return

        Returns:
            List of related code chunks
        """
        namespace = f"{owner}/{repo}"
        top_k = top_k or self._settings.top_k

        try:
            # Embed query
            query_embedding = self._embedder.embed_single(query)

            # Build filter
            filter_dict = None
            if exclude_file:
                filter_dict = {"file_path": {"$ne": exclude_file}}

            # Query Pinecone
            results = self._vector_store.query(
                vector=query_embedding,
                namespace=namespace,
                top_k=top_k,
                filter=filter_dict,
            )

            # Convert to RelatedCode
            related: list[RelatedCode] = []
            for result in results:
                metadata = result["metadata"]

                # Infer relationship
                relationship = self._infer_relationship(
                    query=query,
                    result_name=metadata.get("name", ""),
                    result_file=metadata.get("file_path", ""),
                )

                related.append(
                    RelatedCode(
                        file_path=metadata.get("file_path", ""),
                        name=metadata.get("name", ""),
                        content=metadata.get("content", ""),
                        chunk_type=metadata.get("chunk_type", ""),
                        relevance_score=result["score"],
                        relationship=relationship,
                    )
                )

            log.debug(
                "retrieved_related_code",
                namespace=namespace,
                query_length=len(query),
                results_count=len(related),
            )
            return related

        except Exception as e:
            log.warning("retrieval_failed", namespace=namespace, error=str(e))
            return []

    def retrieve_for_function(
        self,
        owner: str,
        repo: str,
        function_name: str,
        signature: str | None = None,
        current_file: str | None = None,
    ) -> list[RelatedCode]:
        """Retrieve context for a specific function."""
        # Build rich query
        query_parts = [f"function {function_name}"]
        if signature:
            query_parts.append(f"signature: {signature}")

        query = " ".join(query_parts)

        return self.retrieve(
            owner=owner,
            repo=repo,
            query=query,
            exclude_file=current_file,
        )

    def _infer_relationship(
        self,
        query: str,
        result_name: str,
        result_file: str,
    ) -> str:
        """Infer the relationship between query and result."""
        # Check if it's a test file
        if "test" in result_file.lower():
            return "test"

        # Check if names match (caller/callee)
        query_lower = query.lower()
        if result_name.lower() in query_lower:
            return "callee"

        # Default to similar
        return "similar"


def get_retriever() -> Retriever:
    """Factory function to get Retriever instance."""
    return Retriever()
