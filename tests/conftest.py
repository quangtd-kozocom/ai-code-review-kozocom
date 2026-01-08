import os
from unittest.mock import MagicMock, patch

import pytest

# Set test environment variables before importing app
os.environ.update(
    {
        "GITHUB_APP_ID": "123456",
        "GITHUB_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        "GITHUB_WEBHOOK_SECRET": "test-secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-test",
    }
)


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("src.app.config.get_settings") as mock:
        settings = MagicMock()
        settings.GITHUB_APP_ID = 123456
        settings.GITHUB_PRIVATE_KEY = (
            "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
        )
        settings.GITHUB_WEBHOOK_SECRET = "test-secret"
        settings.REDIS_URL = "redis://localhost:6379"
        settings.OPENAI_API_KEY = "sk-test"
        settings.ANTHROPIC_API_KEY = None
        settings.SLACK_BOT_TOKEN = None
        settings.SLACK_CHANNEL = "#pr-reviews"
        settings.SENTRY_DSN = None
        settings.DEBUG = True
        settings.LOG_LEVEL = "DEBUG"
        mock.return_value = settings
        yield settings


@pytest.fixture
def app(mock_settings):
    """Create test app instance."""
    from fastapi.testclient import TestClient

    from src.app.main import app

    return TestClient(app)
