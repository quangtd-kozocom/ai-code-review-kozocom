"""Parse @reviewer commands from PR comments."""

import re
from dataclasses import dataclass

from .commands import CommandType

_PATTERNS: dict[CommandType, re.Pattern[str]] = {
    CommandType.FIX: re.compile(r"@reviewer\s+fix(?:\s+this)?", re.IGNORECASE),
    CommandType.HELP: re.compile(r"@reviewer\s+help", re.IGNORECASE),
}

MAX_COMMENT_LENGTH = 10_000
MENTION_MARKER = "@reviewer"


@dataclass(slots=True, frozen=True)
class ParsedCommand:
    type: CommandType
    target: str | None = None
    raw: str = ""


def parse_command(body: str) -> ParsedCommand | None:
    if not body or not isinstance(body, str) or len(body) > MAX_COMMENT_LENGTH:
        return None
    if MENTION_MARKER not in body.lower():
        return None

    for cmd_type in (CommandType.FIX, CommandType.HELP):
        if _PATTERNS[cmd_type].search(body):
            return ParsedCommand(type=cmd_type, raw=body)

    return ParsedCommand(type=CommandType.UNKNOWN, raw=body)
