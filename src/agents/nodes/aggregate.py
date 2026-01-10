"""Aggregator node - combines and deduplicates review comments.

Final processing step before publishing to GitHub.
"""

from collections import Counter, defaultdict
from difflib import SequenceMatcher

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

# Issue type patterns for semantic grouping
_ISSUE_TYPE_PATTERNS: dict[str, list[str]] = {
    "input_validation": [
        "input", "validate", "sanitize", "check", "parameter", "argument",
        "None", "null", "empty", "missing",
    ],
    "error_handling": [
        "exception", "error", "try", "catch", "except", "finally",
        "raise", "throw", "handle",
    ],
    "resource_management": [
        "close", "cleanup", "dispose", "leak", "file", "connection",
        "resource", "open", "release",
    ],
    "null_safety": [
        "None", "null", "undefined", "optional", "NoneType",
        "AttributeError", "TypeError",
    ],
    "bounds_checking": [
        "index", "bounds", "range", "array", "list", "length",
        "out of", "overflow", "underflow",
    ],
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


def _classify_issue_type(message: str) -> str:
    """Classify a comment into an issue type for grouping."""
    message_lower = message.lower()

    scores: dict[str, int] = defaultdict(int)
    for issue_type, patterns in _ISSUE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in message_lower:
                scores[issue_type] += 1

    if scores:
        return max(scores, key=scores.get)
    return "other"


def _filter_by_severity(
    comments: list[ReviewComment],
) -> list[ReviewComment]:
    """Filter to only keep critical and warning severity comments."""
    allowed_severities = {"critical", "warning"}
    return [c for c in comments if c.severity in allowed_severities]


def _group_related_issues(
    comments: list[ReviewComment],
) -> list[ReviewComment]:
    """Group semantically related issues into single comments.

    Strategy:
    1. Classify each comment by issue type
    2. Within same file+issue_type, consider merging
    3. Create consolidated comments with bullet points
    """
    if not comments:
        return []

    # Group by (file, issue_type)
    grouped: dict[tuple[str, str], list[ReviewComment]] = defaultdict(list)

    for comment in comments:
        issue_type = _classify_issue_type(comment.message)
        key = (comment.file, issue_type)
        grouped[key].append(comment)

    result: list[ReviewComment] = []

    for (file, issue_type), group in grouped.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        # Merge small groups (up to 5 related issues)
        if len(group) <= 5:
            merged = _merge_comments(group, issue_type)
            result.append(merged)
        else:
            # Keep top by confidence
            sorted_group = sorted(group, key=lambda c: c.confidence, reverse=True)
            result.extend(sorted_group[:3])

    return result


def _merge_comments(
    comments: list[ReviewComment],
    issue_type: str,
) -> ReviewComment:
    """Merge multiple comments into a single consolidated comment."""
    # Take highest severity
    severity_order = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}
    comments_sorted = sorted(
        comments, key=lambda c: severity_order.get(c.severity, 99)
    )
    primary = comments_sorted[0]

    # Build consolidated message
    lines = [
        f"**Multiple {issue_type.replace('_', ' ').title()} Issues Found:**",
        "",
    ]

    for i, c in enumerate(comments, 1):
        lines.append(f"{i}. Line {c.line}: {c.message}")
        if c.suggestion:
            lines.append(f"   - Fix: {c.suggestion}")

    # Merge suggestions
    suggestions = [c.suggestion for c in comments if c.suggestion]
    merged_suggestion = "; ".join(suggestions[:3]) if suggestions else None

    # Merge dependencies analyzed
    all_deps = []
    for c in comments:
        all_deps.extend(c.dependencies_analyzed)

    # Average confidence
    avg_confidence = sum(c.confidence for c in comments) / len(comments)

    return ReviewComment(
        file=primary.file,
        line=primary.line,  # Use first issue's line
        severity=primary.severity,
        category=primary.category,
        message="\n".join(lines),
        suggestion=merged_suggestion,
        confidence=avg_confidence,
        agent=primary.agent,
        dependencies_analyzed=all_deps,
        issue_group=issue_type,
        related_issues=[str(hash(c.message)) for c in comments],
    )


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
    - Filter by severity (only critical + warning)
    - Deduplicate comments
    - Group semantically related issues
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

    # Step 1: Filter by severity (only critical and warning)
    comments = _filter_by_severity(comments)
    log.info(
        "aggregator.after_severity_filter",
        count=len(comments),
    )

    # Step 2: Deduplicate by (file, line, category)
    comments = _deduplicate(comments)

    # Step 3: Group semantically related issues
    comments = _group_related_issues(comments)
    log.info(
        "aggregator.after_grouping",
        count=len(comments),
    )

    # Step 4: Sort by priority
    comments = _sort_by_priority(comments)

    # Step 5: Apply per-file limit
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
