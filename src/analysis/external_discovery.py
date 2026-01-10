"""External file discovery for impact analysis.

Finds files outside the PR that depend on changed code using
GitHub Code Search API + AST verification.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

import structlog

from ..app.services.github import GitHubService
from .ast_analyzer import get_ast_analyzer
from .php_patterns import PHPPatternDetector

log = structlog.get_logger()

# Smart priority settings
MAX_SEARCHES_PER_ITERATION = 10
SEARCH_DELAY_SECONDS = 1.0  # Rate limit protection


@dataclass(slots=True)
class ExternalFile:
    """An external file that depends on changed code."""
    
    path: str
    content: str
    usage_type: Literal["import", "di", "facade", "method_call", "model_relation", "unknown"]
    affected_lines: list[int] = field(default_factory=list)
    will_break: bool = False
    break_reason: str | None = None
    references: list[str] = field(default_factory=list)  # What it references


class ExternalDiscoveryService:
    """Discover external files that depend on changed code.
    
    Uses GitHub Code Search to find candidates, then AST analysis
    to verify actual usage and determine impact.
    """
    
    def __init__(self, github: GitHubService):
        self.github = github
        self.analyzer = get_ast_analyzer()
        self.php_detector = PHPPatternDetector()
    
    def _prioritize_targets(
        self,
        changed_classes: list[str],
        changed_methods: list[str],
    ) -> list[str]:
        """Prioritize search targets for smart discovery.
        
        Priority order:
        1. Changed classes (most likely to have external usage)
        2. Changed methods (if not too many)
        
        Args:
            changed_classes: List of class names that changed
            changed_methods: List of method names that changed
            
        Returns:
            Prioritized list of search targets
        """
        targets = []
        
        # Priority 1: All changed classes
        targets.extend(changed_classes)
        
        # Priority 2: Top methods (avoid searching for every single method)
        # Only include methods if we have < 5 classes
        if len(changed_classes) < 5:
            targets.extend(changed_methods[:5])
        
        return targets
    
    async def discover(
        self,
        owner: str,
        repo: str,
        ref: str,
        changed_classes: list[str],
        changed_methods: list[str],
        exclude_paths: list[str] | None = None,
    ) -> list[ExternalFile]:
        """Find external files using GitHub Code Search + AST verification.
        
        Uses smart priority search with rate limiting:
        - Limits to MAX_SEARCHES_PER_ITERATION searches
        - Adds delay between requests to avoid rate limits
        - Stops gracefully on rate limit errors
        
        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git ref (branch/commit)
            changed_classes: List of class names that changed
            changed_methods: List of method names that changed
            exclude_paths: Paths to exclude (e.g., files already in PR)
            
        Returns:
            List of verified external files with usage information
        """
        exclude_paths = exclude_paths or []
        
        # Smart priority: limit search targets
        search_targets = self._prioritize_targets(
            changed_classes, changed_methods
        )[:MAX_SEARCHES_PER_ITERATION]
        
        log.info(
            "external_discovery.started",
            owner=owner,
            repo=repo,
            total_targets=len(search_targets),
            targets=search_targets[:10],
        )
        
        # Collect all candidates from search with rate limiting
        candidates: dict[str, dict] = {}  # path -> search result
        rate_limit_hit = False
        
        for i, target in enumerate(search_targets, 1):
            # Rate limit protection: delay between requests
            if i > 1:
                await asyncio.sleep(SEARCH_DELAY_SECONDS)
            
            try:
                query = f"{target} repo:{owner}/{repo}"
                results = await self.github.search_code(query, per_page=30)
                
                for item in results:
                    path = item.get("path", "")
                    if path and path not in exclude_paths:
                        candidates[path] = item
                
                log.debug(
                    "external_discovery.search_complete",
                    target=target,
                    results=len(results),
                    progress=f"{i}/{len(search_targets)}",
                )
            
            except Exception as e:
                # Likely rate limit - log and stop searching
                log.warning(
                    "external_discovery.search_failed",
                    target=target,
                    error=str(e),
                    progress=f"{i}/{len(search_targets)}",
                )
                rate_limit_hit = True
                break
        
        if rate_limit_hit:
            log.warning(
                "external_discovery.rate_limit_reached",
                searches_completed=i - 1,
                total_targets=len(search_targets),
                candidates_found=len(candidates),
            )
        
        log.info(
            "external_discovery.candidates_found",
            total_candidates=len(candidates),
            paths=list(candidates.keys())[:10],
        )
        
        # Fetch and verify each candidate
        verified: list[ExternalFile] = []
        
        for path, item in candidates.items():
            # Skip test files, vendor, node_modules
            if self._should_skip_path(path):
                log.debug("external_discovery.skipped_path", path=path)
                continue
            
            # Fetch file content
            content = await self.github.get_file_raw(owner, repo, path, ref)
            if not content:
                log.debug("external_discovery.no_content", path=path)
                continue
            
            # Verify usage with AST
            usage_info = self._verify_usage(
                content, path, changed_classes, changed_methods
            )
            
            if usage_info:
                verified.append(ExternalFile(
                    path=path,
                    content=content,
                    usage_type=usage_info["type"],
                    affected_lines=usage_info["lines"],
                    references=usage_info["references"],
                ))
        
        log.info(
            "external_discovery.complete",
            verified_count=len(verified),
            verified_paths=[f.path for f in verified][:10],
        )
        
        return verified
    
    def _should_skip_path(self, path: str) -> bool:
        """Check if path should be skipped."""
        skip_patterns = [
            "/test/", "/tests/", "_test.", "test_",
            "/vendor/", "/node_modules/",
            ".min.", ".bundle.",
            "/migrations/", "/database/migrations/",
        ]
        
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in skip_patterns)
    
    def _verify_usage(
        self,
        content: str,
        file_path: str,
        changed_classes: list[str],
        changed_methods: list[str],
    ) -> dict | None:
        """Verify if file actually uses the changed code.
        
        Returns:
            Dict with usage info if verified, None otherwise
        """
        # Simple text search first for performance
        content_lower = content.lower()
        found_references = []
        
        for class_name in changed_classes:
            if class_name.lower() in content_lower:
                found_references.append(class_name)
        
        for method_name in changed_methods:
            if method_name.lower() in content_lower:
                found_references.append(method_name)
        
        if not found_references:
            return None
        
        # Try AST analysis for precise location
        affected_lines = []
        usage_type = "unknown"
        
        try:
            # For PHP files, detect usage patterns
            if file_path.endswith(".php"):
                usage_type = self._detect_php_usage_type(content, changed_classes)
                affected_lines = self._find_usage_lines_php(
                    content, changed_classes, changed_methods
                )
            else:
                # For other languages, use tree-sitter if available
                functions = self.analyzer.extract_functions(file_path, content)
                for func in functions:
                    for ref in found_references:
                        if ref in func.content:
                            affected_lines.append(func.start_line)
        
        except Exception as e:
            log.debug(
                "external_discovery.ast_failed",
                path=file_path,
                error=str(e),
            )
        
        return {
            "type": usage_type,
            "lines": affected_lines or [1],  # Default to line 1 if can't determine
            "references": found_references,
        }
    
    def _detect_php_usage_type(
        self,
        content: str,
        changed_classes: list[str],
    ) -> str:
        """Detect how PHP code uses the changed classes using Laravel patterns."""
        for class_name in changed_classes:
            patterns = self.php_detector.detect_all_patterns(content, class_name)
            
            if patterns:
                # Return the first detected pattern type
                # Priority: DI > Facade > app_helper > eloquent > route > import
                priority_order = ["di", "facade", "app_helper", "eloquent_relation", "route", "import"]
                
                for pattern_type in priority_order:
                    if any(p.pattern_type == pattern_type for p in patterns):
                        return pattern_type
        
        return "unknown"
    
    def _find_usage_lines_php(
        self,
        content: str,
        changed_classes: list[str],
        changed_methods: list[str],
    ) -> list[int]:
        """Find line numbers where changed code is used in PHP using Laravel patterns."""
        affected_lines = []
        
        # Use Laravel pattern detector for precise line detection
        for class_name in changed_classes:
            patterns = self.php_detector.detect_all_patterns(content, class_name)
            affected_lines.extend(p.line_number for p in patterns)
        
        # Also check for method calls with simple search
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            
            # Check for method calls
            for method_name in changed_methods:
                if method_name.lower() in line_lower:
                    affected_lines.append(i)
                    break
        
        return list(set(affected_lines))  # Deduplicate
