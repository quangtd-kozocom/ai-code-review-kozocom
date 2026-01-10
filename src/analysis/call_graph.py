"""Call graph builder for code analysis.

Builds call relationships between functions using AST analysis,
providing accurate caller/callee information without vector database.
"""

from dataclasses import dataclass, field
from typing import Self

import structlog

from .ast_analyzer import ASTAnalyzer, CallSite, FunctionDefinition, get_ast_analyzer

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class FunctionCall:
    """Represents a function call relationship."""
    
    caller: str
    callee: str
    caller_file: str
    callee_file: str | None = None
    line: int = 0
    context: str = ""


@dataclass(slots=True)
class CallRelation:
    """Call relationships for a function."""
    
    function_name: str
    file_path: str
    callers: list[FunctionCall] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    
    @property
    def caller_count(self) -> int:
        return len(self.callers)
    
    @property
    def callee_count(self) -> int:
        return len(self.callees)


@dataclass(slots=True)
class CallGraph:
    """Complete call graph for a set of files."""
    
    relations: dict[str, CallRelation] = field(default_factory=dict)
    file_functions: dict[str, list[str]] = field(default_factory=dict)
    
    def get_callers(self, function_name: str) -> list[FunctionCall]:
        """Get all callers of a function."""
        if relation := self.relations.get(function_name):
            return relation.callers
        return []
    
    def get_callees(self, function_name: str) -> list[str]:
        """Get all functions called by a function."""
        if relation := self.relations.get(function_name):
            return relation.callees
        return []
    
    def get_transitive_callers(
        self,
        function_name: str,
        max_depth: int = 2,
    ) -> list[FunctionCall]:
        """Get callers up to N levels deep."""
        seen: set[str] = set()
        result: list[FunctionCall] = []
        
        def collect(name: str, depth: int) -> None:
            if depth > max_depth or name in seen:
                return
            seen.add(name)
            
            for caller in self.get_callers(name):
                result.append(caller)
                collect(caller.caller, depth + 1)
        
        collect(function_name, 0)
        return result
    
    def merge(self, other: Self) -> Self:
        """Merge another call graph into this one."""
        for name, relation in other.relations.items():
            if name in self.relations:
                existing = self.relations[name]
                existing.callers.extend(relation.callers)
                existing.callees.extend(
                    c for c in relation.callees if c not in existing.callees
                )
            else:
                self.relations[name] = relation
        
        for file_path, funcs in other.file_functions.items():
            if file_path in self.file_functions:
                existing = self.file_functions[file_path]
                self.file_functions[file_path] = list(set(existing + funcs))
            else:
                self.file_functions[file_path] = funcs
        
        return self


