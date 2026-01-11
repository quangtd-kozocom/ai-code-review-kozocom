# tests/unit/test_finalize_review.py
"""Tests for finalize_review node."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.nodes.finalize_review import (
    run,
    _build_summary,
    _serialize_breaking,
    _serialize_comment,
)
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


class TestSerialize:
    def test_serialize_breaking_change(self, breaking_change):
        result = _serialize_breaking(breaking_change)
        assert result["file_path"] == "src/payment.py"
        assert result["entity_name"] == "processPayment"
        assert result["severity"] == "critical"
        assert len(result["affected_callers"]) == 1
        assert result["affected_callers"][0]["file_path"] == "src/checkout.py"

    def test_serialize_comment(self, review_comment):
        result = _serialize_comment(review_comment)
        assert result["file_path"] == "src/payment.py"
        assert result["severity"] == "critical"
        assert result["line_number"] == 42


class TestRun:
    @pytest.mark.asyncio
    async def test_run_without_context(self):
        state: ReviewState = {}
        result = await run(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_run_with_mocked_services(self, pr_context, breaking_change, review_comment):
        state: ReviewState = {
            "pr_context": pr_context,
            "all_breaking_changes": [breaking_change],
            "all_comments": [review_comment],
            "file_diffs": [],
        }

        mock_settings = MagicMock()
        mock_settings.API_BASE_URL = "http://test-api"

        with patch("src.agents.nodes.finalize_review.settings", mock_settings), \
             patch("src.agents.nodes.finalize_review.SlackService") as mock_slack_cls, \
             patch("httpx.AsyncClient") as mock_client_cls:

            # Mock Slack
            mock_slack = MagicMock()
            mock_slack.is_configured.return_value = False
            mock_slack_cls.return_value = mock_slack

            # Mock HTTP client
            mock_response = MagicMock()
            mock_response.json.return_value = {"review_id": 123}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await run(state)

            assert "db_result" in result
            assert "slack_result" in result
            assert result["db_result"]["status"] == "success"
            assert result["db_result"]["review_id"] == 123

    @pytest.mark.asyncio
    async def test_run_handles_api_error(self, pr_context):
        state: ReviewState = {
            "pr_context": pr_context,
            "all_breaking_changes": [],
            "all_comments": [],
            "file_diffs": [],
        }

        mock_settings = MagicMock()
        mock_settings.API_BASE_URL = "http://test-api"

        with patch("src.agents.nodes.finalize_review.settings", mock_settings), \
             patch("src.agents.nodes.finalize_review.SlackService") as mock_slack_cls, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_slack = MagicMock()
            mock_slack.is_configured.return_value = False
            mock_slack_cls.return_value = mock_slack

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("API Error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await run(state)

            assert result["db_result"]["status"] == "error"
            assert "API Error" in result["db_result"]["error"]
