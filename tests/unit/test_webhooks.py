import hashlib
import hmac
import json
from unittest.mock import patch


class TestGitHubWebhook:
    """Tests for GitHub webhook handler."""

    def test_health_check(self, app):
        """Test health endpoint."""
        response = app.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_api_health_check(self, app):
        """Test API v1 health endpoint."""
        response = app.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_webhook_missing_signature(self, app):
        """Test webhook rejects requests without signature."""
        response = app.post(
            "/api/v1/webhooks/github",
            json={"action": "opened"},
            headers={"x-github-event": "pull_request"},
        )
        assert response.status_code == 401

    def test_webhook_invalid_signature(self, app, mock_settings):
        """Test webhook rejects requests with invalid signature."""
        payload = json.dumps({"action": "opened"})
        response = app.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": "sha256=invalid",
                "content-type": "application/json",
            },
        )
        assert response.status_code == 401

    def test_webhook_valid_signature(self, app, mock_settings):
        """Test webhook accepts requests with valid signature."""
        # Use a 'closed' action without 'merged' flag - should be ignored
        payload = json.dumps(
            {
                "action": "closed",
                "pull_request": {"number": 1, "merged": False},
                "repository": {
                    "name": "test",
                    "full_name": "owner/test",
                    "owner": {"login": "owner"},
                },
                "installation": {"id": 123},
            }
        )
        secret = mock_settings.GITHUB_WEBHOOK_SECRET
        signature = (
            "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        )

        response = app.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": signature,
                "content-type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    @patch("src.workers.tasks.review_pr")
    def test_webhook_queues_pr_review(self, mock_review, app, mock_settings):
        """Test webhook queues PR review for opened PRs."""
        payload = {
            "action": "opened",
            "pull_request": {"number": 42},
            "repository": {
                "name": "test-repo",
                "full_name": "owner/test-repo",
                "owner": {"login": "owner"},
            },
            "installation": {"id": 12345},
        }
        payload_str = json.dumps(payload)
        secret = mock_settings.GITHUB_WEBHOOK_SECRET
        signature = (
            "sha256=" + hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        )

        response = app.post(
            "/api/v1/webhooks/github",
            content=payload_str,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert response.json()["pr"] == 42
        mock_review.delay.assert_called_once_with(
            owner="owner",
            repo="test-repo",
            pr_number=42,
            installation_id=12345,
        )
