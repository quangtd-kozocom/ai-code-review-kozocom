from langgraph.graph import END, StateGraph

from .nodes import (
    aggregator,
    context_extractor,
    github_publisher,
    logic_agent,
    security_agent,
    slack_reporter,
    style_agent,
)
from .state import GraphState


def create_graph() -> StateGraph:
    """Create the review workflow graph."""
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)

    # Flow
    g.set_entry_point("extract")

    # Parallel agents (fan-out)
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")

    # Fan-in to aggregator
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")

    # Publish and notify
    g.add_edge("aggregate", "publish")
    g.add_edge("publish", "notify")
    g.add_edge("notify", END)

    return g.compile()


# Singleton
graph = create_graph()
