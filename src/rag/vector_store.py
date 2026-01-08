"""Pinecone vector store wrapper with proper metadata query support.

Uses Pinecone's fetch_by_metadata API (2025-10) for pure metadata queries.
"""

from dataclasses import dataclass
from functools import cache

import structlog
from pinecone import Pinecone, ServerlessSpec

from .config import get_rag_settings

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """A match from vector store query."""

    id: str
    score: float
    metadata: dict


class VectorStore:
    """Pinecone vector store operations with proper metadata query support.

    Uses the fetch_by_metadata API (Pinecone 2025-10) for pure metadata queries.
    """

    def __init__(self) -> None:
        settings = get_rag_settings()
        if not settings.pinecone_api_key:
            log.warning("pinecone_api_key_not_configured")
            self._pc = None
        else:
            self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index_name = settings.pinecone_index_name
        self._index = None
        self._settings = settings

    @property
    def index(self):
        """Get or create Pinecone index."""
        if self._pc is None:
            raise RuntimeError("Pinecone client not configured. Set PINECONE_API_KEY.")

        if self._index is None:
            existing_indexes = [idx.name for idx in self._pc.list_indexes()]

            if self._index_name not in existing_indexes:
                log.info("creating_pinecone_index", index_name=self._index_name)
                self._pc.create_index(
                    name=self._index_name,
                    dimension=self._settings.embedding_dimensions,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )

            self._index = self._pc.Index(self._index_name)

        return self._index

    @property
    def is_configured(self) -> bool:
        """Check if Pinecone is properly configured."""
        return self._pc is not None

    def upsert(self, vectors: list[dict], namespace: str) -> None:
        """Upsert vectors to index.

        Args:
            vectors: List of {"id": str, "values": list[float], "metadata": dict}
            namespace: Namespace (repo identifier)
        """
        if not vectors:
            return

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
    ) -> list[VectorMatch]:
        """Query similar vectors using vector similarity.

        Args:
            vector: Query vector for similarity search.
            namespace: Namespace to search in.
            top_k: Maximum number of results.
            filter: Optional metadata filter.

        Returns:
            List of VectorMatch objects.
        """
        results = self.index.query(
            vector=vector,
            namespace=namespace,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
        )

        return [
            VectorMatch(
                id=match.id,
                score=match.score,
                metadata=match.metadata or {},
            )
            for match in results.matches
        ]

    def fetch_by_metadata(
        self,
        namespace: str,
        filter: dict,
        limit: int = 10,
    ) -> list[VectorMatch]:
        """Fetch vectors by metadata filter (no vector required).

        Uses Pinecone's native fetch_by_metadata API (2025-10).

        Args:
            namespace: Namespace to search in.
            filter: Metadata filter dict using Pinecone filter syntax.
            limit: Maximum number of results.

        Returns:
            List of VectorMatch objects matching the filter.
        """
        if self._pc is None:
            return []

        try:
            response = self.index.fetch_by_metadata(
                namespace=namespace,
                filter=filter,
                limit=limit,
            )

            # Response format: {"vectors": {"id-1": {...}, "id-2": {...}}, "namespace": "..."}
            vectors_dict = response.get("vectors", {})

            matches = [
                VectorMatch(
                    id=vec_id,
                    score=1.0,  # fetch_by_metadata doesn't return scores
                    metadata=vec_data.get("metadata", {}),
                )
                for vec_id, vec_data in vectors_dict.items()
            ]

            log.debug(
                "fetch_by_metadata.success",
                namespace=namespace,
                filter=filter,
                count=len(matches),
            )
            return matches

        except Exception as e:
            log.warning("fetch_by_metadata.failed", error=str(e), filter=filter)
            return []

    def delete_by_file(self, namespace: str, file_path: str) -> None:
        """Delete all vectors for a specific file."""
        try:
            self.index.delete(
                namespace=namespace,
                filter={"file_path": {"$eq": file_path}},
            )
            log.info("deleted_vectors_for_file", namespace=namespace, file_path=file_path)
        except Exception as e:
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


@cache
def get_vector_store() -> VectorStore:
    """Factory function to get VectorStore instance (cached)."""
    return VectorStore()


def reset_vector_store() -> None:
    """Reset the cached instance (for testing)."""
    get_vector_store.cache_clear()
