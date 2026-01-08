"""Call parsing and callee resolution services.

This module extracts function call parsing and resolution logic from the
main Retriever class into smaller, focused components.
"""

from dataclasses import dataclass

import structlog

from src.ast.models import RelatedCode
from src.core.protocols import LanguagePluginProtocol, VectorStoreProtocol
from src.languages import get_plugin_for_file

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class ResolvedCallee:
    """A resolved function call from the vector store."""

    file_path: str
    name: str
    content: str
    chunk_type: str
    from_same_file: bool = False
    start_line: int = 0
    end_line: int = 0

    def to_related_code(self) -> RelatedCode:
        """Convert to RelatedCode."""
        return RelatedCode(
            file_path=self.file_path,
            name=self.name,
            content=self.content,
            chunk_type=self.chunk_type,
            relevance_score=0.9 if self.from_same_file else 1.0,
            relationship="callee",
            start_line=self.start_line,
            end_line=self.end_line,
        )


class CallParser:
    """Parse function calls from code content."""

    def parse(self, file_path: str, content: str) -> list[str]:
        """Extract function call names from code.

        Args:
            file_path: Path to determine language.
            content: Code content to parse.

        Returns:
            List of function names that are called.
        """
        plugin = get_plugin_for_file(file_path)
        if not plugin:
            return []

        try:
            calls = plugin.parse_calls(content)
            log.debug(
                "call_parser.parsed",
                file=file_path,
                call_count=len(calls),
                sample=calls[:5] if calls else [],
            )
            return calls
        except Exception as e:
            log.warning("call_parser.failed", file=file_path, error=str(e))
            return []


class CalleeResolver:
    """Resolve function calls to indexed definitions.

    This class handles looking up called functions in the vector store,
    prioritizing functions from other files over same-file definitions.
    """

    def __init__(self, store: VectorStoreProtocol) -> None:
        self._store = store

    def resolve(
        self,
        namespace: str,
        calls: list[str],
        current_file: str,
        max_results: int = 5,
    ) -> list[ResolvedCallee]:
        """Resolve function calls to indexed definitions.

        Args:
            namespace: Repository namespace (owner/repo).
            calls: List of function names to resolve.
            current_file: Path to exclude from primary results.
            max_results: Maximum number of callees to return.

        Returns:
            List of resolved callees, prioritizing cross-file definitions.
        """
        if not calls:
            return []

        cross_file_callees: list[ResolvedCallee] = []
        same_file_callees: list[ResolvedCallee] = []

        for name in calls[:max_results]:
            # Try other files first (higher priority)
            callee = self._lookup_in_other_files(namespace, name, current_file)
            if callee:
                cross_file_callees.append(callee)
                continue

            # Fallback to same file
            callee = self._lookup_in_same_file(namespace, name, current_file)
            if callee:
                same_file_callees.append(callee)

        # Prefer cross-file callees, fallback to same-file
        if cross_file_callees:
            return cross_file_callees[:max_results]

        log.debug(
            "callee_resolver.using_same_file",
            file=current_file,
            count=len(same_file_callees),
        )
        return same_file_callees[:2]  # Limit same-file callees

    def _lookup_in_other_files(
        self,
        namespace: str,
        name: str,
        exclude_file: str,
    ) -> ResolvedCallee | None:
        """Look up function in files other than the current one."""
        results = self._store.fetch_by_metadata(
            namespace=namespace,
            filter={"name": name, "file_path": {"$ne": exclude_file}},
            limit=1,
        )

        if not results:
            return None

        metadata = results[0].metadata

        # Validate exact name match
        if metadata.get("name") != name:
            log.debug(
                "callee_resolver.name_mismatch",
                expected=name,
                got=metadata.get("name"),
            )
            return None

        return ResolvedCallee(
            file_path=metadata.get("file_path", ""),
            name=metadata.get("name", ""),
            content=metadata.get("content", ""),
            chunk_type=metadata.get("chunk_type", "function"),
            from_same_file=False,
            start_line=metadata.get("start_line", 0),
            end_line=metadata.get("end_line", 0),
        )

    def _lookup_in_same_file(
        self,
        namespace: str,
        name: str,
        file_path: str,
    ) -> ResolvedCallee | None:
        """Look up function in the same file."""
        results = self._store.fetch_by_metadata(
            namespace=namespace,
            filter={"name": name, "file_path": file_path},
            limit=1,
        )

        if not results:
            return None

        metadata = results[0].metadata

        if metadata.get("name") != name:
            return None

        return ResolvedCallee(
            file_path=metadata.get("file_path", ""),
            name=metadata.get("name", ""),
            content=metadata.get("content", ""),
            chunk_type=metadata.get("chunk_type", "function"),
            from_same_file=True,
            start_line=metadata.get("start_line", 0),
            end_line=metadata.get("end_line", 0),
        )


