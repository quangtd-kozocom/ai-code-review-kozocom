import structlog

from ..state import GraphState, ReviewComment

log = structlog.get_logger()

MAX_PER_FILE = 10
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}


async def run(state: GraphState) -> dict:
    """Aggregate, deduplicate, and limit comments."""
    comments = state["comments"]
    log.info("Aggregator started", total_comments=len(comments))

    # Deduplicate by (file, line, category)
    seen = set()
    unique = []
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
        by_file.setdefault(c.file, []).append(c)

    final = []
    for file_comments in by_file.values():
        final.extend(file_comments[:MAX_PER_FILE])

    # Generate summary
    critical = sum(1 for c in final if c.severity == "critical")
    warning = sum(1 for c in final if c.severity == "warning")

    summary = f"""## 🤖 AI Code Review

| Severity | Count |
|----------|-------|
| 🔴 Critical | {critical} |
| 🟡 Warning | {warning} |
| 🔵 Info/Suggestion | {len(final) - critical - warning} |

**Total: {len(final)} comments**
"""

    log.info("Aggregation complete", total=len(final), critical=critical)
    return {"final_comments": final, "summary": summary}
