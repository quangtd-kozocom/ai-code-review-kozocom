"""Codebase indexing orchestrator."""

import asyncio
import shutil
import tempfile
from pathlib import Path

import structlog
from git import Repo

from .chunker import get_chunker
from .config import get_rag_settings
from .embedder import get_embedder
from .vector_store import get_vector_store

log = structlog.get_logger()


class Indexer:
    """Orchestrate codebase indexing."""

    def __init__(self, github_service=None) -> None:
        """Initialize indexer.

        Args:
            github_service: GitHub service for authenticated operations.
                           Can be None for public repos.
        """
        self.github = github_service
        self._chunker = get_chunker()
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._settings = get_rag_settings()

    async def index_repository(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        installation_id: int | None = None,
    ) -> dict:
        """Index an entire repository.

        Returns:
            Stats about indexing: files_processed, chunks_created, etc.
        """
        namespace = f"{owner}/{repo}"
        stats = {
            "files_processed": 0,
            "chunks_created": 0,
            "files_skipped": 0,
            "namespace": namespace,
        }

        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="rag_index_")
        log.info(
            "starting_repository_index",
            owner=owner,
            repo=repo,
            branch=branch,
            temp_dir=temp_dir,
        )

        try:
            # Clone repository (shallow) - use asyncio.to_thread for blocking I/O
            clone_url = await self._get_clone_url(owner, repo, installation_id)
            repo_path = Path(temp_dir) / repo

            await asyncio.to_thread(
                Repo.clone_from,
                clone_url,
                repo_path,
                depth=1,
                branch=branch,
            )
            log.info("cloned_repository", repo_path=str(repo_path))

            # Collect files
            files: dict[str, str] = {}
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(repo_path))

                    if not self._chunker.should_process_file(relative_path):
                        stats["files_skipped"] += 1
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8")
                        files[relative_path] = content
                        stats["files_processed"] += 1
                    except (UnicodeDecodeError, OSError):
                        stats["files_skipped"] += 1

            log.info(
                "collected_files",
                files_processed=stats["files_processed"],
                files_skipped=stats["files_skipped"],
            )

            # Chunk all files
            chunks = self._chunker.chunk_directory(str(repo_path), files)
            stats["chunks_created"] = len(chunks)

            # Clear existing namespace before reindexing
            self._vector_store.delete_namespace(namespace)

            # Embed and store
            await self._embed_and_store(chunks, namespace)

            log.info("completed_repository_index", stats=stats)

        except Exception as e:
            log.error("repository_index_failed", owner=owner, repo=repo, error=str(e))
            raise

        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

        return stats

    async def update_files(
        self,
        owner: str,
        repo: str,
        files: list[dict],  # [{filename, status, content}]
    ) -> dict:
        """Incrementally update index for changed files.

        Args:
            files: List of {filename, status: added|modified|removed, content}
        """
        namespace = f"{owner}/{repo}"
        stats = {"added": 0, "modified": 0, "removed": 0}

        for file_info in files:
            filename = file_info["filename"]
            status = file_info["status"]
            content = file_info.get("content")

            if status == "removed":
                # Delete vectors for this file
                self._vector_store.delete_by_file(namespace, filename)
                stats["removed"] += 1

            elif status in ("added", "modified"):
                # For modified files, delete old vectors first
                if status == "modified":
                    self._vector_store.delete_by_file(namespace, filename)

                # Parse and index new content
                if content:
                    chunks = self._chunker.chunk_file(filename, content)
                    await self._embed_and_store(chunks, namespace)
                    stats[status] += 1

        log.info(
            "updated_repository_index",
            namespace=namespace,
            stats=stats,
        )
        return stats

    async def _embed_and_store(
        self,
        chunks: list,
        namespace: str,
    ) -> None:
        """Embed chunks and store in vector DB."""
        if not chunks:
            return

        # Prepare texts for embedding
        texts = [chunk.to_embedding_text() for chunk in chunks]

        # Batch embed
        batch_size = self._settings.batch_size
        all_vectors: list[dict] = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_chunks = chunks[i : i + batch_size]

            embeddings = self._embedder.embed(batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings, strict=True):
                all_vectors.append(
                    {
                        "id": chunk.id,
                        "values": embedding,
                        "metadata": {
                            "file_path": chunk.file_path,
                            "name": chunk.name,
                            "chunk_type": chunk.chunk_type,
                            "content": chunk.content[:1000],  # Truncate for metadata
                            "start_line": chunk.start_line,
                            "end_line": chunk.end_line,
                            "language": chunk.language,
                            # RAG v2: Relationship data
                            "imports": chunk.imports,
                            "calls": chunk.calls,
                        },
                    }
                )

        # Upsert to Pinecone
        self._vector_store.upsert(all_vectors, namespace)

    async def _get_clone_url(
        self,
        owner: str,
        repo: str,
        installation_id: int | None,
    ) -> str:
        """Get authenticated clone URL."""
        if installation_id and self.github:
            token = await self.github.get_installation_token(installation_id)
            return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        return f"https://github.com/{owner}/{repo}.git"


def create_indexer(github_service=None) -> Indexer:
    """Factory function to create Indexer instance."""
    return Indexer(github_service)
