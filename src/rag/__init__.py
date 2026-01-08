"""RAG (Retrieval-Augmented Generation) module for context-aware code review.

This module provides the RAG pipeline for enriching code reviews with
related context from the codebase.

Components:
- Chunker: Smart code chunking using AST
- Embedder: Text embedding generation (OpenAI/Gemini)
- Indexer: Codebase indexing orchestrator
- Retriever: Smart context retrieval with explicit relationships
- VectorStore: Pinecone vector store wrapper

Helper classes (call_resolution):
- CallParser: Parse function calls from code
- CalleeResolver: Resolve calls to indexed definitions
- CallerFinder: Find functions that call target
- TestFinder: Find tests for source functions
"""

from .call_resolution import CalleeResolver, CallerFinder, CallParser, TestFinder
from .chunker import Chunker, get_chunker
from .config import RAGSettings, get_rag_settings
from .embedder import Embedder, get_embedder
from .indexer import Indexer, create_indexer
from .retriever import Retriever, get_retriever
from .vector_store import VectorMatch, VectorStore, get_vector_store

__all__ = [
    # Core components
    "Chunker",
    "Embedder",
    "Indexer",
    "RAGSettings",
    "Retriever",
    "VectorStore",
    "VectorMatch",
    # Call resolution helpers
    "CallParser",
    "CalleeResolver",
    "CallerFinder",
    "TestFinder",
    # Factory functions
    "create_indexer",
    "get_chunker",
    "get_embedder",
    "get_rag_settings",
    "get_retriever",
    "get_vector_store",
]
