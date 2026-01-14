"""Tests for CommandType enum."""

from src.chat.commands import CommandType


class TestCommandType:
    def test_all_values_exist(self):
        assert CommandType.FIX == "fix"
        assert CommandType.HELP == "help"
        assert CommandType.UNKNOWN == "unknown"

    def test_from_string_valid(self):
        assert CommandType.from_string("fix") == CommandType.FIX
        assert CommandType.from_string("help") == CommandType.HELP

    def test_from_string_case_insensitive(self):
        assert CommandType.from_string("FIX") == CommandType.FIX
        assert CommandType.from_string("Fix") == CommandType.FIX
        assert CommandType.from_string("HELP") == CommandType.HELP

    def test_from_string_invalid(self):
        assert CommandType.from_string("invalid") == CommandType.UNKNOWN
        assert CommandType.from_string("foobar") == CommandType.UNKNOWN
        assert CommandType.from_string("") == CommandType.UNKNOWN

    def test_is_str_enum(self):
        assert str(CommandType.FIX) == "fix"
        assert f"{CommandType.HELP}" == "help"
