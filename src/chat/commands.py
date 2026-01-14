"""Command type definitions using modern Python enums."""

from enum import StrEnum


class CommandType(StrEnum):
    """Supported @reviewer command types."""

    FIX = "fix"
    HELP = "help"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> CommandType:
        """Safely convert string to CommandType."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN
