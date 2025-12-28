"""Unified command context for all handlers."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CommandContext:
    """Immutable context passed to all command handlers."""

    owner: str
    repo: str
    pr_number: int
    comment_id: int
    author: str
    target: str | None = None
    in_reply_to_id: int | None = None

    @property
    def requires_parent_comment(self) -> bool:
        """Check if this context has a parent review comment."""
        return self.in_reply_to_id is not None
