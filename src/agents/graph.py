"""LangGraph workflow for PR code review.

Implements a file-by-file processing workflow with:
- Immediate GitHub publishing per file
- LLM-driven search planning and verification
- Automatic cleanup on completion/error
"""

from typing import Literal

import structlog
from langgraph.graph import END, StateGraph

from .constants import (
    NODE_ANALYZE_FILE,
    NODE_CLEANUP,
    NODE_CLONE_REPO,
    NODE_EXECUTE_SEARCH,
    NODE_EXTRACT_DIFF,
    NODE_GENERATE_REVIEW,
    NODE_GET_NEXT_FILE,
    NODE_NEXT_CHANGE,
    NODE_PLAN_SEARCH,
    NODE_PUBLISH_GITHUB,
    NODE_PUBLISH_SUMMARY,
    NODE_VERIFY_IMPACT,
    ROUTE_END,
)
from .nodes import (
    analyze_file,
    clone_repo,
    execute_search,
    extract_diff,
    generate_file_review,
    get_next_file,
    plan_search,
    publish_github,
    publish_summary,
    verify_impact,
)
from .state import ReviewState

log = structlog.get_logger()

__all__ = ["create_review_graph", "run_review"]


# ═══════════════════════════════════════════════════════════════════════════════
# Routing Functions
# ═══════════════════════════════════════════════════════════════════════════════


def route_after_extract(state: ReviewState) -> Literal["clone_repo", "end"]:
    """Route after extracting diff - skip if no files."""
    if state.get("skip_review"):
        log.info("route.after_extract", decision=ROUTE_END, reason="skip_review")
        return ROUTE_END
    log.debug("route.after_extract", decision=NODE_CLONE_REPO)
    return NODE_CLONE_REPO


def route_after_get_file(
    state: ReviewState,
) -> Literal["analyze_file", "publish_summary"]:
    """Route after getting next file - continue or finish."""
    if state.get("current_file") is None:
        log.info("route.after_get_file", decision=NODE_PUBLISH_SUMMARY, reason="no more files")
        return NODE_PUBLISH_SUMMARY
    log.debug(
        "route.after_get_file",
        decision=NODE_ANALYZE_FILE,
        file=state["current_file"].file_path,
    )
    return NODE_ANALYZE_FILE


def route_after_analyze(
    state: ReviewState,
) -> Literal["plan_search", "get_next_file"]:
    """Route after analyzing file - search if changes found."""
    changes = state.get("file_changes", [])
    if not changes:
        log.info("route.after_analyze", decision=NODE_GET_NEXT_FILE, reason="no breaking changes")
        return NODE_GET_NEXT_FILE
    log.debug(
        "route.after_analyze",
        decision=NODE_PLAN_SEARCH,
        changes_count=len(changes),
    )
    return NODE_PLAN_SEARCH


def route_after_verify(
    state: ReviewState,
) -> Literal["plan_search", "next_change", "generate_review"]:
    """Route after verifying impact - more search, next change, or generate."""
    if state.get("need_more_search"):
        log.debug("route.after_verify", decision=NODE_PLAN_SEARCH, reason="need more search")
        return NODE_PLAN_SEARCH

    # Check if more changes to process
    changes = state.get("file_changes", [])
    idx = state.get("current_change_index", 0)

    if idx + 1 < len(changes):
        log.debug(
            "route.after_verify",
            decision=NODE_NEXT_CHANGE,
            current_index=idx,
            total_changes=len(changes),
        )
        return NODE_NEXT_CHANGE

    log.debug("route.after_verify", decision=NODE_GENERATE_REVIEW)
    return NODE_GENERATE_REVIEW


def route_after_publish(state: ReviewState) -> Literal["get_next_file"]:
    """Route after publishing - always get next file."""
    log.debug("route.after_publish", decision=NODE_GET_NEXT_FILE)
    return NODE_GET_NEXT_FILE


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Nodes
# ═══════════════════════════════════════════════════════════════════════════════


async def next_change(state: ReviewState) -> dict:
    """Move to next change in current file."""
    changes = state.get("file_changes", [])
    idx = state.get("current_change_index", 0) + 1

    if idx >= len(changes):
        log.debug("next_change.no_more", index=idx, total=len(changes))
        return {"current_change": None, "current_change_index": idx}

    next_entity = changes[idx]
    log.info(
        "next_change.processing",
        index=idx,
        total=len(changes),
        entity=next_entity.entity_name,
        entity_type=next_entity.entity_type,
    )

    return {
        "current_change_index": idx,
        "current_change": next_entity,
        "search_plan": None,
        "search_results": [],
        "search_iteration": 0,
    }


async def cleanup_node(state: ReviewState) -> dict:
    """Cleanup cloned repo on completion."""
    repo_path = state.get("repo_path")

    log.info(
        "cleanup.started",
        repo_path=repo_path,
        has_repo=bool(repo_path),
    )

    if repo_path:
        await clone_repo.cleanup_repo(repo_path)

    log.info("cleanup.complete")
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ═══════════════════════════════════════════════════════════════════════════════


