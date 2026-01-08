"""Smart context retrieval with explicit relationships.

This module implements the RAG v2 retrieval strategy that uses explicit
relationships (TEST, CALLER, CALLEE) instead of semantic similarity.

Key improvements over v1:
- No semantic similarity fallback (reduces noise)
- Explicit relationship types for context quality
- Test file discovery using naming conventions
- Caller/callee detection using indexed function calls
"""

import structlog

from src.ast.models import RelatedCode
from src.languages import get_plugin_for_file

from .config import get_rag_settings
from .vector_store import get_vector_store

log = structlog.get_logger()


class Retriever:
    """Retrieve related code using explicit relationships only.

    This retriever finds code that has explicit relationships with the
    target code, avoiding noisy semantic similarity matches.

    Relationship types:
    - TEST: Test functions/files for the target
    - CALLER: Functions that call the target function
    - CALLEE: Functions that the target function calls
    """

    def __init__(self) -> None:
        self._store = get_vector_store()
        self._settings = get_rag_settings()

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
                test = self._find_test(namespace, file_path, function_name, plugin)
                if test:
                    log.debug("retriever.found_test", func=function_name, test=test.name)
                    results.append(test)

            # 2. Find CALLERS (functions that call this function)
            callers = self._find_callers(namespace, file_path, function_name)
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
    ) -> list[RelatedCode]:
        """Retrieve context for a specific function.

        This is the main entry point for the context extractor.

        Args:
            owner: Repository owner.
            repo: Repository name.
            function_name: Name of the function.
            signature: Function signature (not used in v2, kept for API compat).
            current_file: Path to the file containing the function.

        Returns:
            List of RelatedCode with explicit relationships.
        """
        if not current_file:
            log.warning("retriever.no_file_path", func=function_name)
            return []

        return self.retrieve(
            owner=owner,
            repo=repo,
            file_path=current_file,
            function_name=function_name,
        )

    def _find_test(
        self, namespace: str, file_path: str, function_name: str, plugin
    ) -> RelatedCode | None:
        """Find test file/function using patterns.

        Uses language-specific test patterns to find relevant tests.
        """
        test_paths = plugin.get_test_patterns(file_path)

        for test_path in test_paths:
            results = self._store.query_by_metadata(
                namespace=namespace,
                filter={"file_path": test_path},
                top_k=10,
            )
            if not results:
                continue

            # Look for test function matching the source function
            for r in results:
                name = r["metadata"].get("name", "")
                # Check if function name appears in test name
                # e.g., test_calculate for function calculate
                if function_name.lower() in name.lower():
                    return RelatedCode(
                        file_path=r["metadata"]["file_path"],
                        name=name,
                        content=r["metadata"].get("content", ""),
                        chunk_type=r["metadata"].get("chunk_type", "function"),
                        relevance_score=1.0,
                        relationship="test",
                        start_line=r["metadata"].get("start_line", 0),
                        end_line=r["metadata"].get("end_line", 0),
                    )
        return None

    def _find_callers(
        self, namespace: str, file_path: str, function_name: str
    ) -> list[RelatedCode]:
        """Find functions that call this function.

        Searches indexed metadata for functions that have this function
        in their 'calls' list.
        """
        results = self._store.query_by_metadata(
            namespace=namespace,
            filter={
                "calls": {"$in": [function_name]},
                "file_path": {"$ne": file_path},
            },
            top_k=5,
        )
        return [
            RelatedCode(
                file_path=r["metadata"]["file_path"],
                name=r["metadata"]["name"],
                content=r["metadata"].get("content", ""),
                chunk_type=r["metadata"].get("chunk_type", "function"),
                relevance_score=1.0,
                relationship="caller",
                start_line=r["metadata"].get("start_line", 0),
                end_line=r["metadata"].get("end_line", 0),
            )
            for r in results
        ]

    def _find_callees(
        self, namespace: str, file_path: str, function_name: str
    ) -> list[RelatedCode]:
        """Find functions that this function calls.

        First retrieves the function to get its 'calls' list,
        then finds definitions for those called functions.
        """
        # Get current function's calls
        current = self._store.query_by_metadata(
            namespace=namespace,
            filter={"file_path": file_path, "name": function_name},
            top_k=1,
        )
        if not current:
            return []

        called = current[0]["metadata"].get("calls", [])
        if not called:
            return []

        callees = []
        for name in called[:5]:  # Limit to 5 calls to reduce queries
            results = self._store.query_by_metadata(
                namespace=namespace,
                filter={"name": name, "file_path": {"$ne": file_path}},
                top_k=1,
            )
            if results:
                r = results[0]
                callees.append(
                    RelatedCode(
                        file_path=r["metadata"]["file_path"],
                        name=r["metadata"]["name"],
                        content=r["metadata"].get("content", ""),
                        chunk_type=r["metadata"].get("chunk_type", "function"),
                        relevance_score=1.0,
                        relationship="callee",
                        start_line=r["metadata"].get("start_line", 0),
                        end_line=r["metadata"].get("end_line", 0),
                    )
                )
        return callees


def get_retriever() -> Retriever:
    """Factory function to get Retriever instance."""
    return Retriever()
