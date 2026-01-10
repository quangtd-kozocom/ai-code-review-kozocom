#!/usr/bin/env python3
"""Script to visualize the LangGraph workflow."""

import sys
from pathlib import Path

# Add parent directory to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.graph import create_review_graph


def main():
    """Generate graph visualization."""
    # Create and compile the graph
    graph = create_review_graph()
    app = graph.compile()
    
    # Generate Mermaid diagram
    print("Generating graph visualization...")
    
    try:
        # Try to get PNG image (requires graphviz)
        from langchain_core.runnables.graph import MermaidDrawMethod
        
        png_path = Path(__file__).parent.parent / "docs" / "workflow_graph.png"
        png_path.parent.mkdir(exist_ok=True)
        
        png_data = app.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API
        )
        
        with open(png_path, "wb") as f:
            f.write(png_data)
        
        print(f"✅ PNG saved to: {png_path}")
    except Exception as e:
        print(f"⚠️  Could not generate PNG: {e}")
    
    # Generate Mermaid markdown (always works)
    mermaid_path = Path(__file__).parent.parent / "docs" / "workflow_graph.md"
    mermaid_path.parent.mkdir(exist_ok=True)
    
    mermaid_code = app.get_graph().draw_mermaid()
    
    with open(mermaid_path, "w") as f:
        f.write("# LangGraph Workflow Visualization\n\n")
        f.write("```mermaid\n")
        f.write(mermaid_code)
        f.write("\n```\n")
    
    print(f"✅ Mermaid diagram saved to: {mermaid_path}")
    
    # Also print to console
    print("\n" + "="*80)
    print("MERMAID DIAGRAM (copy to https://mermaid.live)")
    print("="*80 + "\n")
    print(mermaid_code)
    print("\n" + "="*80)
    
    # Print node information
    print("\n📋 Graph Nodes:")
    nodes = app.get_graph().nodes
    for i, node in enumerate(nodes.values(), 1):
        print(f"  {i}. {node.id}")
    
    print("\n🔗 Graph Edges:")
    edges = app.get_graph().edges
    for i, edge in enumerate(edges, 1):
        print(f"  {i}. {edge.source} → {edge.target}")


if __name__ == "__main__":
    main()
