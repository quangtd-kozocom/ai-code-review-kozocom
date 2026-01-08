"""Smart context retrieval with explicit relationships.

This module implements the RAG v2 retrieval strategy that uses explicit
relationships (TEST, CALLER, CALLEE) instead of semantic similarity.

Key improvements over v1:
- No semantic similarity fallback (reduces noise)
- Explicit relationship types for context quality
- Test file discovery using naming conventions
- Caller/callee detection using indexed function calls

Refactored to use extracted helper classes for better maintainability:
- CallParser: Parse function calls from code
- CalleeResolver: Resolve calls to indexed definitions
- CallerFinder: Find functions that call target
- TestFinder: Find tests for source functions
"""

import structlog

from src.ast.models import RelatedCode
from src.languages import get_plugin_for_file

from .call_resolution import CalleeResolver, CallerFinder, CallParser, TestFinder
from .config import get_rag_settings
from .vector_store import VectorStore, get_vector_store

log = structlog.get_logger()


class Retriever:
    """Retrieve related code using explicit relationships only.

    This retriever finds code that has explicit relationships with the
    target code, avoiding noisy semantic similarity matches.

    Relationship types:
    - TEST: Test functions/files for the target
    - CALLER: Functions that call the target function
    - CALLEE: Functions that the target function calls

    Uses dependency injection via constructor for better testability.
    """

    def __init__(
        self,
        store: VectorStore | None = None,
        call_parser: CallParser | None = None,
        callee_resolver: CalleeResolver | None = None,
        caller_finder: CallerFinder | None = None,
        test_finder: TestFinder | None = None,
    ) -> None:
        """Initialize retriever with optional dependency injection.

        Args:
            store: Vector store instance (defaults to cached singleton).
            call_parser: Call parser instance.
            callee_resolver: Callee resolver instance.
            caller_finder: Caller finder instance.
            test_finder: Test finder instance.
        """
        self._store = store or get_vector_store()
        self._settings = get_rag_settings()

        # Initialize helper components with the store
        self._call_parser = call_parser or CallParser()
        self._callee_resolver = callee_resolver or CalleeResolver(self._store)
        self._caller_finder = caller_finder or CallerFinder(self._store)
        self._test_finder = test_finder or TestFinder(self._store)

    def retrieve(
        self,
        owner: str,
        repo: str,
        file_path: str,
        function_name: str,
    ) -> list[RelatedCode]:
        """Retrieve explicitly related code.

        Args:
            owner: Repository owner.
            repo: Repository name.
            file_path: Path to the source file.
            function_name: Name of the function to find relations for.

        Returns:
            List of RelatedCode with relationship: 'test', 'caller', or 'callee'
        """
        namespace = f"{owner}/{repo}"
        plugin = get_plugin_for_file(file_path)
        results: list[RelatedCode] = []

        try:
            # 1. Find TEST
            if plugin:
                test = self._test_finder.find(namespace, file_path, function_name, plugin)
                if test:
                    log.debug("retriever.found_test", func=function_name, test=test.name)
                    results.append(test)

            # 2. Find CALLERS (functions that call this function)
            callers = self._caller_finder.find(namespace, function_name, file_path)
            for c in callers[:2]:
                log.debug(
                    "retriever.found_caller",
                    func=function_name,
                    caller=c.name,
                    file=c.file_path,
                )
            results.extend(callers[:2])

            # 3. Find CALLEES (functions this function calls)
            callees = self._find_callees(namespace, file_path, function_name)
            for c in callees[:2]:
                log.debug(
                    "retriever.found_callee",
                    func=function_name,
                    callee=c.name,
                    file=c.file_path,
                )
            results.extend(callees[:2])

            log.info(
                "retriever.complete",
                file=file_path,
                func=function_name,
                count=len(results),
            )
        except Exception as e:
            log.warning("retriever.failed", error=str(e), file=file_path)
            return []

        return results

    def retrieve_for_function(
        self,
        owner: str,
        repo: str,
        function_name: str,
        signature: str | None = None,
        current_file: str | None = None,
        function_content: str | None = None,
    ) -> list[RelatedCode]:
        """Retrieve context for a specific function.

        This is the main entry point for the context extractor.

        Args:
            owner: Repository owner.
            repo: Repository name.
            function_name: Name of the function.
            signature: Function signature (not used in v2, kept for API compat).
            current_file: Path to the file containing the function.
            function_content: Content of the function (for new functions not in index).

        Returns:
            List of RelatedCode with explicit relationships.
        """
        if not current_file:
            log.warning("retriever.no_file_path", func=function_name)
            return []

        # First try normal retrieval (function exists in index)
        results = self.retrieve(
            owner=owner,
            repo=repo,
            file_path=current_file,
            function_name=function_name,
        )

        # If no results and we have function content, try to find callees
        # by parsing the content directly (for new functions not in index)
        if not results and function_content:
            log.debug(
                "retriever.trying_content_parse",
                func=function_name,
                file=current_file,
            )
            results = self._find_callees_from_content(
                owner=owner,
                repo=repo,
                file_path=current_file,
                function_content=function_content,
            )

        return results

    def _find_callees(
        self, namespace: str, file_path: str, function_name: str
    ) -> list[RelatedCode]:
        """Find functions that this function calls.

        First retrieves the function to get its 'calls' list,
        then finds definitions for those called functions.
        """
        # Get current function's calls from index
        results = self._store.fetch_by_metadata(
            namespace=namespace,
            filter={"file_path": file_path, "name": function_name},
            limit=1,
        )

        if not results:
            return []

        # Get metadata from result
        match = results[0]
        metadata = match.metadata if hasattr(match, "metadata") else match.get("metadata", {})

        # Validate we got the exact function
        if metadata.get("name") != function_name:
            log.debug(
                "retriever.callee_mismatch",
                expected=function_name,
                got=metadata.get("name"),
            )
            return []

        calls = metadata.get("calls", [])
        if not calls:
            return []

        # Resolve calls to definitions
        resolved = self._callee_resolver.resolve(
            namespace=namespace,
            calls=calls,
            current_file=file_path,
            max_results=5,
        )

        return [r.to_related_code() for r in resolved]

    def _find_callees_from_content(
        self,
        owner: str,
        repo: str,
        file_path: str,
        function_content: str,
    ) -> list[RelatedCode]:
        """Find callees by parsing function content directly.

        Used for new functions that aren't in the index yet.
        Parses their content to find function calls, then looks up
        those functions in the index.
        """
        namespace = f"{owner}/{repo}"

        # Parse calls from function content
        calls = self._call_parser.parse(file_path, function_content)
        if not calls:
            return []

        log.debug(
            "retriever.parsed_calls_from_content",
            file=file_path,
            calls=calls[:10],
        )

        # Resolve calls to definitions
        resolved = self._callee_resolver.resolve(
            namespace=namespace,
            calls=calls,
            current_file=file_path,
            max_results=5,
        )

        callees = [r.to_related_code() for r in resolved]

        log.info(
            "retriever.found_callees_from_content",
            count=len(callees),
            file=file_path,
        )
        return callees


# =============================================================================
# Factory
# =============================================================================


def get_retriever() -> Retriever:
    """Factory function to get Retriever instance."""
    return Retriever()
