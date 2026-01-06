"""Parse @reviewer commands from PR comments."""

import re
from dataclasses import dataclass

from .commands import CommandType

# Pre-compiled regex patterns for performance
_PATTERNS: dict[CommandType, re.Pattern[str]] = {
    CommandType.FIX: re.compile(r"@reviewer\s+fix(?:\s+this)?", re.IGNORECASE),
    CommandType.EXPLAIN: re.compile(r"@reviewer\s+explain(?:\s+this)?", re.IGNORECASE),
    CommandType.HELP: re.compile(r"@reviewer\s+help", re.IGNORECASE),
    CommandType.GENERATE_TESTS: re.compile(
        r"@reviewer\s+(?:generate\s+)?tests?(?:\s+for\s+(.+))?", re.IGNORECASE
    ),
}

# Validation constants
MAX_COMMENT_LENGTH = 10_000
MENTION_MARKER = "@reviewer"


@dataclass(slots=True, frozen=True)
class ParsedCommand:
    """Immutable parsed @reviewer command."""

    type: CommandType
    target: str | None = None
    raw: str = ""


def parse_command(body: str) -> ParsedCommand | None:
    """
    Parse @reviewer command from comment body.

    Args:
        body: Comment body text

    Returns:
        ParsedCommand if valid @reviewer command found, None otherwise

    Examples:
        >>> parse_command("@reviewer fix this")
        ParsedCommand(type=<CommandType.FIX: 'fix'>, target=None, raw='@reviewer fix this')

        >>> parse_command("@reviewer generate tests for auth.py")
        ParsedCommand(type=<CommandType.GENERATE_TESTS: 'generate_tests'>, target='auth.py', ...)
    """
    # Input validation
    if not _is_valid_input(body):
        return None

    # Check for mention marker first (fast path)
    if MENTION_MARKER not in body.lower():
        return None

    # Match commands in priority order
    return _match_command(body)


def _is_valid_input(body: str) -> bool:
    """Validate input before processing."""
    return bool(body) and isinstance(body, str) and len(body) <= MAX_COMMENT_LENGTH


def _match_command(body: str) -> ParsedCommand:
    """Match body against known command patterns."""
    # Order matters: more specific patterns first
    for cmd_type in (
        CommandType.FIX,
        CommandType.EXPLAIN,
        CommandType.HELP,
        CommandType.GENERATE_TESTS,
    ):
        pattern = _PATTERNS[cmd_type]
        if match := pattern.search(body):
            target = None
            # Extract target for generate_tests command
            if cmd_type == CommandType.GENERATE_TESTS and match.lastindex:
                target = match.group(1).strip() if match.group(1) else None
            return ParsedCommand(type=cmd_type, target=target, raw=body)

    return ParsedCommand(type=CommandType.UNKNOWN, raw=body)
