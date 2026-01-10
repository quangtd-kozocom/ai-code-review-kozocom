"""Unit tests for the review graph."""

import pytest

from src.agents.graph import create_review_graph
from src.agents.state import PRContext, ReviewState


class TestReviewGraph:
    """Test the review graph structure."""

    def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = create_review_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_all_nodes(self):
        """Graph should have all expected nodes."""
        graph = create_review_graph()
        compiled = graph.compile()

        expected_nodes = {
            "__start__",
            "extract_diff",
            "clone_repo",
            "get_next_file",
            "analyze_file",
            "plan_search",
            "execute_search",
            "verify_impact",
            "next_change",
            "generate_review",
            "publish_github",
            "publish_summary",
            "cleanup",
        }

        assert set(compiled.nodes.keys()) == expected_nodes

    def test_pr_context_creation(self):
        """PRContext should be creatable with required fields."""
        ctx = PRContext(
            owner="test-owner",
            repo="test-repo",
            pr_number=123,
            title="Test PR",
            author="test-user",
            installation_id=456,
            base_branch="main",
            head_branch="feature/test",
        )

        assert ctx.owner == "test-owner"
        assert ctx.repo == "test-repo"
        assert ctx.pr_number == 123
        assert ctx.head_branch == "feature/test"

    def test_initial_state_structure(self):
        """Initial state should have correct structure."""
        ctx = PRContext(
            owner="test-owner",
            repo="test-repo",
            pr_number=123,
            title="Test PR",
            author="test-user",
            installation_id=456,
            base_branch="main",
            head_branch="feature/test",
        )

        state: ReviewState = {
            "pr_context": ctx,
            "file_diffs": [],
            "all_breaking_changes": [],
            "all_comments": [],
            "published_comments": [],
        }

        assert state["pr_context"] == ctx
        assert state["file_diffs"] == []
