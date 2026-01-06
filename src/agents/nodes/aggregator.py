"""Aggregator node - combines, deduplicates, and limits review comments."""

from collections import Counter, defaultdict
from typing import Literal

import structlog

from ...core.config import ReviewerConfig
from ..state import GraphState, ReviewComment

log = structlog.get_logger()

type Severity = Literal["critical", "warning", "info", "suggestion"]

_SEVERITY_PRIORITY: dict[str, int] = {
    "critical": 0,
    "warning": 1,
    "info": 2,
    "suggestion": 3,
}

_SUMMARY_TEMPLATES: dict[str, str] = {
    "vi": (
        "## 🤖 AI Code Review\n\n"
        "| Mức độ | Số lượng |\n"
        "|--------|----------|\n"
        "| 🔴 Critical | {critical} |\n"
        "| 🟡 Warning | {warning} |\n"
        "| 🔵 Info | {info} |\n"
        "| 💡 Suggestion | {suggestion} |\n\n"
        "**Tổng cộng: {total} nhận xét**\n"
    ),
    "ja": (
        "## 🤖 AI Code Review\n\n"
        "| 深刻度 | 件数 |\n"
        "|--------|------|\n"
        "| 🔴 Critical | {critical} |\n"
        "| 🟡 Warning | {warning} |\n"
        "| 🔵 Info | {info} |\n"
        "| 💡 Suggestion | {suggestion} |\n\n"
        "**合計: {total} 件**\n"
    ),
    "en": (
        "## 🤖 AI Code Review\n\n"
        "| Severity | Count |\n"
        "|----------|-------|\n"
        "| 🔴 Critical | {critical} |\n"
        "| 🟡 Warning | {warning} |\n"
        "| 🔵 Info | {info} |\n"
        "| 💡 Suggestion | {suggestion} |\n\n"
        "**Total: {total} comments**\n"
    ),
}


# =============================================================================
# Comment Processing
# =============================================================================


def _deduplicate(comments: list[ReviewComment]) -> list[ReviewComment]:
    """Remove duplicates by (file, line, category) key."""
    seen: set[tuple[str, int, str]] = set()
    unique: list[ReviewComment] = []

    for c in comments:
        key = (c.file, c.line, c.category)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


def _sort_by_priority(comments: list[ReviewComment]) -> list[ReviewComment]:
    """Sort by severity (critical first), then confidence (highest first)."""
    return sorted(
        comments,
        key=lambda c: (_SEVERITY_PRIORITY.get(c.severity, 99), -c.confidence),
    )


def _limit_per_file(comments: list[ReviewComment], limit: int) -> list[ReviewComment]:
    """Keep only top N comments per file (assumes already sorted by priority)."""
    by_file: defaultdict[str, list[ReviewComment]] = defaultdict(list)

    for c in comments:
        if len(by_file[c.file]) < limit:
            by_file[c.file].append(c)

    return [c for file_comments in by_file.values() for c in file_comments]


# =============================================================================
# Summary Generation
# =============================================================================


def _generate_summary(comments: list[ReviewComment], language: str) -> str:
    """Generate a markdown summary table in the specified language."""
    counts = Counter(c.severity for c in comments)
    template = _SUMMARY_TEMPLATES.get(language, _SUMMARY_TEMPLATES["en"])

    return template.format(
        critical=counts.get("critical", 0),
        warning=counts.get("warning", 0),
        info=counts.get("info", 0),
        suggestion=counts.get("suggestion", 0),
        total=len(comments),
    )


# =============================================================================
# Main Node
# =============================================================================


async def run(state: GraphState) -> dict:
    """Aggregate comments: deduplicate, sort, limit, and generate summary."""
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    comments = state["comments"]

    log.info("aggregator.started", total=len(comments))

    # Process pipeline
    unique = _deduplicate(comments)
    sorted_comments = _sort_by_priority(unique)
    final = _limit_per_file(sorted_comments, config.get_max_comments())

    # Generate summary
    summary = _generate_summary(final, config.language)

    # Log stats
    counts = Counter(c.severity for c in final)
    log.info(
        "aggregator.completed",
        total=len(final),
        critical=counts.get("critical", 0),
        deduplicated=len(comments) - len(unique),
    )

    return {"final_comments": final, "summary": summary}
