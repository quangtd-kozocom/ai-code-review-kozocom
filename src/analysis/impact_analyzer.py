"""Impact analyzer for code changes.

Determines the impact of code changes by analyzing call graphs,
test coverage, and breaking changes.
"""

from dataclasses import dataclass, field
from enum import StrEnum, auto

import structlog

from .ast_analyzer import FunctionDefinition, get_ast_analyzer
from .call_graph import CallGraph, FunctionCall
from .diff_extractor import ChangeType, FileDiff, FunctionChange

log = structlog.get_logger()


class ImpactLevel(StrEnum):
    """Level of impact for a change."""
    CRITICAL = auto()  # Breaking changes, security implications
    HIGH = auto()      # Core business logic, many callers
    MEDIUM = auto()    # Moderate impact, some callers
    LOW = auto()       # Minimal impact, isolated changes
    TRIVIAL = auto()   # Cosmetic, documentation only


class WarningType(StrEnum):
    """Types of warnings from impact analysis."""
    BREAKING_SIGNATURE = auto()
    MISSING_TESTS = auto()
    MANY_CALLERS = auto()
    DELETED_FUNCTION = auto()
    UNUSED_PARAMETER = auto()
    IMPORT_CHANGE = auto()


@dataclass(slots=True)
class ImpactWarning:
    """A warning from impact analysis."""
    
    warning_type: WarningType
    message: str
    file_path: str
    function_name: str | None = None
    line: int | None = None
    severity: ImpactLevel = ImpactLevel.MEDIUM


@dataclass(slots=True)
class FunctionImpact:
    """Impact analysis for a single function."""
    
    name: str
    file_path: str
    change_type: ChangeType
    impact_level: ImpactLevel
    caller_count: int = 0
    callers: list[FunctionCall] = field(default_factory=list)
    warnings: list[ImpactWarning] = field(default_factory=list)
    has_tests: bool = False
    signature_changed: bool = False
    
    @property
    def needs_deep_review(self) -> bool:
        """Determine if function needs deep review."""
        match self.impact_level:
            case ImpactLevel.CRITICAL | ImpactLevel.HIGH:
                return True
            case ImpactLevel.MEDIUM:
                return self.signature_changed or self.caller_count > 2
            case _:
                return False


@dataclass(slots=True)
class ImpactReport:
    """Complete impact analysis report for a PR."""
    
    functions: list[FunctionImpact] = field(default_factory=list)
    breaking_changes: list[ImpactWarning] = field(default_factory=list)
    warnings: list[ImpactWarning] = field(default_factory=list)
    test_coverage: dict[str, bool] = field(default_factory=dict)
    affected_files: set[str] = field(default_factory=set)
    
    @property
    def has_breaking_changes(self) -> bool:
        return len(self.breaking_changes) > 0
    
    @property
    def critical_functions(self) -> list[FunctionImpact]:
        return [f for f in self.functions if f.impact_level == ImpactLevel.CRITICAL]
    
    @property
    def high_impact_functions(self) -> list[FunctionImpact]:
        return [
            f for f in self.functions
            if f.impact_level in (ImpactLevel.CRITICAL, ImpactLevel.HIGH)
        ]
    
    def functions_needing_review(self) -> list[FunctionImpact]:
        """Get functions that need deep review."""
        return [f for f in self.functions if f.needs_deep_review]


