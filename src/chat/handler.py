"""Main command handler using strategy pattern."""

import structlog

from ..app.services.github import GitHubService
from .commands import CommandType
from .context import CommandContext
from .handlers import (
    BaseCommandHandler,
    FixCommandHandler,
    HelpCommandHandler,
    UnknownCommandHandler,
)

log = structlog.get_logger()

# Command type -> Handler class mapping
HANDLERS: dict[CommandType, type[BaseCommandHandler]] = {
    CommandType.FIX: FixCommandHandler,
    CommandType.HELP: HelpCommandHandler,
    CommandType.UNKNOWN: UnknownCommandHandler,
}


class CommandHandler:
    """Routes commands to appropriate handler implementations."""

    def __init__(self, github: GitHubService):
        self.github = github

    async def handle(self, command_type: CommandType, ctx: CommandContext) -> str:
        """Handle a command and return response text."""
        handler_cls = HANDLERS.get(command_type, UnknownCommandHandler)
        handler = handler_cls(self.github)

        log.info("Executing command", command=command_type, pr=ctx.pr_number, author=ctx.author)
        return await handler.execute(ctx)
