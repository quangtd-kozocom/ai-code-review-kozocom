"""Build call graph node - Phase 2a of the review pipeline.

Builds call relationships for changed functions using AST analysis.
This is a deterministic operation without LLM.
"""

import structlog

from ...analysis.call_graph import CallGraph, CallGraphBuilder
from ...app.services.github import GitHubService
from ..state import ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Build call graph for changed functions.
    
    Phase 2a: Analyze call relationships
    - Find functions that call changed functions (callers)
    - Find functions that changed functions call (callees)
    - Build relationship graph for impact analysis
    
    This node does NOT use LLM - it's purely AST-based.
    
    Args:
        state: Current workflow state with file_diffs, function_changes, and file_contents.
        
    Returns:
        State update with call_graph.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {"call_graph": CallGraph()}
    
    ctx = state["pr_context"]
    file_contents = state.get("file_contents", {})
    
    if not file_contents:
        log.info("build_call_graph.skipped", reason="no_file_contents")
        return {"call_graph": CallGraph()}
    
    log.info(
        "build_call_graph.started",
        owner=ctx.owner,
        repo=ctx.repo,
        files=len(file_contents),
        file_paths=list(file_contents.keys()),
    )
    
    # Build call graph from in-memory file contents
    # This correctly finds all functions and their relationships
    builder = CallGraphBuilder()
    call_graph = builder.build_from_content(file_contents)
    
    log.info(
        "build_call_graph.complete",
        functions=len(call_graph.relations),
        function_names=list(call_graph.relations.keys())[:10],  # Log first 10
        total_callers=sum(
            len(r.callers) for r in call_graph.relations.values()
        ),
        total_callees=sum(
            len(r.callees) for r in call_graph.relations.values()
        ),
    )
    
    return {"call_graph": call_graph}