class CallerFinder:
    """Find functions that call a target function."""

    def __init__(self, store: VectorStoreProtocol) -> None:
        self._store = store

    def find(
        self,
        namespace: str,
        function_name: str,
        exclude_file: str,
        max_results: int = 5,
    ) -> list[RelatedCode]:
        """Find functions that call the target function.

        Args:
            namespace: Repository namespace.
            function_name: Name of function to find callers for.
            exclude_file: File path to exclude (the target's file).
            max_results: Maximum callers to return.

        Returns:
            List of RelatedCode for calling functions.
        """
        results = self._store.fetch_by_metadata(
            namespace=namespace,
            filter={
                "calls": {"$in": [function_name]},
                "file_path": {"$ne": exclude_file},
            },
            limit=max_results,
        )

        callers = []
        for match in results:
            metadata = match.metadata
            calls_list = metadata.get("calls", [])

            # Verify the function name is actually in the calls list
            if function_name not in calls_list:
                log.debug(
                    "caller_finder.mismatch",
                    caller=metadata.get("name"),
                    expected=function_name,
                    actual_calls=calls_list,
                )
                continue

            callers.append(
                RelatedCode(
                    file_path=metadata.get("file_path", ""),
                    name=metadata.get("name", ""),
                    content=metadata.get("content", ""),
                    chunk_type=metadata.get("chunk_type", "function"),
                    relevance_score=1.0,
                    relationship="caller",
                    start_line=metadata.get("start_line", 0),
                    end_line=metadata.get("end_line", 0),
                )
            )

        return callers


class TestFinder:
    """Find test files/functions for source code."""

    def __init__(self, store: VectorStoreProtocol) -> None:
        self._store = store

    def find(
        self,
        namespace: str,
        file_path: str,
        function_name: str,
        plugin: LanguagePluginProtocol,
    ) -> RelatedCode | None:
        """Find test matching the source function.

        Args:
            namespace: Repository namespace.
            file_path: Source file path.
            function_name: Source function name.
            plugin: Language plugin for test patterns.

        Returns:
            RelatedCode for matching test, or None.
        """
        test_paths = plugin.get_test_patterns(file_path)

        for test_path in test_paths:
            results = self._store.fetch_by_metadata(
                namespace=namespace,
                filter={"file_path": test_path},
                limit=10,
            )

            if not results:
                continue

            # Look for test function matching source function name
            for match in results:
                metadata = match.metadata
                name = metadata.get("name", "")

                # Check if function name appears in test name
                if function_name.lower() in name.lower():
                    return RelatedCode(
                        file_path=metadata.get("file_path", ""),
                        name=name,
                        content=metadata.get("content", ""),
                        chunk_type=metadata.get("chunk_type", "function"),
                        relevance_score=1.0,
                        relationship="test",
                        start_line=metadata.get("start_line", 0),
                        end_line=metadata.get("end_line", 0),
                    )

        return None