class CallGraphBuilder:
    """Build call graph from source files using AST analysis.
    
    Creates accurate call relationships by analyzing source code directly,
    without relying on vector database or semantic similarity.
    """
    
    def __init__(
        self,
        analyzer: ASTAnalyzer | None = None,
        github_client=None,
    ) -> None:
        """Initialize builder.
        
        Args:
            analyzer: AST analyzer instance.
            github_client: GitHub client for fetching files.
        """
        self._analyzer = analyzer or get_ast_analyzer()
        self._github = github_client
    
    async def build_for_changes(
        self,
        owner: str,
        repo: str,
        changed_files: list[dict],
        base_ref: str,
        head_ref: str,
    ) -> CallGraph:
        """Build call graph for changed functions.
        
        Args:
            owner: Repository owner.
            repo: Repository name.
            changed_files: List of changed file info dicts.
            base_ref: Base branch ref (target).
            head_ref: Head branch ref (source).
            
        Returns:
            CallGraph with relationships for changed functions.
        """
        log.info(
            "call_graph.building",
            owner=owner,
            repo=repo,
            files_count=len(changed_files),
        )
        
        graph = CallGraph()
        
        # First pass: Extract functions from changed files
        changed_functions: list[FunctionDefinition] = []
        for file_info in changed_files:
            file_path = file_info["file_path"]
            content = file_info.get("head_content") or ""
            
            if not content:
                continue
            
            funcs = self._analyzer.extract_functions(file_path, content)
            for func in funcs:
                changed_functions.append(func)
                
                # Initialize relation
                graph.relations[func.name] = CallRelation(
                    function_name=func.name,
                    file_path=file_path,
                    callees=func.calls,
                )
            
            graph.file_functions[file_path] = [f.name for f in funcs]
        
        # Second pass: Find callers in repository files
        if self._github and changed_functions:
            await self._find_callers(
                owner, repo, head_ref, changed_functions, graph
            )
        
        log.info(
            "call_graph.complete",
            functions=len(graph.relations),
            total_callers=sum(r.caller_count for r in graph.relations.values()),
        )
        
        return graph
    
    async def _find_callers(
        self,
        owner: str,
        repo: str,
        ref: str,
        functions: list[FunctionDefinition],
        graph: CallGraph,
    ) -> None:
        """Find callers for functions across the repository."""
        # Get list of potential caller files (same language)
        function_names = {f.name for f in functions}
        
        # For each function, search for callers in other files
        # This is a simplified approach - in production you'd want
        # to scope this better using import analysis
        for func in functions:
            callers = await self._find_function_callers(
                owner, repo, ref, func, graph
            )
            
            if func.name in graph.relations:
                graph.relations[func.name].callers = callers
    
    async def _find_function_callers(
        self,
        owner: str,
        repo: str,
        ref: str,
        func: FunctionDefinition,
        graph: CallGraph,
    ) -> list[FunctionCall]:
        """Find all callers of a specific function."""
        callers: list[FunctionCall] = []
        
        # Search in files we already have content for
        for file_path, func_names in graph.file_functions.items():
            if file_path == func.file_path:
                continue  # Skip self
            
            # Get content from changed files
            content = await self._get_file_content(owner, repo, file_path, ref)
            if not content:
                continue
            
            call_sites = self._analyzer.find_call_sites(
                file_path, content, func.name
            )
            
            for site in call_sites:
                callers.append(FunctionCall(
                    caller=site.caller_function or "<module>",
                    callee=func.name,
                    caller_file=file_path,
                    callee_file=func.file_path,
                    line=site.line,
                    context=site.context_code,
                ))
        
        return callers
    
    async def _get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> str | None:
        """Fetch file content from GitHub."""
        if not self._github:
            return None
        
        try:
            return await self._github.get_file_raw(owner, repo, path, ref)
        except Exception as e:
            log.debug("call_graph.fetch_failed", path=path, error=str(e))
            return None
    
    def build_from_content(
        self,
        files: dict[str, str],
    ) -> CallGraph:
        """Build call graph from in-memory file contents.
        
        Args:
            files: Dict mapping file paths to content.
            
        Returns:
            CallGraph with relationships.
        """
        graph = CallGraph()
        all_functions: dict[str, FunctionDefinition] = {}
        
        # First pass: Extract all functions
        for file_path, content in files.items():
            funcs = self._analyzer.extract_functions(file_path, content)
            
            for func in funcs:
                all_functions[func.name] = func
                graph.relations[func.name] = CallRelation(
                    function_name=func.name,
                    file_path=file_path,
                    callees=func.calls,
                )
            
            graph.file_functions[file_path] = [f.name for f in funcs]
        
        # Second pass: Find callers
        for file_path, content in files.items():
            for func_name, func in all_functions.items():
                if func.file_path == file_path:
                    continue
                
                call_sites = self._analyzer.find_call_sites(
                    file_path, content, func_name
                )
                
                for site in call_sites:
                    if func_name in graph.relations:
                        graph.relations[func_name].callers.append(FunctionCall(
                            caller=site.caller_function or "<module>",
                            callee=func_name,
                            caller_file=file_path,
                            callee_file=func.file_path,
                            line=site.line,
                            context=site.context_code,
                        ))
        
        return graph
