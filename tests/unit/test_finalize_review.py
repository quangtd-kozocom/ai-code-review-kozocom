# tests/unit/test_finalize_review.py
"""Tests for finalize_review node."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.nodes.finalize_review import run, _build_summary
from src.agents.state import (
    PRContext,
    BreakingChange,
    AffectedCaller,
    ReviewComment,
    ReviewState,
)


@pytest.fixture
def pr_context():
    return PRContext(
        owner="test-org",
        repo="test-repo",
        pr_number=42,
        title="Test PR",
        author="dev123",
        installation_id=12345,
        base_branch="main",
        head_branch="feature/test",
    )


@pytest.fixture
def breaking_change():
    return BreakingChange(
        entity_type="function",
        entity_name="processPayment",
        class_name="PaymentService",
        file_path="src/payment.py",
        change_type="signature_changed",
        old_definition="def processPayment(amount)",
        new_definition="def processPayment(amount, customer_id)",
        change_detail="Added required parameter: customer_id",
        line=42,
        affected_callers=[
            AffectedCaller(file_path="src/checkout.py", line=10, call_text="processPayment(100)", break_reason="Missing customer_id"),
        ],
        severity="critical",
        recommendation="Add default value for customer_id",
    )


@pytest.fixture
def review_comment():
    return ReviewComment(
        file="src/payment.py",
        line=42,
        severity="critical",
        message="Breaking change detected",
        affected_files=[{"path": "src/checkout.py", "line": 10, "reason": "Missing param"}],
        recommendation="Fix the callers",
    )


class TestBuildSummary:
    def test_no_breaking_changes(self, pr_context):
        result = _build_summary(pr_context, [])
        assert "No breaking changes" in result
        assert "42" in result

    def test_with_breaking_changes(self, pr_context, breaking_change):
        result = _build_summary(pr_context, [breaking_change])
        assert "Critical: 1" in result
        assert "processPayment" in result


class TestRun:
    @pytest.mark.asyncio
    async def test_run_without_context(self):
        state: ReviewState = {}
        result = await run(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_run_db_not_configured(self, pr_context, breaking_change, review_comment):
        state: ReviewState = {
            "pr_context": pr_context,
            "all_breaking_changes": [breaking_change],
            "all_comments": [review_comment],
            "file_diffs": [],
        }

        with patch("src.agents.nodes.finalize_review.is_db_configured", return_value=False), \
             patch("src.agents.nodes.finalize_review.SlackService") as mock_slack_cls:

            mock_slack = MagicMock()
            mock_slack.is_configured.return_value = False
            mock_slack_cls.return_value = mock_slack

            result = await run(state)

            assert "db_result" in result
            assert "slack_result" in result
            assert result["db_result"]["status"] == "skipped"
            assert result["db_result"]["reason"] == "Database not configured"

    @pytest.mark.asyncio
    async def test_run_with_mocked_db(self, pr_context, breaking_change, review_comment):
        state: ReviewState = {
            "pr_context": pr_context,
            "all_breaking_changes": [breaking_change],
            "all_comments": [review_comment],
            "file_diffs": [],
        }

        mock_repo = MagicMock()
        mock_repo.id = 1
        mock_review = MagicMock()
        mock_review.id = 123

        mock_repository = AsyncMock()
        mock_repository.get_or_create_repo = AsyncMock(return_value=mock_repo)
        mock_repository.get_review_by_pr = AsyncMock(return_value=None)
        mock_repository.create_review = AsyncMock(return_value=mock_review)
        mock_repository.add_breaking_change = AsyncMock()
        mock_repository.add_comment = AsyncMock()

        async def mock_session_context():
            yield MagicMock()

        with patch("src.agents.nodes.finalize_review.is_db_configured", return_value=True), \
             patch("src.agents.nodes.finalize_review.get_session") as mock_get_session, \
             patch("src.agents.nodes.finalize_review.ReviewRepository", return_value=mock_repository), \
             patch("src.agents.nodes.finalize_review.SlackService") as mock_slack_cls:

            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_get_session.return_value.__aexit__ = AsyncMock()

            mock_slack = MagicMock()
            mock_slack.is_configured.return_value = False
            mock_slack_cls.return_value = mock_slack

            result = await run(state)

            assert "db_result" in result
            assert result["db_result"]["status"] == "success"
            assert result["db_result"]["review_id"] == 123
