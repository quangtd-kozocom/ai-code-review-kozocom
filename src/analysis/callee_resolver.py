"""Resolve callee source code for dependency verification."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from .ast_analyzer import ASTAnalyzer, get_ast_analyzer
from .call_graph import CallGraph

if TYPE_CHECKING:
    from ..app.services.github import GitHubService

log = structlog.get_logger()


@dataclass(slots=True)
class CalleeInfo:
    """Information about a called function."""

    name: str
    file_path: str | None = None
    source_code: str | None = None
    signature: str | None = None
    has_validation: bool = False
    returns_optional: bool = False


class CalleeResolver:
    """Resolves callee source code from the repository."""

    def __init__(
        self,
        analyzer: ASTAnalyzer | None = None,
    ):
        self._analyzer = analyzer or get_ast_analyzer()
        self._cache: dict[str, CalleeInfo] = {}

    async def resolve_callees(
        self,
        callee_names: list[str],
        call_graph: CallGraph,
        file_contents: dict[str, str],
        github_service: "GitHubService | None" = None,
        owner: str | None = None,
        repo: str | None = None,
        ref: str | None = None,
    ) -> list[CalleeInfo]:
        """Resolve source code for callees.

        Args:
            callee_names: List of function names called by the target function.
            call_graph: Current call graph with file mappings.
            file_contents: Pre-fetched file contents from PR.
            github_service: Optional GitHub service for fetching external files.
            owner: Repository owner (required if github_service provided).
            repo: Repository name (required if github_service provided).
            ref: Git ref to fetch from (required if github_service provided).

        Returns:
            List of CalleeInfo with source code.
        """
        log.debug(
            "callee_resolver.resolve_callees.started",
            callee_count=len(callee_names),
            callee_names=callee_names[:10],  # Log first 10
            call_graph_functions=len(call_graph.relations),
            call_graph_keys=list(call_graph.relations.keys())[:10],
            file_contents_count=len(file_contents),
            file_paths=list(file_contents.keys()),
            cache_size=len(self._cache),
        )
        
        resolved: list[CalleeInfo] = []
        cache_hits = 0
        resolved_with_code = 0
        resolved_without_code = 0

        for name in callee_names:
            if name in self._cache:
                resolved.append(self._cache[name])
                cache_hits += 1
                continue

            info = await self._resolve_single_callee(
                name, call_graph, file_contents, github_service, owner, repo, ref
            )
            if info:
                self._cache[name] = info
                resolved.append(info)
                if info.source_code:
                    resolved_with_code += 1
                else:
                    resolved_without_code += 1

        log.info(
            "callee_resolver.resolve_callees.complete",
            total=len(callee_names),
            cache_hits=cache_hits,
            resolved_with_code=resolved_with_code,
            resolved_without_code=resolved_without_code,
        )
        
        return resolved

    async def _resolve_single_callee(
        self,
        name: str,
        call_graph: CallGraph,
        file_contents: dict[str, str],
        github_service: "GitHubService | None" = None,
        owner: str | None = None,
        repo: str | None = None,
        ref: str | None = None,
    ) -> CalleeInfo | None:
        """Resolve a single callee."""
        log.debug(
            "callee_resolver.resolving_single",
            callee=name,
            in_call_graph=name in call_graph.relations,
        )
        
        # Check if callee is in our call graph (meaning it's in changed files or analyzed files)
        if relation := call_graph.relations.get(name):
            file_path = relation.file_path
            content = file_contents.get(file_path)
            
            log.debug(
                "callee_resolver.found_in_call_graph",
                callee=name,
                file_path=file_path,
                has_content=content is not None,
            )

            if content:
                info = self._extract_callee_info(name, file_path, content)
                if info.source_code:
                    log.debug(
                        "callee_resolver.resolved_from_call_graph",
                        callee=name,
                        file_path=file_path,
                        has_signature=info.signature is not None,
                    )
                return info

        # Try to find in other known files from file_contents
        log.debug(
            "callee_resolver.searching_all_files",
            callee=name,
            file_count=len(file_contents),
        )
        
        for file_path, content in file_contents.items():
            info = self._extract_callee_info(name, file_path, content)
            if info.source_code:  # Found it
                log.debug(
                    "callee_resolver.resolved_from_scan",
                    callee=name,
                    file_path=file_path,
                )
                return info

        # Try to fetch from GitHub if service is available
        if github_service and owner and repo and ref:
            log.info(
                "callee_resolver.trying_github_search",
                callee=name,
                owner=owner,
                repo=repo,
            )
            
            try:
                # Search for the function in the repository
                search_results = await github_service.search_code(
                    owner=owner,
                    repo=repo,
                    query=f"function {name} OR def {name}",
                )
                
                # Try to fetch and analyze the first few results
                for result in search_results[:3]:  # Limit to first 3 results
                    try:
                        file_path = result.get("path")
                        if not file_path:
                            continue
                        
                        log.debug(
                            "callee_resolver.fetching_from_github",
                            callee=name,
                            file_path=file_path,
                        )
                        
                        # Fetch file content
                        content = await github_service.get_file_content(
                            owner=owner,
                            repo=repo,
                            path=file_path,
                            ref=ref,
                        )
                        
                        if content:
                            info = self._extract_callee_info(name, file_path, content)
                            if info.source_code:
                                log.info(
                                    "callee_resolver.resolved_from_github",
                                    callee=name,
                                    file_path=file_path,
                                )
                                return info
                    except Exception as e:
                        log.warning(
                            "callee_resolver.github_fetch_failed",
                            callee=name,
                            file_path=file_path,
                            error=str(e),
                        )
                        continue
            except Exception as e:
                log.warning(
                    "callee_resolver.github_search_failed",
                    callee=name,
                    error=str(e),
                )
        
        # Could not find the callee in available files or GitHub
        log.warning(
            "callee_resolver.not_found",
            callee=name,
            searched_files=len(file_contents),
            file_paths=list(file_contents.keys()),
            tried_github=github_service is not None,
        )
        return CalleeInfo(name=name, file_path=None, source_code=None)

    def _extract_callee_info(
        self,
        name: str,
        file_path: str,
        content: str,
    ) -> CalleeInfo:
        """Extract callee info from file content."""
        try:
            functions = self._analyzer.extract_functions(file_path, content)
            log.debug(
                "callee_resolver.extracted_functions",
                file=file_path,
                function_count=len(functions),
                function_names=[f.name for f in functions],
                looking_for=name,
            )
        except Exception as e:
            log.warning(
                "callee_resolver.extraction_failed",
                file=file_path,
                error=str(e),
            )
            return CalleeInfo(name=name, file_path=file_path, source_code=None)

        for func in functions:
            if func.name == name:
                source_code = func.content

                log.debug(
                    "callee_resolver.function_matched",
                    name=name,
                    file=file_path,
                    signature=func.signature,
                    content_length=len(source_code),
                )

                return CalleeInfo(
                    name=name,
                    file_path=file_path,
                    source_code=source_code,
                    signature=func.signature,
                    has_validation=self._detect_validation(func.content),
                    returns_optional=self._detect_optional_return(
                        func.content, func.return_type
                    ),
                )

        # Function not found in this file
        log.debug(
            "callee_resolver.function_not_in_file",
            name=name,
            file=file_path,
            available_functions=[f.name for f in functions],
        )
        return CalleeInfo(name=name, file_path=file_path, source_code=None)

    def _detect_validation(self, content: str) -> bool:
        """Detect if function has input validation."""
        validation_patterns = [
            r"if\s+not\s+",
            r"if\s+\w+\s+is\s+None",
            r"if\s+\w+\s+==\s+None",
            r"raise\s+ValueError",
            r"raise\s+TypeError",
            r"assert\s+",
            r"validate\(",
            r"is_valid",
            r"check_",
            r"verify_",
        ]

        for pattern in validation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _detect_optional_return(
        self, content: str, return_type: str | None
    ) -> bool:
        """Detect if function can return None/Optional."""
        if return_type:
            if "None" in return_type or "Optional" in return_type:
                return True

        return "return None" in content
