"""Tests for CommandType enum."""

from src.chat.commands import CommandType


class TestCommandType:
    """Tests for CommandType enum."""

    def test_all_values_exist(self):
        """Should have all expected command types."""
        assert CommandType.FIX == "fix"
        assert CommandType.GENERATE_TESTS == "generate_tests"
        assert CommandType.EXPLAIN == "explain"
        assert CommandType.HELP == "help"
        assert CommandType.UNKNOWN == "unknown"

    def test_from_string_valid(self):
        """Should convert valid strings to CommandType."""
        assert CommandType.from_string("fix") == CommandType.FIX
        assert CommandType.from_string("generate_tests") == CommandType.GENERATE_TESTS
        assert CommandType.from_string("explain") == CommandType.EXPLAIN
        assert CommandType.from_string("help") == CommandType.HELP

    def test_from_string_case_insensitive(self):
        """Should handle case-insensitive conversion."""
        assert CommandType.from_string("FIX") == CommandType.FIX
        assert CommandType.from_string("Fix") == CommandType.FIX
        assert CommandType.from_string("HELP") == CommandType.HELP

    def test_from_string_invalid(self):
        """Should return UNKNOWN for invalid strings."""
        assert CommandType.from_string("invalid") == CommandType.UNKNOWN
        assert CommandType.from_string("foobar") == CommandType.UNKNOWN
        assert CommandType.from_string("") == CommandType.UNKNOWN

    def test_is_str_enum(self):
        """CommandType should be usable as string."""
        assert str(CommandType.FIX) == "fix"
        assert f"{CommandType.HELP}" == "help"
