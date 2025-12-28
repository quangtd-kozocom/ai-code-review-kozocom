"""Tests for command parser."""

from src.chat.commands import CommandType
from src.chat.parser import MAX_COMMENT_LENGTH, parse_command


class TestParseCommand:
    """Tests for command parser."""

    def test_parse_fix_command(self):
        """Should parse 'fix this' command."""
        result = parse_command("@reviewer fix this")
        assert result is not None
        assert result.type == CommandType.FIX
        assert result.target is None

    def test_parse_fix_command_without_this(self):
        """Should parse 'fix' without 'this'."""
        result = parse_command("@reviewer fix")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_parse_explain_command(self):
        """Should parse 'explain' command."""
        result = parse_command("@reviewer explain")
        assert result is not None
        assert result.type == CommandType.EXPLAIN

    def test_parse_explain_command_with_this(self):
        """Should parse 'explain this' command."""
        result = parse_command("@reviewer explain this")
        assert result is not None
        assert result.type == CommandType.EXPLAIN

    def test_parse_generate_tests(self):
        """Should parse 'generate tests' without target."""
        result = parse_command("@reviewer generate tests")
        assert result is not None
        assert result.type == CommandType.GENERATE_TESTS
        assert result.target is None

    def test_parse_generate_tests_with_target(self):
        """Should parse 'generate tests' with target file."""
        result = parse_command("@reviewer generate tests for auth.py")
        assert result is not None
        assert result.type == CommandType.GENERATE_TESTS
        assert result.target == "auth.py"

    def test_parse_tests_shorthand(self):
        """Should parse 'tests' shorthand."""
        result = parse_command("@reviewer tests")
        assert result is not None
        assert result.type == CommandType.GENERATE_TESTS

    def test_parse_help(self):
        """Should parse 'help' command."""
        result = parse_command("@reviewer help")
        assert result is not None
        assert result.type == CommandType.HELP

    def test_parse_unknown(self):
        """Should return UNKNOWN for unrecognized commands."""
        result = parse_command("@reviewer something else")
        assert result is not None
        assert result.type == CommandType.UNKNOWN

    def test_no_mention_returns_none(self):
        """Should return None if no @reviewer mention."""
        result = parse_command("just a comment")
        assert result is None

    def test_case_insensitive(self):
        """Should handle case-insensitive mentions."""
        result = parse_command("@REVIEWER FIX THIS")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_mixed_case(self):
        """Should handle mixed case."""
        result = parse_command("@Reviewer Fix This")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_empty_string_returns_none(self):
        """Should return None for empty string."""
        result = parse_command("")
        assert result is None

    def test_too_long_comment_returns_none(self):
        """Should return None for comments exceeding max length."""
        long_body = "a" * (MAX_COMMENT_LENGTH + 1)
        result = parse_command(long_body)
        assert result is None

    def test_with_surrounding_text(self):
        """Should parse command with surrounding text."""
        result = parse_command("Hey there! @reviewer fix this please!")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_stores_raw_body(self):
        """Should store original comment body."""
        body = "@reviewer fix this"
        result = parse_command(body)
        assert result is not None
        assert result.raw == body
