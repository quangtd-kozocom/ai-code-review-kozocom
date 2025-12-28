"""Tests for CommandContext dataclass."""

import pytest

from src.chat.context import CommandContext


class TestCommandContext:
    """Tests for CommandContext dataclass."""

    def test_requires_parent_comment_true(self):
        """Should return True when in_reply_to_id is set."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
            in_reply_to_id=456,
        )
        assert ctx.requires_parent_comment is True

    def test_requires_parent_comment_false(self):
        """Should return False when in_reply_to_id is None."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
        )
        assert ctx.requires_parent_comment is False

    def test_immutable(self):
        """Context should be immutable (frozen dataclass)."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
        )
        with pytest.raises(AttributeError):
            ctx.owner = "modified"

    def test_default_values(self):
        """Should have correct default values."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
        )
        assert ctx.target is None
        assert ctx.in_reply_to_id is None

    def test_with_target(self):
        """Should store target correctly."""
        ctx = CommandContext(
            owner="test",
            repo="repo",
            pr_number=1,
            comment_id=123,
            author="user",
            target="auth.py",
        )
        assert ctx.target == "auth.py"

    def test_all_fields(self):
        """Should store all fields correctly."""
        ctx = CommandContext(
            owner="octocat",
            repo="hello-world",
            pr_number=42,
            comment_id=999,
            author="developer",
            target="main.py",
            in_reply_to_id=888,
        )
        assert ctx.owner == "octocat"
        assert ctx.repo == "hello-world"
        assert ctx.pr_number == 42
        assert ctx.comment_id == 999
        assert ctx.author == "developer"
        assert ctx.target == "main.py"
        assert ctx.in_reply_to_id == 888
        assert ctx.requires_parent_comment is True
