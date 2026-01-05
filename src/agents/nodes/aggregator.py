"""Aggregator node - combines and sorts comments.

Uses repository configuration for:
- max_comments_per_file limits
- language-aware summary generation
"""

import structlog

from ...core.config import ReviewerConfig
from ..state import GraphState, ReviewComment

log = structlog.get_logger()

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}


async def run(state: GraphState) -> dict:
    """Aggregate, deduplicate, and limit comments with config-aware limits."""
    # Get config (with defaults fallback)
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    max_per_file = config.get_max_comments()

    comments = state["comments"]
    log.info("Aggregator started", total_comments=len(comments))

    # Deduplicate by (file, line, category)
    seen: set[tuple[str, int, str]] = set()
    unique: list[ReviewComment] = []
    for c in comments:
        key = (c.file, c.line, c.category)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Sort by severity, then confidence
    unique.sort(key=lambda c: (SEVERITY_ORDER.get(c.severity, 99), -c.confidence))

    # Limit per file
    by_file: dict[str, list[ReviewComment]] = {}
    for c in unique:
        if c.file not in by_file:
            by_file[c.file] = []
        if len(by_file[c.file]) < max_per_file:
            by_file[c.file].append(c)

    final: list[ReviewComment] = []
    for file_comments in by_file.values():
        final.extend(file_comments)

    # Generate summary in configured language
    summary = _generate_summary(final, config.language)

    log.info(
        "Aggregation complete",
        total=len(final),
        critical=sum(1 for c in final if c.severity == "critical"),
    )
    return {"final_comments": final, "summary": summary}


def _generate_summary(comments: list[ReviewComment], language: str) -> str:
    """Generate summary in configured language."""
    by_severity: dict[str, int] = {}
    for c in comments:
        by_severity.setdefault(c.severity, 0)
        by_severity[c.severity] += 1

    critical = by_severity.get("critical", 0)
    warning = by_severity.get("warning", 0)
    info = by_severity.get("info", 0)
    suggestion = by_severity.get("suggestion", 0)

    if language == "vi":
        return f"""## 🤖 AI Code Review

| Mức độ | Số lượng |
|--------|----------|
| 🔴 Critical | {critical} |
| 🟡 Warning | {warning} |
| 🔵 Info | {info} |
| 💡 Suggestion | {suggestion} |

**Tổng cộng: {len(comments)} nhận xét**
"""

    if language == "ja":
        return f"""## 🤖 AI Code Review

| 深刻度 | 件数 |
|--------|------|
| 🔴 Critical | {critical} |
| 🟡 Warning | {warning} |
| 🔵 Info | {info} |
| 💡 Suggestion | {suggestion} |

**合計: {len(comments)} 件**
"""

    # Default: English
    return f"""## 🤖 AI Code Review

| Severity | Count |
|----------|-------|
| 🔴 Critical | {critical} |
| 🟡 Warning | {warning} |
| 🔵 Info | {info} |
| 💡 Suggestion | {suggestion} |

**Total: {len(comments)} comments**
"""