class ImpactAnalyzer:
    """Analyze the impact of code changes.
    
    Uses call graph and AST analysis to determine:
    - Which functions are affected by changes
    - Breaking changes to APIs
    - Test coverage gaps
    - High-risk changes
    """
    
    # Thresholds for impact classification
    HIGH_CALLER_THRESHOLD = 5
    MEDIUM_CALLER_THRESHOLD = 2
    
    def __init__(self) -> None:
        self._analyzer = get_ast_analyzer()
    
    def analyze(
        self,
        diffs: list[FileDiff],
        call_graph: CallGraph,
        function_changes: dict[str, dict],
    ) -> ImpactReport:
        """Analyze impact of changes.
        
        Args:
            diffs: List of file diffs.
            call_graph: Call graph for changed code.
            function_changes: Dict of function changes from AST comparison.
            
        Returns:
            ImpactReport with analysis results.
        """
        log.info(
            "impact_analyzer.analyzing",
            diff_count=len(diffs),
            function_count=len(function_changes),
        )
        
        report = ImpactReport()
        
        # Analyze each changed function
        for func_name, change_info in function_changes.items():
            impact = self._analyze_function(
                func_name, change_info, call_graph
            )
            report.functions.append(impact)
            
            # Collect warnings
            report.warnings.extend(impact.warnings)
            
            # Track breaking changes
            if impact.signature_changed and impact.caller_count > 0:
                warning = ImpactWarning(
                    warning_type=WarningType.BREAKING_SIGNATURE,
                    message=f"Signature change affects {impact.caller_count} callers",
                    file_path=impact.file_path,
                    function_name=func_name,
                    severity=ImpactLevel.CRITICAL,
                )
                report.breaking_changes.append(warning)
        
        # Analyze deleted files
        for diff in diffs:
            if diff.status == ChangeType.DELETED:
                self._analyze_deleted_file(diff, call_graph, report)
        
        # Check test coverage
        self._analyze_test_coverage(report, diffs)
        
        # Collect affected files
        for impact in report.functions:
            report.affected_files.add(impact.file_path)
            for caller in impact.callers:
                report.affected_files.add(caller.caller_file)
        
        log.info(
            "impact_analyzer.complete",
            functions_analyzed=len(report.functions),
            breaking_changes=len(report.breaking_changes),
            warnings=len(report.warnings),
        )
        
        return report
    
    def _analyze_function(
        self,
        func_name: str,
        change_info: dict,
        call_graph: CallGraph,
    ) -> FunctionImpact:
        """Analyze impact of a single function change."""
        change_type = self._map_change_type(change_info["type"])
        
        # Get function details
        new_func: FunctionDefinition | None = change_info.get("new")
        old_func: FunctionDefinition | None = change_info.get("old")
        file_path = (new_func or old_func).file_path if (new_func or old_func) else ""
        
        # Get callers from call graph
        callers = call_graph.get_callers(func_name)
        caller_count = len(callers)
        
        # Check signature change
        signature_changed = change_info.get("signature_changed", False)
        if old_func and new_func:
            signature_changed = signature_changed or (
                old_func.signature != new_func.signature
            )
        
        # Determine impact level
        impact_level = self._determine_impact_level(
            change_type, caller_count, signature_changed, new_func
        )
        
        # Generate warnings
        warnings = self._generate_warnings(
            func_name, file_path, change_type, caller_count,
            signature_changed, old_func, new_func
        )
        
        return FunctionImpact(
            name=func_name,
            file_path=file_path,
            change_type=change_type,
            impact_level=impact_level,
            caller_count=caller_count,
            callers=callers,
            warnings=warnings,
            signature_changed=signature_changed,
        )
    
    def _determine_impact_level(
        self,
        change_type: ChangeType,
        caller_count: int,
        signature_changed: bool,
        func: FunctionDefinition | None,
    ) -> ImpactLevel:
        """Determine impact level for a function change."""
        # Deleted functions with callers are critical
        if change_type == ChangeType.DELETED and caller_count > 0:
            return ImpactLevel.CRITICAL
        
        # Signature changes with callers are critical
        if signature_changed and caller_count > 0:
            return ImpactLevel.CRITICAL
        
        # High caller count is high impact
        if caller_count >= self.HIGH_CALLER_THRESHOLD:
            return ImpactLevel.HIGH
        
        # Check for security-sensitive patterns
        if func and self._is_security_sensitive(func):
            return ImpactLevel.HIGH
        
        # Medium caller count is medium impact
        if caller_count >= self.MEDIUM_CALLER_THRESHOLD:
            return ImpactLevel.MEDIUM
        
        # New functions with no callers are low impact
        if change_type == ChangeType.ADDED:
            return ImpactLevel.LOW
        
        # Check for trivial changes (docstring only, etc.)
        if func and self._is_trivial_change(func):
            return ImpactLevel.TRIVIAL
        
        return ImpactLevel.MEDIUM
    
    def _is_security_sensitive(self, func: FunctionDefinition) -> bool:
        """Check if function involves security-sensitive operations."""
        sensitive_patterns = {
            "auth", "login", "password", "secret", "token",
            "encrypt", "decrypt", "hash", "verify", "permission",
            "sanitize", "escape", "validate", "sql", "query",
        }
        
        name_lower = func.name.lower()
        content_lower = func.content.lower()
        
        return any(
            pattern in name_lower or pattern in content_lower
            for pattern in sensitive_patterns
        )
    
    def _is_trivial_change(self, func: FunctionDefinition) -> bool:
        """Check if the change is trivial (docs, formatting)."""
        # This is a simplified check - in practice you'd compare
        # before/after and check for semantic equivalence
        return False
    
    def _generate_warnings(
        self,
        func_name: str,
        file_path: str,
        change_type: ChangeType,
        caller_count: int,
        signature_changed: bool,
        old_func: FunctionDefinition | None,
        new_func: FunctionDefinition | None,
    ) -> list[ImpactWarning]:
        """Generate warnings for a function change."""
        warnings: list[ImpactWarning] = []
        
        # Warning for many callers
        if caller_count >= self.HIGH_CALLER_THRESHOLD:
            warnings.append(ImpactWarning(
                warning_type=WarningType.MANY_CALLERS,
                message=f"Function has {caller_count} callers that may be affected",
                file_path=file_path,
                function_name=func_name,
                severity=ImpactLevel.HIGH,
            ))
        
        # Warning for deleted function with callers
        if change_type == ChangeType.DELETED and caller_count > 0:
            warnings.append(ImpactWarning(
                warning_type=WarningType.DELETED_FUNCTION,
                message=f"Deleted function still has {caller_count} callers",
                file_path=file_path,
                function_name=func_name,
                severity=ImpactLevel.CRITICAL,
            ))
        
        # Check for new unused parameters
        if old_func and new_func:
            old_params = {p.name for p in old_func.parameters}
            new_params = {p.name for p in new_func.parameters}
            added_params = new_params - old_params
            
            if added_params:
                # Check if callers pass the new parameters
                # (simplified - would need call site analysis)
                for param in added_params:
                    param_obj = next(
                        (p for p in new_func.parameters if p.name == param), None
                    )
                    if param_obj and param_obj.default_value is None:
                        warnings.append(ImpactWarning(
                            warning_type=WarningType.BREAKING_SIGNATURE,
                            message=f"New required parameter '{param}' added",
                            file_path=file_path,
                            function_name=func_name,
                            severity=ImpactLevel.CRITICAL if caller_count > 0 else ImpactLevel.MEDIUM,
                        ))
        
        return warnings
    
    def _analyze_deleted_file(
        self,
        diff: FileDiff,
        call_graph: CallGraph,
        report: ImpactReport,
    ) -> None:
        """Analyze impact of deleted file."""
        if not diff.base_content:
            return
        
        # Extract functions that were in the deleted file
        functions = self._analyzer.extract_functions(
            diff.file_path, diff.base_content
        )
        
        for func in functions:
            callers = call_graph.get_callers(func.name)
            if callers:
                report.breaking_changes.append(ImpactWarning(
                    warning_type=WarningType.DELETED_FUNCTION,
                    message=f"Deleted function '{func.name}' has {len(callers)} callers",
                    file_path=diff.file_path,
                    function_name=func.name,
                    severity=ImpactLevel.CRITICAL,
                ))
    
    def _analyze_test_coverage(
        self,
        report: ImpactReport,
        diffs: list[FileDiff],
    ) -> None:
        """Analyze test coverage for changed functions."""
        # Find test files in the changes
        test_files = {
            d.file_path for d in diffs
            if self._is_test_file(d.file_path)
        }
        
        # Check if each changed function has tests
        for impact in report.functions:
            func_name = impact.name
            
            # Simple heuristic: check if there's a test file with matching name
            expected_test_patterns = [
                f"test_{func_name}",
                f"{func_name}_test",
                f"Test{func_name.title()}",
            ]
            
            # Check test files for test functions
            has_test = False
            for test_file in test_files:
                # Would need to parse test file content for accurate detection
                has_test = any(
                    pattern.lower() in test_file.lower()
                    for pattern in expected_test_patterns
                )
                if has_test:
                    break
            
            impact.has_tests = has_test
            report.test_coverage[func_name] = has_test
            
            if not has_test and impact.impact_level in (ImpactLevel.CRITICAL, ImpactLevel.HIGH):
                report.warnings.append(ImpactWarning(
                    warning_type=WarningType.MISSING_TESTS,
                    message=f"High-impact function '{func_name}' has no associated tests",
                    file_path=impact.file_path,
                    function_name=func_name,
                    severity=ImpactLevel.MEDIUM,
                ))
    
    @staticmethod
    def _is_test_file(file_path: str) -> bool:
        """Check if a file is a test file."""
        path_lower = file_path.lower()
        return any([
            "test_" in path_lower,
            "_test." in path_lower,
            "/tests/" in path_lower,
            "/test/" in path_lower,
            "spec." in path_lower,
        ])
    
    @staticmethod
    def _map_change_type(type_str: str) -> ChangeType:
        """Map change type string to enum."""
        match type_str:
            case "added":
                return ChangeType.ADDED
            case "deleted":
                return ChangeType.DELETED
            case "modified":
                return ChangeType.MODIFIED
            case _:
                return ChangeType.MODIFIED
