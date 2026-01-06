"""Code chunking logic."""

import fnmatch
import re
from pathlib import Path

import structlog

from src.ast.models import CodeChunk
from src.ast.parser import get_code_parser

from .config import INCLUDE_EXTENSIONS, RAG_EXCLUDE_PATTERNS, get_rag_settings

log = structlog.get_logger()


class Chunker:
    """Smart code chunking using AST."""

    def __init__(self) -> None:
        self._settings = get_rag_settings()
        self._parser = get_code_parser()

    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed."""
        path = Path(file_path)

        # Check extension against LANGUAGE_MAP keys
        ext = path.suffix.lower()
        if ext not in INCLUDE_EXTENSIONS:
            return False

        # Check exclude patterns
        for pattern in RAG_EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(file_path, pattern):
                return False
            # Also check with wildcard prefix for nested paths
            if fnmatch.fnmatch(file_path, f"*/{pattern}"):
                return False

        return True

    def has_secrets(self, content: str) -> bool:
        """Check if content contains potential secrets."""
        secret_patterns = [
            r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][^'\"]{10,}['\"]",
            r"(?i)(secret|password|token|credential)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
            r"(?i)bearer\s+[a-zA-Z0-9\-_.]+",
        ]
        for pattern in secret_patterns:
            if re.search(pattern, content):
                return True
        return False

    def chunk_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Chunk a single file into semantic units."""
        if not self.should_process_file(file_path):
            return []

        if self.has_secrets(content):
            log.warning("skipping_file_with_secrets", file_path=file_path)
            return []

        chunks = self._parser.parse_file(file_path, content)

        # If no chunks extracted (parsing failed or unsupported),
        # fall back to whole file as single chunk
        if not chunks:
            language = self._parser.detect_language(file_path) or "unknown"
            chunks = [
                CodeChunk(
                    chunk_type="module",
                    name=Path(file_path).stem,
                    content=content[:5000],  # Limit size
                    file_path=file_path,
                    start_line=1,
                    end_line=content.count("\n") + 1,
                    language=language,
                )
            ]

        return chunks

    def chunk_directory(self, root_path: str, files: dict[str, str]) -> list[CodeChunk]:
        """Chunk all files in a directory.

        Args:
            root_path: Root path for relative file paths
            files: Dict of {relative_path: content}

        Returns:
            List of all chunks
        """
        all_chunks: list[CodeChunk] = []

        for file_path, content in files.items():
            chunks = self.chunk_file(file_path, content)
            all_chunks.extend(chunks)

        log.info(
            "chunked_directory",
            root_path=root_path,
            files_processed=len(files),
            chunks_created=len(all_chunks),
        )
        return all_chunks


def get_chunker() -> Chunker:
    """Factory function to get Chunker instance."""
    return Chunker()
