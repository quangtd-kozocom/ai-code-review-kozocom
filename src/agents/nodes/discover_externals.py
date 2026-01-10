"""Discover externals node - Phase 2.5a of the review pipeline.

Finds external files that depend on changed code using GitHub Code Search.
This is the optimizer in the evaluator-optimizer pattern.
"""

import structlog

from ...analysis.external_discovery import ExternalDiscoveryService
from ...app.services.github import GitHubService
from ..state import ReviewState

log = structlog.get_logger()


def _extract_search_targets(state: ReviewState) -> tuple[list[str], list[str]]:
    """Extract initial search targets from function changes.
    
    Args:
        state: Current workflow state with function_changes and file_diffs.
        
    Returns:
        Tuple of (changed_classes, changed_methods)
    """
    function_changes = state.get("function_changes", {})
    
    # Extract class names from file paths
    changed_classes = set()
    for func_name, change_info in function_changes.items():
        func_def = change_info.get("new") or change_info.get("old")
        if func_def and hasattr(func_def, "file_path"):
            file_path = func_def.file_path
            if "/" in file_path:
                filename = file_path.split("/")[-1]
                class_name = filename.split(".")[0]
                changed_classes.add(class_name)
    
    # Extract method names
    changed_methods = list(function_changes.keys())
    
    return list(changed_classes), changed_methods


async def run(state: ReviewState) -> dict:
    """Discover external files that depend on changed code.
    
    Phase 2.5a: External discovery (optimizer)
    - Get search targets from state (initial or from evaluator)
    - Search GitHub Code Search API for references
    - Verify usage with AST analysis
    - Return discovered files for evaluation
    
    This implements the optimizer part of the evaluator-optimizer pattern.
    The LLM evaluator decides if we need more context and what to search for next.
    
    Args:
        state: Current workflow state with function_changes or pending_searches.
        
    Returns:
        State update with external_files, pending_searches cleared.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {
            "external_files": [],
            "pending_searches": [],
        }
    
    ctx = state["pr_context"]
    file_diffs = state.get("file_diffs", [])
    iteration = state.get("evaluation_iteration", 0)
    
    # Get search targets
    pending_searches = state.get("pending_searches", [])
    
    if pending_searches:
        # Subsequent iteration: use targets from LLM evaluator
        changed_classes = pending_searches
        changed_methods = []
        log.info(
            "discover_externals.from_evaluator",
            owner=ctx.owner,
            repo=ctx.repo,
            iteration=iteration,
            targets=pending_searches[:10],
        )
    else:
        # Initial iteration: extract from function changes
        changed_classes, changed_methods = _extract_search_targets(state)
        log.info(
            "discover_externals.initial",
            owner=ctx.owner,
            repo=ctx.repo,
            changed_classes=changed_classes[:5],
            changed_methods_count=len(changed_methods),
        )
    
    # Get paths of files in the PR to exclude from search
    pr_file_paths = [diff.file_path for diff in file_diffs]
    
    # Discover external files
    async with GitHubService(ctx.installation_id) as github:
        discovery = ExternalDiscoveryService(github)
        
        new_external_files = await discovery.discover(
            owner=ctx.owner,
            repo=ctx.repo,
            ref=ctx.head_branch,
            changed_classes=changed_classes,
            changed_methods=changed_methods,
            exclude_paths=pr_file_paths,
        )
    
    # Merge with existing external files (avoid duplicates)
    existing_external_files = state.get("external_files", [])
    existing_paths = {f.path for f in existing_external_files}
    
    merged_external_files = list(existing_external_files)
    for ext_file in new_external_files:
        if ext_file.path not in existing_paths:
            merged_external_files.append(ext_file)
            existing_paths.add(ext_file.path)
    
    log.info(
        "discover_externals.complete",
        iteration=iteration,
        new_files=len(new_external_files),
        total_files=len(merged_external_files),
    )
    
    return {
        "external_files": merged_external_files,
        "pending_searches": [],  # Clear pending searches
    }
