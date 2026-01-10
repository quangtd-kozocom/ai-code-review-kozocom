"""Context builder for PR review.

Assembles precise, targeted context for LLM review by combining
diff information, call graphs, and impact analysis.
"""

from dataclasses import dataclass, field

import structlog

from .ast_analyzer import FunctionDefinition
from .call_graph import CallGraph, FunctionCall
from .callee_resolver import CalleeInfo, CalleeResolver
from .diff_extractor import ChangeType, FileDiff
from .impact_analyzer import FunctionImpact, ImpactLevel, ImpactReport

log = structlog.get_logger()


@dataclass(slots=True)
class FunctionContext:
    """Context for reviewing a single function."""

    name: str
    file_path: str
    change_type: ChangeType
    impact_level: ImpactLevel

    # Code content
    old_code: str | None = None
    new_code: str | None = None
    diff: str | None = None

    # Relationships
    callers: list[FunctionCall] = field(default_factory=list)
    callees: list[CalleeInfo] = field(default_factory=list)

    # Metadata
    signature_changed: bool = False
    has_tests: bool = False
    review_questions: list[str] = field(default_factory=list)
    
    def format_for_prompt(self) -> str:
        """Format context for LLM prompt."""
        lines = [
            f"## Function: `{self.name}`",
            f"**File**: {self.file_path}",
            f"**Change Type**: {self.change_type.value.upper()}",
            f"**Impact Level**: {self.impact_level.value.upper()}",
            "",
        ]
        
        # Show code changes
        if self.old_code and self.change_type != ChangeType.ADDED:
            lines.extend([
                "### Before:",
                "```python",
                self.old_code,
                "```",
                "",
            ])
        
        if self.new_code and self.change_type != ChangeType.DELETED:
            lines.extend([
                "### After:",
                "```python",
                self.new_code,
                "```",
                "",
            ])
        
        if self.diff:
            lines.extend([
                "### Diff:",
                "```diff",
                self.diff,
                "```",
                "",
            ])
        
        # Show callers
        if self.callers:
            lines.extend([
                f"### Callers ({len(self.callers)}):",
                "",
            ])
            for caller in self.callers[:5]:  # Limit to 5
                lines.extend([
                    f"- `{caller.caller}` in {caller.caller_file}:{caller.line}",
                    "```python",
                    caller.context,
                    "```",
                    "",
                ])
        
        # Show callees
        if self.callees:
            lines.extend([
                f"### Calls ({len(self.callees)}):",
                ", ".join(f"`{c.name}`" for c in self.callees[:10]),
                "",
            ])
        
        # Show review questions
        if self.review_questions:
            lines.extend([
                "### Review Questions:",
                "",
            ])
            for i, q in enumerate(self.review_questions, 1):
                lines.append(f"{i}. {q}")
            lines.append("")
        
        # Metadata
        if self.signature_changed:
            lines.append("⚠️ **Signature Changed**: This may break existing callers.")
        
        if not self.has_tests:
            lines.append("⚠️ **No Tests**: Consider adding test coverage.")
        
        return "\n".join(lines)


@dataclass(slots=True)
class ReviewContext:
    """Complete context for PR review."""
    
    pr_number: int
    owner: str
    repo: str
    base_branch: str
    head_branch: str
    
    # Function contexts
    functions: list[FunctionContext] = field(default_factory=list)
    
    # File-level info
    new_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    
    # Summary info
    breaking_changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def format_summary(self) -> str:
        """Format summary for prompt."""
        lines = [
            f"# PR #{self.pr_number} Review Context",
            f"**Repository**: {self.owner}/{self.repo}",
            f"**Branches**: {self.head_branch} → {self.base_branch}",
            "",
        ]
        
        # Breaking changes
        if self.breaking_changes:
            lines.extend([
                "## ⚠️ Breaking Changes",
                "",
            ])
            for change in self.breaking_changes:
                lines.append(f"- {change}")
            lines.append("")
        
        # Warnings
        if self.warnings:
            lines.extend([
                "## Warnings",
                "",
            ])
            for warning in self.warnings:
                lines.append(f"- {warning}")
            lines.append("")
        
        # Stats
        lines.extend([
            "## Summary",
            f"- Functions changed: {len(self.functions)}",
            f"- New files: {len(self.new_files)}",
            f"- Deleted files: {len(self.deleted_files)}",
            "",
        ])
        
        return "\n".join(lines)
    
    def get_functions_for_review(self) -> list[FunctionContext]:
        """Get functions that need review, sorted by impact."""
        return sorted(
            [f for f in self.functions if f.impact_level != ImpactLevel.TRIVIAL],
            key=lambda f: list(ImpactLevel).index(f.impact_level),
        )


