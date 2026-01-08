"""Comment formatting for GitHub publisher - CodeRabbit-inspired style."""

from ....core.i18n import Language
from ...state import ReviewComment

SEVERITY_CONFIG = {
    "critical": {"emoji": "🔴", "label": "Critical", "icon": "🚨"},
    "warning": {"emoji": "🟡", "label": "Warning", "icon": "⚠️"},
    "info": {"emoji": "🔵", "label": "Info", "icon": "ℹ️"},
    "suggestion": {"emoji": "💡", "label": "Suggestion", "icon": "💡"},
}

CATEGORY_ICONS = {
    "security": "🔐",
    "logic": "🧠",
    "style": "🎨",
}


class CommentFormatter:
    """Formats review comments for GitHub display - CodeRabbit style."""

    def __init__(self, language: Language):
        self._language = language

    def _get_severity_config(self, severity: str) -> dict:
        return SEVERITY_CONFIG.get(severity, {"emoji": "•", "label": severity, "icon": "•"})

    def _get_category_icon(self, category: str) -> str:
        return CATEGORY_ICONS.get(category.lower(), "📝")

    def format_inline(self, comment: ReviewComment) -> str:
        """Format a single comment for GitHub inline review - CodeRabbit style."""
        config = self._get_severity_config(comment.severity)
        cat_icon = self._get_category_icon(comment.category)

        lines = [
            f"{cat_icon} **{config['label']}**: {comment.category.title()}",
            "",
            "**Problem:**",
            comment.message,
        ]

        # Show RAG context sources if available
        if comment.related_files:
            lines.extend([
                "",
                "<details>",
                "<summary>📚 <b>Context Used</b></summary>",
                "",
            ])
            for ref in comment.related_files[:3]:
                lines.append(f"- `{ref}`")
            lines.extend(["", "</details>"])

        # Recommendation
        if comment.suggestion:
            lines.extend([
                "",
                "**Recommendation:**",
                comment.suggestion,
            ])

        # Code suggestion if available
        if comment.code_suggestion:
            lines.extend([
                "",
                "**Suggested Fix:**",
                "```python",
                comment.code_suggestion,
                "```",
            ])

        # Footer with confidence
        confidence_pct = int(comment.confidence * 100) if comment.confidence else 80
        lines.extend([
            "",
            "---",
            f"*🤖 {comment.agent.title()} Agent • Confidence: {confidence_pct}%*",
        ])

        return "\n".join(lines)

    def format_fallback(self, comment: ReviewComment) -> str:
        """Format a single comment for fallback (non-inline) display."""
        config = self._get_severity_config(comment.severity)
        cat_icon = self._get_category_icon(comment.category)

        lines = [
            f"### {config['emoji']} `{comment.file}:{comment.line}`",
            "",
            f"{cat_icon} **{config['label']}** — {comment.category.title()}",
            "",
            "**Problem:**",
            comment.message,
        ]

        # Show RAG context sources
        if comment.related_files:
            lines.extend(["", "**Context Used:**"])
            for ref in comment.related_files[:3]:
                lines.append(f"- `{ref}`")

        if comment.suggestion:
            lines.extend([
                "",
                "**Recommendation:**",
                comment.suggestion,
            ])

        if comment.code_suggestion:
            lines.extend([
                "",
                "**Suggested Fix:**",
                "```python",
                comment.code_suggestion,
                "```",
            ])

        confidence_pct = int(comment.confidence * 100) if comment.confidence else 80
        lines.extend([
            "",
            f"*🤖 {comment.agent.title()} Agent • Confidence: {confidence_pct}%*",
            "",
            "---",
        ])

        return "\n".join(lines)

    def format_fallback_body(
        self,
        summary: str,
        comments: list[ReviewComment],
    ) -> str:
        """Format all comments as a single issue comment (fallback mode)."""
        parts = [summary, "", "---", "", "## 📝 Detailed Findings", ""]
        parts.extend(self.format_fallback(c) for c in comments)
        return "\n".join(parts)

    @staticmethod
    def build_skipped_note(skipped_count: int) -> str:
        """Build a note about skipped comments."""
        return (
            f"⚠️ *{skipped_count} additional findings could not be posted "
            f"as inline comments (outside diff context).*"
        )

