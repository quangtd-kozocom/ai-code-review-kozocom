"""LangGraph workflow for PR review.

Implements the 3-phase review pipeline:
1. Diff Analysis (deterministic)
2. Impact Analysis (AST-based)
3. Review (LLM-based)
"""

import structlog
from langgraph.graph import END, StateGraph

from .nodes import (
    aggregate,
    analyze_impact,
    build_call_graph,
    extract_diff,
    review_function,
    route_review,
)
from .nodes.github_publisher import run as publish_github
from .state import ReviewState

log = structlog.get_logger()


def should_skip_review(state: ReviewState) -> str:
    """Check if review should be skipped."""
    if state.get("skip_review"):
        log.info(
            "graph.skipping_review",
            reason=state.get("skip_reason", "unknown"),
        )
        return "skip"
    return "continue"


def should_skip_publish(state: ReviewState) -> str:
    """Check if publishing should be skipped."""
    comments = state.get("final_comments", [])
    if not comments:
        return "skip"
    return "continue"


def create_review_graph() -> StateGraph:
    """Create the v2 PR review workflow graph.
    
    Graph structure:
    ```
    START
      │
      ▼
    extract_diff ──────────────────────────────┐
      │                                         │
      ▼                                         │ (skip)
    build_call_graph                           │
      │                                         │
      ▼                                         │
    analyze_impact                             │
      │                                         │
      ▼                                         │
    route_review                               │
      │                                         │
      ▼                                         │
    review_functions                           │
      │                                         │
      ▼                                         │
    aggregate ◄────────────────────────────────┘
      │
      ├──────────────┐
      ▼              ▼
    publish       notify
      │              │
      └──────┬───────┘
             ▼
            END
    ```
    """
    graph = StateGraph(ReviewState)
    
    # =========================================================================
    # Phase 1: Diff Analysis (deterministic)
    # =========================================================================
    graph.add_node("extract_diff", extract_diff.run)
    
    # =========================================================================
    # Phase 2: Impact Analysis (AST-based)
    # =========================================================================
    graph.add_node("build_call_graph", build_call_graph.run)
    graph.add_node("analyze_impact", analyze_impact.run)
    
    # =========================================================================
    # Phase 3: Review (LLM-based)
    # =========================================================================
    graph.add_node("route_review", route_review.run)
    graph.add_node("review_functions", review_function.run)
    
    # =========================================================================
    # Aggregation & Output
    # =========================================================================
    graph.add_node("aggregate", aggregate.run)
    graph.add_node("publish", publish_github)
    
    # =========================================================================
    # Edges: Linear flow with skip conditions
    # =========================================================================
    
    # Entry point
    graph.set_entry_point("extract_diff")
    
    # After extract_diff, check if we should skip
    graph.add_conditional_edges(
        "extract_diff",
        should_skip_review,
        {
            "skip": "aggregate",
            "continue": "build_call_graph",
        },
    )
    
    # Phase 2 flow
    graph.add_edge("build_call_graph", "analyze_impact")
    graph.add_edge("analyze_impact", "route_review")
    
    # Phase 3 flow
    graph.add_edge("route_review", "review_functions")
    graph.add_edge("review_functions", "aggregate")
    
    # Output flow
    graph.add_conditional_edges(
        "aggregate",
        should_skip_publish,
        {
            "skip": END,
            "continue": "publish",
        },
    )
    
    graph.add_edge("publish", END)
    
    return graph.compile()


# Singleton compiled graph
graph = create_review_graph()


# Backward compatibility alias
def create_graph() -> StateGraph:
    """Create the review workflow graph (backward compatible)."""
    return create_review_graph()
