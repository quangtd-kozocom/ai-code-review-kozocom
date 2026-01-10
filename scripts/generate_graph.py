#!/usr/bin/env python3
"""Generate workflow graph visualization."""

from graphviz import Digraph


def create_workflow_graph():
    """Create the PR review workflow graph visualization."""
    dot = Digraph(
        name="PR Review Workflow",
        format="png",
        graph_attr={
            "rankdir": "TB",
            "splines": "spline",
            "nodesep": "0.5",
            "ranksep": "0.7",
            "fontname": "Helvetica",
            "fontsize": "12",
            "bgcolor": "white",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "11",
            "style": "filled",
            "shape": "box",
            "margin": "0.2,0.1",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "9",
        },
    )

    # Colors
    init_color = "#e3f2fd"  # Light blue
    file_loop_color = "#fff3e0"  # Light orange
    search_loop_color = "#f3e5f5"  # Light purple
    publish_color = "#e8f5e9"  # Light green
    final_color = "#fce4ec"  # Light pink
    start_end_color = "#424242"  # Dark gray

    # Start/End nodes
    dot.node("START", "START", shape="circle", style="filled", fillcolor=start_end_color, fontcolor="white", width="0.5")
    dot.node("END", "END", shape="doublecircle", style="filled", fillcolor=start_end_color, fontcolor="white", width="0.5")

    # Initialization cluster
    with dot.subgraph(name="cluster_init") as c:
        c.attr(label="Initialization", style="rounded,filled", fillcolor=init_color, fontsize="14")
        c.node("extract_diff", "📥 extract_diff\nFetch PR files from GitHub", fillcolor="#bbdefb")
        c.node("clone_repo", "📂 clone_repo\nShallow clone repo locally", fillcolor="#bbdefb")

    # File Processing Loop cluster
    with dot.subgraph(name="cluster_file_loop") as c:
        c.attr(label="File Processing Loop", style="rounded,filled", fillcolor=file_loop_color, fontsize="14")
        c.node("get_next_file", "📄 get_next_file\nPop next file", shape="diamond", fillcolor="#ffe0b2")
        c.node("analyze_file", "🔍 analyze_file\nLLM detects breaking changes", fillcolor="#ffe0b2")

    # Search Agent Loop cluster
    with dot.subgraph(name="cluster_search_loop") as c:
        c.attr(label="Search Agent Loop", style="rounded,filled", fillcolor=search_loop_color, fontsize="14")
        c.node("plan_search", "🧠 plan_search\nLLM plans search queries", fillcolor="#e1bee7")
        c.node("execute_search", "🔎 execute_search\nRipgrep search", fillcolor="#e1bee7")
        c.node("verify_impact", "✅ verify_impact\nLLM verifies callers", fillcolor="#e1bee7")
        c.node("next_change", "➡️ next_change\nNext entity", shape="diamond", fillcolor="#e1bee7")

    # Publishing cluster
    with dot.subgraph(name="cluster_publish") as c:
        c.attr(label="Publishing", style="rounded,filled", fillcolor=publish_color, fontsize="14")
        c.node("generate_review", "📝 generate_review\nLLM formats comments", fillcolor="#c8e6c9")
        c.node("publish_github", "🐙 publish_github\nPost to PR immediately", fillcolor="#c8e6c9")

    # Finalization cluster
    with dot.subgraph(name="cluster_final") as c:
        c.attr(label="Finalization", style="rounded,filled", fillcolor=final_color, fontsize="14")
        c.node("publish_summary", "📢 publish_summary\nSlack notification", fillcolor="#f8bbd9")
        c.node("cleanup", "🧹 cleanup\nRemove cloned repo", fillcolor="#f8bbd9")

    # Edges - Initialization
    dot.edge("START", "extract_diff")
    dot.edge("extract_diff", "clone_repo", label="has files")
    dot.edge("extract_diff", "cleanup", label="no code files", style="dashed")
    dot.edge("clone_repo", "get_next_file")

    # Edges - File Loop
    dot.edge("get_next_file", "analyze_file", label="has file")
    dot.edge("get_next_file", "publish_summary", label="no more files")
    dot.edge("analyze_file", "plan_search", label="has changes")
    dot.edge("analyze_file", "get_next_file", label="no changes", style="dashed")

    # Edges - Search Loop
    dot.edge("plan_search", "execute_search")
    dot.edge("execute_search", "verify_impact")
    dot.edge("verify_impact", "plan_search", label="need more\nsearch", style="dashed", constraint="false")
    dot.edge("verify_impact", "next_change", label="more changes")
    dot.edge("verify_impact", "generate_review", label="done")
    dot.edge("next_change", "plan_search")

    # Edges - Publishing
    dot.edge("generate_review", "publish_github")
    dot.edge("publish_github", "get_next_file")

    # Edges - Finalization
    dot.edge("publish_summary", "cleanup")
    dot.edge("cleanup", "END")

    return dot


if __name__ == "__main__":
    import sys
    from pathlib import Path

    output_dir = Path(__file__).parent.parent / "docs"
    output_file = output_dir / "workflow_graph_v2"

    dot = create_workflow_graph()
    dot.render(output_file, cleanup=True)

    print(f"✅ Graph generated: {output_file}.png")
