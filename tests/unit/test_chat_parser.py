"""Tests for command parser."""

from src.chat.commands import CommandType
from src.chat.parser import MAX_COMMENT_LENGTH, parse_command


class TestParseCommand:
    def test_parse_fix_command(self):
        result = parse_command("@reviewer fix this")
        assert result is not None
        assert result.type == CommandType.FIX
        assert result.target is None

    def test_parse_fix_command_without_this(self):
        result = parse_command("@reviewer fix")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_parse_help(self):
        result = parse_command("@reviewer help")
        assert result is not None
        assert result.type == CommandType.HELP

    def test_parse_unknown(self):
        result = parse_command("@reviewer something else")
        assert result is not None
        assert result.type == CommandType.UNKNOWN

    def test_no_mention_returns_none(self):
        result = parse_command("just a comment")
        assert result is None

    def test_case_insensitive(self):
        result = parse_command("@REVIEWER FIX THIS")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_mixed_case(self):
        result = parse_command("@Reviewer Fix This")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_empty_string_returns_none(self):
        result = parse_command("")
        assert result is None

    def test_too_long_comment_returns_none(self):
        long_body = "a" * (MAX_COMMENT_LENGTH + 1)
        result = parse_command(long_body)
        assert result is None

    def test_with_surrounding_text(self):
        result = parse_command("Hey there! @reviewer fix this please!")
        assert result is not None
        assert result.type == CommandType.FIX

    def test_stores_raw_body(self):
        body = "@reviewer fix this"
        result = parse_command(body)
        assert result is not None
        assert result.raw == body
