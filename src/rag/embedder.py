"""Embedding service using OpenAI."""

import structlog
from openai import APIError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import get_rag_settings

log = structlog.get_logger()


class Embedder:
    """Generate embeddings using OpenAI API."""

    def __init__(self) -> None:
        settings = get_rag_settings()
        self.client = OpenAI()
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=lambda retry_state: log.warning(
            "embedding_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
        ),
    )
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )

        return [item.embedding for item in response.data]

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        result = self.embed([text])
        if not result:
            raise ValueError("Failed to generate embedding")
        return result[0]


def get_embedder() -> Embedder:
    """Factory function to get Embedder instance."""
    return Embedder()