class ContextBuilder:
    """Assemble review context from analysis results.

    Combines diff extraction, call graph, and impact analysis
    into targeted context for LLM review.
    """

    def __init__(self, github_service=None):
        """Initialize context builder.
        
        Args:
            github_service: Optional GitHub service for fetching external callees.
        """
        self.callee_resolver = CalleeResolver()
        self.github_service = github_service
        self._owner: str | None = None
        self._repo: str | None = None
        self._ref: str | None = None

    async def build(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        base_branch: str,
        head_branch: str,
        diffs: list[FileDiff],
        call_graph: CallGraph,
        impact_report: ImpactReport,
        function_changes: dict[str, dict],
        file_contents: dict[str, str],
    ) -> ReviewContext:
        """Build review context from analysis results.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.
            base_branch: Base branch name.
            head_branch: Head branch name.
            diffs: File diffs from diff extractor.
            call_graph: Call graph from call graph builder.
            impact_report: Impact report from impact analyzer.
            function_changes: Function changes from AST comparison.
            file_contents: Dictionary of file paths to their content.

        Returns:
            ReviewContext ready for LLM review.
        """
        log.info(
            "context_builder.building",
            pr=pr_number,
            functions=len(function_changes),
        )
        
        # Store repo info for callee resolution
        self._owner = owner
        self._repo = repo
        self._ref = head_branch  # Use head branch for fetching callees
        
        context = ReviewContext(
            pr_number=pr_number,
            owner=owner,
            repo=repo,
            base_branch=base_branch,
            head_branch=head_branch,
        )
        
        # Build function contexts
        for impact in impact_report.functions:
            func_ctx = await self._build_function_context(
                impact, diffs, call_graph, function_changes, file_contents
            )
            context.functions.append(func_ctx)
        
        # Categorize files
        for diff in diffs:
            match diff.status:
                case ChangeType.ADDED:
                    context.new_files.append(diff.file_path)
                case ChangeType.DELETED:
                    context.deleted_files.append(diff.file_path)
        
        # Extract warnings
        for warning in impact_report.breaking_changes:
            context.breaking_changes.append(warning.message)
        
        for warning in impact_report.warnings:
            context.warnings.append(warning.message)
        
        log.info(
            "context_builder.complete",
            functions=len(context.functions),
            breaking_changes=len(context.breaking_changes),
        )
        
        return context
    
    async def _build_function_context(
        self,
        impact: FunctionImpact,
        diffs: list[FileDiff],
        call_graph: CallGraph,
        function_changes: dict[str, dict],
        file_contents: dict[str, str],
    ) -> FunctionContext:
        """Build context for a single function."""
        change_info = function_changes.get(impact.name, {})

        # Get code content
        old_code = None
        new_code = None
        diff_content = None

        if old_func := change_info.get("old"):
            old_code = old_func.content

        if new_func := change_info.get("new"):
            new_code = new_func.content

        # Find diff for this function's file
        old_func = change_info.get("old")
        new_func = change_info.get("new")
        
        for diff in diffs:
            if diff.file_path == impact.file_path:
                diff_content = self._extract_function_diff(
                    diff, impact.name, old_func, new_func
                )
                break

        # Get relationships
        callers = call_graph.get_callers(impact.name)
        callee_names = call_graph.get_callees(impact.name)

        # Resolve callee source code (with optional GitHub fallback)
        callees = await self.callee_resolver.resolve_callees(
            callee_names,
            call_graph,
            file_contents,
            github_service=self.github_service,
            owner=self._owner,
            repo=self._repo,
            ref=self._ref,
        )

        # Generate review questions
        questions = self._generate_review_questions(impact, change_info, callers)

        return FunctionContext(
            name=impact.name,
            file_path=impact.file_path,
            change_type=impact.change_type,
            impact_level=impact.impact_level,
            old_code=old_code,
            new_code=new_code,
            diff=diff_content,
            callers=callers,
            callees=callees,
            signature_changed=impact.signature_changed,
            has_tests=impact.has_tests,
            review_questions=questions,
        )
    
    def _extract_function_diff(
        self,
        file_diff: FileDiff,
        function_name: str,
        old_func: "FunctionDefinition | None",
        new_func: "FunctionDefinition | None",
    ) -> str | None:
        """Extract diff lines relevant to a function.
        
        Filters the full file patch to only include hunks that overlap
        with the function's line range.
        
        Args:
            file_diff: The file diff containing all hunks.
            function_name: Name of the function.
            old_func: Old function definition with line numbers.
            new_func: New function definition with line numbers.
        """
        if not file_diff.patch:
            return None
        
        # If we don't have line information, return full patch
        if not file_diff.hunks:
            return file_diff.patch
        
        # Get function line ranges from FunctionDefinition objects
        old_start = old_func.start_line if old_func else None
        old_end = old_func.end_line if old_func else None
        new_start = new_func.start_line if new_func else None
        new_end = new_func.end_line if new_func else None
        
        # If we can't determine ranges, return full patch
        if (old_start is None and new_start is None):
            return file_diff.patch
        
        # Filter hunks that overlap with function ranges
        relevant_hunks = []
        for hunk in file_diff.hunks:
            # Check if hunk overlaps with old or new function range
            old_overlaps = (
                old_start is not None and
                self._ranges_overlap(
                    hunk.old_start, hunk.old_start + hunk.old_lines,
                    old_start, old_end
                )
            )
            new_overlaps = (
                new_start is not None and
                self._ranges_overlap(
                    hunk.new_start, hunk.new_start + hunk.new_lines,
                    new_start, new_end
                )
            )
            
            if old_overlaps or new_overlaps:
                relevant_hunks.append(hunk)
        
        # If no relevant hunks found, return None (function might not have changed)
        if not relevant_hunks:
            return None
        
        # Reconstruct diff from relevant hunks
        diff_lines = []
        for hunk in relevant_hunks:
            # Add hunk header
            diff_lines.append(
                f"@@ -{hunk.old_start},{hunk.old_lines} "
                f"+{hunk.new_start},{hunk.new_lines} @@"
            )
            # Add hunk content
            diff_lines.extend(hunk.lines)
        
        return "\n".join(diff_lines)
    
    def _ranges_overlap(
        self,
        start1: int,
        end1: int,
        start2: int | None,
        end2: int | None,
    ) -> bool:
        """Check if two line ranges overlap."""
        if start2 is None or end2 is None:
            return False
        return not (end1 < start2 or end2 < start1)
    
    def _generate_review_questions(
        self,
        impact: FunctionImpact,
        change_info: dict,
        callers: list[FunctionCall],
    ) -> list[str]:
        """Generate targeted review questions based on change type."""
        questions: list[str] = []
        
        old_func: FunctionDefinition | None = change_info.get("old")
        new_func: FunctionDefinition | None = change_info.get("new")
        
        # Signature change questions
        if impact.signature_changed and callers:
            questions.append(
                f"Is the signature change backward compatible with the "
                f"{len(callers)} existing callers?"
            )
        
        # New parameter questions
        if old_func and new_func:
            old_params = {p.name for p in old_func.parameters}
            new_params = {p.name for p in new_func.parameters}
            
            for param in new_params - old_params:
                param_obj = next(
                    (p for p in new_func.parameters if p.name == param), None
                )
                if param_obj:
                    if param_obj.default_value is None:
                        questions.append(
                            f"New required parameter `{param}` - will all callers be updated?"
                        )
                    else:
                        questions.append(
                            f"Is the default value for `{param}` appropriate?"
                        )
        
        # Type questions
        if new_func:
            untyped_params = [
                p.name for p in new_func.parameters
                if not p.type_hint and not p.is_variadic and not p.is_keyword
            ]
            if untyped_params:
                questions.append(
                    f"Consider adding type hints for: {', '.join(untyped_params)}"
                )
        
        # Security questions
        if new_func and self._has_security_patterns(new_func.content):
            questions.append("Are there any security concerns with this implementation?")
        
        # Test coverage questions
        if not impact.has_tests:
            match impact.impact_level:
                case ImpactLevel.CRITICAL | ImpactLevel.HIGH:
                    questions.append("This high-impact function should have tests. What test cases are needed?")
                case ImpactLevel.MEDIUM:
                    questions.append("Consider adding tests for this function.")
        
        # Error handling questions
        if new_func and "try" not in new_func.content and any(
            call in new_func.calls for call in ["open", "read", "write", "request", "query"]
        ):
            questions.append("Should this function have error handling for I/O operations?")
        
        return questions
    
    @staticmethod
    def _has_security_patterns(content: str) -> bool:
        """Check for security-sensitive patterns in code."""
        patterns = [
            "password", "secret", "token", "api_key", "apikey",
            "sql", "query", "execute", "eval", "exec",
            "input(", "raw_input",
        ]
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in patterns)
