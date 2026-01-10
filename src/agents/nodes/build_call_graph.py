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
        state: Current workflow state with file_diffs and function_changes.
        
    Returns:
        State update with call_graph.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {"call_graph": CallGraph()}
    
    ctx = state["pr_context"]
    diffs = state.get("file_diffs", [])
    
    if not diffs:
        log.info("build_call_graph.skipped", reason="no_diffs")
        return {"call_graph": CallGraph()}
    
    log.info(
        "build_call_graph.started",
        owner=ctx.owner,
        repo=ctx.repo,
        files=len(diffs),
    )
    
    async with GitHubService(ctx.installation_id) as github:
        builder = CallGraphBuilder(github_client=github)
        
        # Prepare file info for call graph builder
        changed_files = [
            {
                "file_path": diff.file_path,
                "head_content": diff.head_content,
                "base_content": diff.base_content,
            }
            for diff in diffs
            if diff.head_content  # Only files with content
        ]
        
        # Build call graph
        call_graph = await builder.build_for_changes(
            owner=ctx.owner,
            repo=ctx.repo,
            changed_files=changed_files,
            base_ref=ctx.base_branch,
            head_ref=ctx.head_branch,
        )
        
        log.info(
            "build_call_graph.complete",
            functions=len(call_graph.relations),
            total_callers=sum(
                len(r.callers) for r in call_graph.relations.values()
            ),
        )
        
        return {"call_graph": call_graph}
