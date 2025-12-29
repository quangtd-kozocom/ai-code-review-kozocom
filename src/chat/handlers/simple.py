"""Simple command handlers - Help and Unknown commands."""

from ..context import CommandContext
from ..responses import ERROR_UNKNOWN_COMMAND, HELP_MESSAGE
from .base import BaseCommandHandler


class HelpCommandHandler(BaseCommandHandler):
    """Return help message."""

    async def execute(self, ctx: CommandContext) -> str:
        return HELP_MESSAGE


class UnknownCommandHandler(BaseCommandHandler):
    """Handle unknown commands."""

    async def execute(self, ctx: CommandContext) -> str:
        return ERROR_UNKNOWN_COMMAND
