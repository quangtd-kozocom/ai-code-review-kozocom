"""RAG (Retrieval-Augmented Generation) module for context-aware code review.

This module has been refactored from a vector database approach to
AST-based direct analysis. The core functionality has moved to:
- src/analysis/ - New analysis module with AST-based approach

Remaining components:
- Chunker: Smart code chunking using AST (still useful for context)
- Config: Configuration settings

Removed (moved to analysis module):
- Embedder: No longer needed (removed Pinecone dependency)
- VectorStore: No longer needed (removed Pinecone dependency)
- Indexer: No longer needed (on-demand analysis instead)
- Retriever: Replaced by analysis/call_graph.py
"""

from .chunker import Chunker, get_chunker
from .config import RAGSettings, get_rag_settings

__all__ = [
    # Remaining components
    "Chunker",
    "RAGSettings",
    # Factory functions
    "get_chunker",
    "get_rag_settings",
]
