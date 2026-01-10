"""Analyze impact node - Phase 2b of the review pipeline.

Determines the impact of changes using call graph and AST analysis.
This is a deterministic operation without LLM.
"""

import structlog

from ...analysis.call_graph import CallGraph
from ...analysis.context_builder import ContextBuilder
from ...analysis.impact_analyzer import ImpactAnalyzer, ImpactReport
from ..state import ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Analyze impact of code changes.
    
    Phase 2b: Impact analysis
    - Determine impact level for each changed function
    - Identify breaking changes
    - Check test coverage
    - Generate warnings
    
    This node does NOT use LLM - it's deterministic analysis.
    
    Args:
        state: Current workflow state with call_graph and function_changes.
        
    Returns:
        State update with impact_report.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {"impact_report": ImpactReport()}
    
    ctx = state["pr_context"]
    diffs = state.get("file_diffs", [])
    call_graph = state.get("call_graph", CallGraph())
    function_changes = state.get("function_changes", {})
    file_contents = state.get("file_contents", {})

    if not function_changes:
        log.info("analyze_impact.skipped", reason="no_function_changes")
        return {"impact_report": ImpactReport()}

    log.info(
        "analyze_impact.started",
        functions=len(function_changes),
        files=len(diffs),
    )

    # Run impact analysis
    analyzer = ImpactAnalyzer()
    report = analyzer.analyze(diffs, call_graph, function_changes)

    # Build review context
    context_builder = ContextBuilder()
    review_context = await context_builder.build(
        owner=ctx.owner,
        repo=ctx.repo,
        pr_number=ctx.pr_number,
        base_branch=ctx.base_branch,
        head_branch=ctx.head_branch,
        diffs=diffs,
        call_graph=call_graph,
        impact_report=report,
        function_changes=function_changes,
        file_contents=file_contents,
    )
    
    log.info(
        "analyze_impact.complete",
        functions_analyzed=len(report.functions),
        breaking_changes=len(report.breaking_changes),
        warnings=len(report.warnings),
        high_impact=len(report.high_impact_functions),
    )
    
    return {
        "impact_report": report,
        "review_context": review_context,
    }
