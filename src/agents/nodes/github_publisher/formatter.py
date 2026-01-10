"""Comment formatting for GitHub publisher - CodeRabbit-inspired style."""

from ....core.i18n import Language
from ...state import PRContext, ReviewComment

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

    def __init__(self, language: Language, ctx: PRContext | None = None):
        self._language = language
        self._ctx = ctx

    def _get_severity_config(self, severity: str) -> dict:
        return SEVERITY_CONFIG.get(severity, {"emoji": "•", "label": severity, "icon": "•"})

    def _get_category_icon(self, category: str) -> str:
        return CATEGORY_ICONS.get(category.lower(), "📝")
    
    def _github_link(self, file: str, line: int | None = None) -> str:
        """Generate clickable GitHub link to file/line."""
        if not self._ctx:
            return f"`{file}{'#L' + str(line) if line else ''}`"
        
        base = f"https://github.com/{self._ctx.owner}/{self._ctx.repo}/blob/{self._ctx.head_branch}/{file}"
        if line:
            base += f"#L{line}"
        return base

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

        # NEW: Show impact context (callers, dependencies, external files)
        if comment.caller_refs or comment.dependency_refs or comment.affected_files:
            lines.extend(["", "**Context Used:**", ""])
        
        # Show callers that will break (collapsible)
        if comment.caller_refs:
            lines.extend([
                "<details>",
                f"<summary>📞 <b>Callers ({len(comment.caller_refs)} will break)</b></summary>",
                "",
                "| File | Line | Break Reason |",
                "|------|------|--------------|",
            ])
            for caller in comment.caller_refs:
                file_link = f"[`{caller.file}`]({self._github_link(caller.file, caller.line)})"
                reason = caller.break_reason or "Incompatible change"
                lines.append(f"| {file_link} | {caller.line} | {reason} |")
            lines.extend(["", "</details>", ""])
        
        # Show dependencies analyzed (collapsible)
        if comment.dependency_refs:
            lines.extend([
                "<details>",
                f"<summary>🔗 <b>Dependencies ({len(comment.dependency_refs)} analyzed)</b></summary>",
                "",
            ])
            for dep in comment.dependency_refs:
                if dep.break_reason:
                    lines.append(f"- `{dep.name}` - {dep.break_reason}")
                else:
                    lines.append(f"- `{dep.name}`")
            lines.extend(["", "</details>", ""])
        
        # Show external files affected (collapsible)
        if comment.affected_files:
            lines.extend([
                "<details>",
                f"<summary>📁 <b>External Files ({len(comment.affected_files)} affected)</b></summary>",
                "",
                "| File | Break Reason |",
                "|------|--------------|",
            ])
            for ext in comment.affected_files:
                file_link = f"[`{ext.path}`]({self._github_link(ext.path, ext.line)})"
                lines.append(f"| {file_link} | {ext.break_reason} |")
            lines.extend(["", "</details>", ""])

        # Show dependencies analyzed (old format - keep for backward compat)
        if comment.dependencies_analyzed:
            lines.extend([
                "",
                "<details>",
                "<summary>🔍 <b>Dependencies Analyzed</b></summary>",
                "",
            ])
            for dep in comment.dependencies_analyzed:
                status = "✅" if dep.behavior_verified else "❓"
                lines.append(f"- {status} `{dep.name}`")
                if dep.file:
                    lines.append(f"  - File: `{dep.file}`")
                if dep.validation_provided:
                    lines.append("  - Has input validation")
                if dep.summary:
                    lines.append(f"  - {dep.summary}")
            lines.extend(["", "</details>"])

        # Show RAG context sources if available
        if comment.related_context:
            lines.extend([
                "",
                "<details>",
                "<summary>📚 <b>Context Used</b></summary>",
                "",
            ])
            for ref in comment.related_context[:3]:
                lines.append(f"- `{ref}`")
            lines.extend(["", "</details>"])

        # Show grouped issues indicator
        if comment.issue_group and comment.related_issues:
            lines.extend([
                "",
                f"*This comment consolidates {len(comment.related_issues)} related {comment.issue_group.replace('_', ' ')} issues.*",
            ])

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