def create_review_graph() -> StateGraph:
    """Create the PR review workflow graph.

    Flow:
    1. extract_diff → clone_repo → get_next_file
    2. For each file:
       - analyze_file → (if changes) plan_search → execute_search → verify_impact
       - Loop: verify may request more search
       - Loop: process all changes in file
       - generate_file_review → publish_github → get_next_file
    3. After all files: publish_summary → cleanup → END
    """
    log.debug("graph.creating")

    graph = StateGraph(ReviewState)

    # ─────────────────────────────────────────────────────────────────────────
    # Add nodes
    # ─────────────────────────────────────────────────────────────────────────
    graph.add_node(NODE_EXTRACT_DIFF, extract_diff.run)
    graph.add_node(NODE_CLONE_REPO, clone_repo.run)
    graph.add_node(NODE_GET_NEXT_FILE, get_next_file.run)
    graph.add_node(NODE_ANALYZE_FILE, analyze_file.run)
    graph.add_node(NODE_PLAN_SEARCH, plan_search.run)
    graph.add_node(NODE_EXECUTE_SEARCH, execute_search.run)
    graph.add_node(NODE_VERIFY_IMPACT, verify_impact.run)
    graph.add_node(NODE_NEXT_CHANGE, next_change)
    graph.add_node(NODE_GENERATE_REVIEW, generate_file_review.run)
    graph.add_node(NODE_PUBLISH_GITHUB, publish_github.run)
    graph.add_node(NODE_PUBLISH_SUMMARY, publish_summary.run)
    graph.add_node(NODE_CLEANUP, cleanup_node)

    # ─────────────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────────────
    graph.set_entry_point(NODE_EXTRACT_DIFF)

    # ─────────────────────────────────────────────────────────────────────────
    # Edges
    # ─────────────────────────────────────────────────────────────────────────

    # Initial flow
    graph.add_conditional_edges(NODE_EXTRACT_DIFF, route_after_extract, {
        NODE_CLONE_REPO: NODE_CLONE_REPO,
        ROUTE_END: NODE_CLEANUP,
    })
    graph.add_edge(NODE_CLONE_REPO, NODE_GET_NEXT_FILE)

    # File loop
    graph.add_conditional_edges(NODE_GET_NEXT_FILE, route_after_get_file, {
        NODE_ANALYZE_FILE: NODE_ANALYZE_FILE,
        NODE_PUBLISH_SUMMARY: NODE_PUBLISH_SUMMARY,
    })

    # Analysis → Search
    graph.add_conditional_edges(NODE_ANALYZE_FILE, route_after_analyze, {
        NODE_PLAN_SEARCH: NODE_PLAN_SEARCH,
        NODE_GET_NEXT_FILE: NODE_GET_NEXT_FILE,
    })

    # Search loop
    graph.add_edge(NODE_PLAN_SEARCH, NODE_EXECUTE_SEARCH)
    graph.add_edge(NODE_EXECUTE_SEARCH, NODE_VERIFY_IMPACT)

    graph.add_conditional_edges(NODE_VERIFY_IMPACT, route_after_verify, {
        NODE_PLAN_SEARCH: NODE_PLAN_SEARCH,
        NODE_NEXT_CHANGE: NODE_NEXT_CHANGE,
        NODE_GENERATE_REVIEW: NODE_GENERATE_REVIEW,
    })

    # Next change loops back to plan_search
    graph.add_edge(NODE_NEXT_CHANGE, NODE_PLAN_SEARCH)

    # Generate → Publish → Next file
    graph.add_edge(NODE_GENERATE_REVIEW, NODE_PUBLISH_GITHUB)
    graph.add_conditional_edges(NODE_PUBLISH_GITHUB, route_after_publish, {
        NODE_GET_NEXT_FILE: NODE_GET_NEXT_FILE,
    })

    # Final summary and cleanup
    graph.add_edge(NODE_PUBLISH_SUMMARY, NODE_CLEANUP)
    graph.add_edge(NODE_CLEANUP, END)

    log.debug("graph.created", nodes=list(graph.nodes.keys()))

    return graph


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════


async def run_review(state: ReviewState) -> ReviewState:
    """Run the review workflow with error handling and cleanup.

    Args:
        state: Initial state with pr_context.

    Returns:
        Final state with all results.
    """
    ctx = state["pr_context"]
    repo_path = None

    log.info(
        "review.started",
        pr=ctx.pr_number,
        repo=f"{ctx.owner}/{ctx.repo}",
        author=ctx.author,
        title=ctx.title,
    )

    graph = create_review_graph()
    compiled = graph.compile()

    try:
        result = await compiled.ainvoke(state)

        # Track repo_path for cleanup on error
        repo_path = result.get("repo_path")

        log.info(
            "review.complete",
            pr=ctx.pr_number,
            comments=len(result.get("all_comments", [])),
            breaking_changes=len(result.get("all_breaking_changes", [])),
            published=len(result.get("published_comments", [])),
        )

        return result

    except Exception as e:
        log.error(
            "review.failed",
            pr=ctx.pr_number,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Ensure cleanup on error
        repo_path = repo_path or state.get("repo_path")
        if repo_path:
            log.info("review.cleanup_on_error", repo_path=repo_path)
            await clone_repo.cleanup_repo(repo_path)

        raise
