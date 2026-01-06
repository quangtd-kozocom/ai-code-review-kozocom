"""Pinecone vector store wrapper."""

import structlog
from pinecone import Pinecone, ServerlessSpec

from .config import get_rag_settings

log = structlog.get_logger()


class VectorStore:
    """Pinecone vector store operations."""

    def __init__(self) -> None:
        settings = get_rag_settings()
        if not settings.pinecone_api_key:
            log.warning("pinecone_api_key_not_configured")
            self.pc = None
        else:
            self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self._index = None
        self._settings = settings

    @property
    def index(self):
        """Get or create Pinecone index."""
        if self.pc is None:
            raise RuntimeError("Pinecone client not configured. Set PINECONE_API_KEY.")

        if self._index is None:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                # Create index
                log.info("creating_pinecone_index", index_name=self.index_name)
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self._settings.embedding_dimensions,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )

            self._index = self.pc.Index(self.index_name)

        return self._index

    def upsert(
        self,
        vectors: list[dict],
        namespace: str,
    ) -> None:
        """Upsert vectors to index.

        Args:
            vectors: List of {"id": str, "values": list[float], "metadata": dict}
            namespace: Namespace (repo identifier)
        """
        if not vectors:
            return

        # Batch upsert
        batch_size = self._settings.batch_size
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self.index.upsert(vectors=batch, namespace=namespace)
            log.debug("upserted_vectors", count=len(batch), namespace=namespace)

    def query(
        self,
        vector: list[float],
        namespace: str,
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list[dict]:
        """Query similar vectors.

        Returns:
            List of matches with scores and metadata
        """
        results = self.index.query(
            vector=vector,
            namespace=namespace,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
        )

        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata or {},
            }
            for match in results.matches
        ]

    def delete_by_file(self, namespace: str, file_path: str) -> None:
        """Delete all vectors for a specific file.

        Note: Pinecone serverless supports delete by metadata filter.
        """
        try:
            self.index.delete(
                namespace=namespace,
                filter={"file_path": {"$eq": file_path}},
            )
            log.info("deleted_vectors_for_file", namespace=namespace, file_path=file_path)
        except Exception as e:
            # Fallback: Log warning and skip
            log.warning(
                "delete_by_filter_failed",
                namespace=namespace,
                file_path=file_path,
                error=str(e),
            )

    def delete_namespace(self, namespace: str) -> None:
        """Delete entire namespace (all vectors for a repo)."""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            log.info("deleted_namespace", namespace=namespace)
        except Exception as e:
            log.warning("delete_namespace_failed", namespace=namespace, error=str(e))

    def describe_namespace(self, namespace: str) -> dict:
        """Get stats for a namespace."""
        try:
            stats = self.index.describe_index_stats()
            ns_stats = stats.namespaces.get(namespace, {})
            return {
                "vector_count": getattr(ns_stats, "vector_count", 0),
            }
        except Exception as e:
            log.warning("describe_namespace_failed", namespace=namespace, error=str(e))
            return {"vector_count": 0}


def get_vector_store() -> VectorStore:
    """Factory function to get VectorStore instance."""
    return VectorStore()
