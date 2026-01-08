"""RAG enrichment service for PR file context.

This module extracts the RAG enrichment logic from context_extractor.py
into a dedicated service class for better maintainability and testability.
"""

import re
from contextlib import asynccontextmanager

import structlog

from src.agents.state import EnhancedFileChange, FileChange, PRContext
from src.ast.models import ASTInfo, FunctionInfo
from src.ast.parser import CodeParser, get_code_parser
from src.core.protocols import GitHubClientProtocol
from src.rag.config import get_rag_settings
from src.rag.retriever import Retriever, get_retriever

log = structlog.get_logger()


class RAGEnricher:
    """Enrich PR files with RAG context.

    Extracts related code context for changed functions using the RAG
    retrieval system. Supports both indexed functions and new functions
    via content parsing.
    """

    def __init__(
        self,
        github: GitHubClientProtocol,
        parser: CodeParser | None = None,
        retriever: Retriever | None = None,
    ) -> None:
        """Initialize enricher with dependencies.

        Args:
            github: GitHub client for fetching file content.
            parser: Code parser (defaults to cached instance).
            retriever: RAG retriever (defaults to new instance).
        """
        self._github = github
        self._parser = parser or get_code_parser()
        self._retriever = retriever or get_retriever()
        self._settings = get_rag_settings()

    async def enrich_files(
        self,
        files: list[FileChange],
        ctx: PRContext,
    ) -> list[FileChange | EnhancedFileChange]:
        """Enrich files with RAG context.

        Args:
            files: List of PR file changes.
            ctx: PR context with owner, repo, pr_number.

        Returns:
            List of files, with enrichable files converted to EnhancedFileChange.
        """
        if not self._settings.pinecone_api_key:
            log.debug("rag_enricher.not_configured")
            return files

        # Get PR head SHA for file fetching
        pr_details = await self._github.get_pr_details(ctx.owner, ctx.repo, ctx.pr_number)
        head_sha = pr_details.get("head", {}).get("sha", "HEAD")

        enriched_count = 0
        result_files: list[FileChange | EnhancedFileChange] = []

        for file in files:
            enriched = await self._enrich_single_file(file, ctx, head_sha)
            if enriched is not file:
                enriched_count += 1
            result_files.append(enriched)

        log.info("rag_enricher.complete", enriched_count=enriched_count, total=len(files))
        return result_files

    async def _enrich_single_file(
        self,
        file: FileChange,
        ctx: PRContext,
        head_sha: str,
    ) -> FileChange | EnhancedFileChange:
        """Enrich a single file with RAG context.

        Args:
            file: File change to enrich.
            ctx: PR context.
            head_sha: Git SHA for file content.

        Returns:
            EnhancedFileChange if enriched, original FileChange otherwise.
        """
        # Skip files that can't be enriched
        if not self._can_enrich(file):
            return file

        try:
            # Fetch file content
            content = await self._github.get_file_raw(ctx.owner, ctx.repo, file.filename, head_sha)
            if not content:
                return file

            # Parse AST
            ast_info = self._parser.get_ast_info(file.filename, content)
            if not ast_info:
                return file

            # Find changed functions
            changed_funcs = self._identify_changed_functions(ast_info, file.patch)
            if not changed_funcs:
                return file

            # Retrieve context for each changed function
            related = await self._retrieve_context_for_functions(
                changed_funcs, content, ctx, file.filename
            )

            if not related:
                return file

            # Build enriched file change
            return self._build_enhanced_file(file, content, ast_info, related)

        except Exception as e:
            log.debug(
                "rag_enricher.file_failed",
                file=file.filename,
                error=str(e),
            )
            return file

    def _can_enrich(self, file: FileChange) -> bool:
        """Check if file can be enriched with RAG context."""
        if file.status not in ("modified", "added"):
            return False

        if not self._parser.detect_language(file.filename):
            return False

        return True

    def _identify_changed_functions(self, ast_info: ASTInfo, patch: str) -> list[FunctionInfo]:
        """Identify functions that have changes in their body.

        Uses strict detection: function must have at least one added line
        within its body.
        """
        added_lines = set(self._parse_added_lines(patch))

        if not added_lines:
            return []

        changed_funcs = []
        for func in ast_info.functions:
            func_range = set(range(func.start_line, func.end_line + 1))
            if added_lines & func_range:
                changed_funcs.append(func)
                log.debug(
                    "rag_enricher.changed_func",
                    func=func.name,
                    range=f"L{func.start_line}-{func.end_line}",
                )

        return changed_funcs

    def _parse_added_lines(self, patch: str) -> list[int]:
        """Extract line numbers of added lines from diff.

        Parses lines with + prefix (excluding +++ header).
        """
        added_lines = []
        current_line = 0

        for line in patch.split("\n"):
            # Match hunk header
            hunk_match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match:
                current_line = int(hunk_match.group(1))
                continue

            if current_line == 0:
                continue

            match line[:1]:
                case "+":
                    if not line.startswith("+++"):
                        added_lines.append(current_line)
                    current_line += 1
                case "-":
                    pass  # Deleted line, no line number increment
                case _:
                    current_line += 1

        return added_lines

    async def _retrieve_context_for_functions(
        self,
        functions: list[FunctionInfo],
        file_content: str,
        ctx: PRContext,
        file_path: str,
    ) -> list:
        """Retrieve RAG context for changed functions."""
        related = []

        for func in functions[:3]:  # Limit to first 3 functions
            func_content = self._extract_function_content(file_content, func)
            results = self._retriever.retrieve_for_function(
                owner=ctx.owner,
                repo=ctx.repo,
                function_name=func.name,
                signature=func.signature,
                current_file=file_path,
                function_content=func_content,
            )
            related.extend(results)

        return related

    def _extract_function_content(self, file_content: str, func: FunctionInfo) -> str:
        """Extract function content using line numbers."""
        lines = file_content.split("\n")
        start_idx = func.start_line - 1
        end_idx = func.end_line
        return "\n".join(lines[start_idx:end_idx])

    def _build_enhanced_file(
        self,
        file: FileChange,
        content: str,
        ast_info: ASTInfo,
        related: list,
    ) -> EnhancedFileChange:
        """Build EnhancedFileChange with RAG context."""
        log.debug(
            "rag_enricher.enriched",
            file=file.filename,
            related_count=len(related),
        )

        return EnhancedFileChange(
            filename=file.filename,
            status=file.status,
            additions=file.additions,
            deletions=file.deletions,
            patch=file.patch,
            language=file.language,
            full_content=content,
            ast_info=ast_info,
            related_context=related,
        )


@asynccontextmanager
async def create_rag_enricher(github: GitHubClientProtocol):
    """Async context manager for RAGEnricher.

    Usage:
        async with create_rag_enricher(github) as enricher:
            files = await enricher.enrich_files(files, ctx)
    """
    enricher = RAGEnricher(github)
    try:
        yield enricher
    finally:
        # Cleanup if needed
        pass
