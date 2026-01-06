"""Comment formatting for GitHub publisher."""

from ....core.i18n import Language, get_message
from ...state import ReviewComment

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
    "suggestion": "💡",
}


class CommentFormatter:
    """Formats review comments for GitHub display."""

    def __init__(self, language: Language):
        self._language = language

    def _get_emoji(self, severity: str) -> str:
        return SEVERITY_EMOJI.get(severity, "•")

    def format_inline(self, comment: ReviewComment) -> str:
        """Format a single comment for GitHub inline review."""
        emoji = self._get_emoji(comment.severity)
        lines = [
            f"{emoji} **{comment.severity.upper()}** ({comment.category})",
            "",
            comment.message,
        ]

        if comment.suggestion:
            prefix = get_message("suggestion_prefix", self._language)
            lines.extend(["", f"{prefix} {comment.suggestion}"])

        return "\n".join(lines)

    def format_fallback(self, comment: ReviewComment) -> str:
        """Format a single comment for fallback (non-inline) display."""
        emoji = self._get_emoji(comment.severity)
        lines = [
            f"### {emoji} `{comment.file}:{comment.line}`",
            "",
            f"**{comment.severity.upper()}** ({comment.category})",
            "",
            comment.message,
        ]

        if comment.suggestion:
            prefix = get_message("suggestion_prefix", self._language)
            lines.extend(["", f"{prefix} {comment.suggestion}"])

        lines.extend(["", "---", ""])
        return "\n".join(lines)

    def format_fallback_body(
        self,
        summary: str,
        comments: list[ReviewComment],
    ) -> str:
        """Format all comments as a single issue comment (fallback mode)."""
        parts = [summary, "", "---", "", "## Inline Comments", ""]
        parts.extend(self.format_fallback(c) for c in comments)
        return "\n".join(parts)

    @staticmethod
    def build_skipped_note(skipped_count: int) -> str:
        """Build a note about skipped comments."""
        return f"⚠️ *{skipped_count} additional comments could not be posted as inline comments.*"
