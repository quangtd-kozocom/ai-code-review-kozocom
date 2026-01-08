"""Embedding service with support for multiple providers (OpenAI, Google Gemini)."""

from abc import ABC, abstractmethod

import structlog
from google import genai
from google.genai import types
from openai import APIError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..app.config import get_settings
from .config import get_rag_settings

log = structlog.get_logger()


class BaseEmbedder(ABC):
    """Abstract base class for embedders."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        pass

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        result = self.embed([text])
        if not result:
            raise ValueError("Failed to generate embedding")
        return result[0]


class OpenAIEmbedder(BaseEmbedder):
    """Generate embeddings using OpenAI API."""

    def __init__(self) -> None:
        rag_settings = get_rag_settings()
        app_settings = get_settings()
        self.client = OpenAI(api_key=app_settings.OPENAI_API_KEY)
        self.model = rag_settings.openai_embedding_model
        self.dimensions = rag_settings.openai_embedding_dimensions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=lambda retry_state: log.warning(
            "openai_embedding_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()) if retry_state.outcome else "Unknown error",
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


class GeminiEmbedder(BaseEmbedder):
    """Generate embeddings using Google Gemini API (free tier available)."""

    def __init__(self) -> None:
        rag_settings = get_rag_settings()
        self.client = genai.Client(api_key=rag_settings.google_api_key)
        self.model = rag_settings.gemini_embedding_model
        self.dimensions = rag_settings.gemini_embedding_dimensions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: log.warning(
            "gemini_embedding_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()) if retry_state.outcome else "Unknown error",
        ),
    )
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        result = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dimensions,
            ),
        )

        return [embedding.values for embedding in result.embeddings]


def get_embedder() -> BaseEmbedder:
    """Factory function to get Embedder instance based on configured provider."""
    rag_settings = get_rag_settings()
    provider = rag_settings.embedding_provider.lower()

    if provider == "gemini":
        log.info("using_gemini_embedder", model=rag_settings.gemini_embedding_model)
        return GeminiEmbedder()
    elif provider == "openai":
        log.info("using_openai_embedder", model=rag_settings.openai_embedding_model)
        return OpenAIEmbedder()
    else:
        raise ValueError(f"Unknown embedding provider: {provider}. Use 'openai' or 'gemini'.")


# Backward compatibility alias
Embedder = OpenAIEmbedder
