from langgraph.graph import END, StateGraph

from .nodes import (
    acknowledger,
    aggregator,
    context_extractor,
    github_publisher,
    logic_agent,
    security_agent,
    slack_reporter,
    smart_router,
    style_agent,
)
from .state import GraphState


def create_graph() -> StateGraph:
    """Create the review workflow graph with smart routing."""
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("acknowledge", acknowledger.run)
    g.add_node("extract", context_extractor.run)
    g.add_node("router", smart_router.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)

    # Flow: acknowledge -> extract -> router -> parallel agents -> aggregate -> publish -> notify
    g.set_entry_point("acknowledge")
    g.add_edge("acknowledge", "extract")
    g.add_edge("extract", "router")

    # Router fans out to all agents (agents self-filter based on routing_decisions)
    g.add_edge("router", "security")
    g.add_edge("router", "style")
    g.add_edge("router", "logic")

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
