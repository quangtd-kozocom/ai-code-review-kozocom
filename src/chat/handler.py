"""Main command handler using strategy pattern."""

import structlog

from ..app.services.github import GitHubService
from .commands import CommandType
from .context import CommandContext
from .handlers import (
    BaseCommandHandler,
    ExplainCommandHandler,
    FixCommandHandler,
    GenerateTestsCommandHandler,
    HelpCommandHandler,
    UnknownCommandHandler,
)

log = structlog.get_logger()


class CommandHandler:
    """
    Main command handler using strategy pattern.

    Routes commands to appropriate handler implementations.
    """

    _handlers: dict[CommandType, type[BaseCommandHandler]] = {
        CommandType.FIX: FixCommandHandler,
        CommandType.EXPLAIN: ExplainCommandHandler,
        CommandType.GENERATE_TESTS: GenerateTestsCommandHandler,
        CommandType.HELP: HelpCommandHandler,
        CommandType.UNKNOWN: UnknownCommandHandler,
    }

    def __init__(self, github: GitHubService):
        self.github = github

    async def handle(self, command_type: CommandType, ctx: CommandContext) -> str:
        """
        Handle a command and return response text.

        Args:
            command_type: Type of command to handle
            ctx: Unified command context

        Returns:
            Response text to post as reply
        """
        handler_cls = self._handlers.get(command_type, UnknownCommandHandler)
        handler = handler_cls(self.github)

        log.info(
            "Executing command",
            command=command_type,
            pr=ctx.pr_number,
            author=ctx.author,
        )

        return await handler.execute(ctx)
