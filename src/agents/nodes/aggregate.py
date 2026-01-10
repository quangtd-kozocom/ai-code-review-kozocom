"""Aggregator node - combines and deduplicates review comments.

Final processing step before publishing to GitHub.
"""

from collections import Counter, defaultdict

import structlog

from ...core.config import ReviewerConfig
from ...core.i18n import Language
from ..state import ReviewComment, ReviewState

log = structlog.get_logger()

type Severity = str

_SEVERITY_PRIORITY: dict[str, int] = {
    "critical": 0,
    "warning": 1,
    "info": 2,
    "suggestion": 3,
}

_SUMMARY_TEMPLATES: dict[Language, str] = {
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


def _deduplicate(comments: list[ReviewComment]) -> list[ReviewComment]:
    """Remove duplicate comments by (file, line, category) key."""
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


def _limit_per_file(
    comments: list[ReviewComment],
    limit: int,
) -> list[ReviewComment]:
    """Keep only top N comments per file."""
    by_file: defaultdict[str, list[ReviewComment]] = defaultdict(list)
    
    for c in comments:
        if len(by_file[c.file]) < limit:
            by_file[c.file].append(c)
    
    return [c for file_comments in by_file.values() for c in file_comments]


def _generate_summary(comments: list[ReviewComment], language: Language) -> str:
    """Generate markdown summary in specified language."""
    counts = Counter(c.severity for c in comments)
    
    template = _SUMMARY_TEMPLATES.get(language, _SUMMARY_TEMPLATES["en"])
    
    return template.format(
        critical=counts.get("critical", 0),
        warning=counts.get("warning", 0),
        info=counts.get("info", 0),
        suggestion=counts.get("suggestion", 0),
        total=len(comments),
    )


async def run(state: ReviewState) -> dict:
    """Aggregate and finalize review comments.
    
    Final processing:
    - Deduplicate comments
    - Sort by priority
    - Apply limits
    - Generate summary
    
    Args:
        state: Current workflow state with comments.
        
    Returns:
        State update with final_comments and summary.
    """
    comments = state.get("comments", [])
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    
    log.info(
        "aggregator.started",
        raw_count=len(comments),
    )
    
    if not comments:
        return {
            "final_comments": [],
            "summary": "## 🤖 AI Code Review\n\n✅ No issues found!",
        }
    
    # Process comments
    comments = _deduplicate(comments)
    comments = _sort_by_priority(comments)
    
    # Apply limit from config
    max_per_file = getattr(config, "max_comments_per_file", 10)
    comments = _limit_per_file(comments, max_per_file)
    
    # Get language from config
    language: Language = getattr(config, "language", "en")
    if language not in ("en", "vi", "ja"):
        language = "en"
    
    # Generate summary
    summary = _generate_summary(comments, language)
    
    log.info(
        "aggregator.complete",
        final_count=len(comments),
        critical=sum(1 for c in comments if c.severity == "critical"),
        warning=sum(1 for c in comments if c.severity == "warning"),
    )
    
    return {
        "final_comments": comments,
        "summary": summary,
    }
