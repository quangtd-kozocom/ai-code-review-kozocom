"""Generate file review node - creates review comments for a file."""

import structlog

from ...core.llm import get_structured_llm, invoke_with_retry
from ..models import FileReviewResult
from ..prompts.generate_review import get_generate_review_prompt
from ..state import AffectedCaller, BreakingChange, ReviewComment, ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Generate review comments for breaking changes in a file.

    Creates formatted review comments for each breaking change
    found in the current file.

    Args:
        state: Current workflow state with file_breaking_changes.

    Returns:
        State updates with file_comments.
    """
    breaking_changes = state.get("file_breaking_changes", [])
    current_file = state.get("current_file")

    if not breaking_changes or not current_file:
        return {"file_comments": []}

    log.info(
        "generate_file_review.started",
        file=current_file.file_path,
        breaking_changes=len(breaking_changes),
    )

    file_comments: list[ReviewComment] = []
    
    # Get output language from config
    config = state.get("config")
    output_language = config.output_language if config else "en"
    prompt_template = get_generate_review_prompt(output_language)

    for bc in breaking_changes:
        # Format affected callers for prompt
        callers_text = _format_affected_callers(bc.affected_callers)

        prompt = prompt_template.format(
            file_path=bc.file_path,
            entity_name=bc.entity_name,
            entity_type=bc.entity_type,
            change_type=bc.change_type,
            change_detail=bc.change_detail,
            old_definition=bc.old_definition or "(none)",
            new_definition=bc.new_definition or "(none)",
            affected_callers=callers_text,
        )

        # Call LLM
        llm = get_structured_llm(FileReviewResult)

        try:
            result: FileReviewResult = await invoke_with_retry(llm, prompt)

            for comment in result.comments:
                file_comments.append(ReviewComment(
                    file=bc.file_path,
                    line=bc.line,  # Use line from breaking change (from analyze_file)
                    severity=comment.severity,
                    message=comment.message,
                    affected_files=[
                        {"path": c.file_path, "line": c.line, "reason": c.break_reason}
                        for c in bc.affected_callers
                    ],
                    recommendation=comment.recommendation,
                ))

        except Exception as e:
            log.error(
                "generate_file_review.llm_error",
                entity=bc.entity_name,
                error=str(e),
            )
            # Create a formatted comment on error
            file_comments.append(_create_fallback_comment(bc))

    log.info(
        "generate_file_review.complete",
        file=current_file.file_path,
        comments=len(file_comments),
    )

    return {
        "file_comments": file_comments,
        "all_breaking_changes": breaking_changes,
    }


def _format_affected_callers(callers: list[AffectedCaller]) -> str:
    """Format affected callers for the prompt."""
    if not callers:
        return "(no affected callers found)"

    lines = []
    for c in callers:
        lines.append(f"- **{c.file_path}:{c.line}**")
        lines.append(f"  - Call: `{c.call_text}`")
        lines.append(f"  - Issue: {c.break_reason}")
    return "\n".join(lines)


def _create_fallback_comment(bc: BreakingChange) -> ReviewComment:
    """Create a formatted comment when LLM fails."""
    # Build affected files list
    affected_inline = ", ".join(
        f"{c.file_path}:{c.line}" for c in bc.affected_callers[:3]
    )
    if len(bc.affected_callers) > 3:
        affected_inline += f", and {len(bc.affected_callers) - 3} more"

    # Build table rows
    table_rows = "\n".join(
        f"| {c.file_path} | {c.break_reason} |"
        for c in bc.affected_callers
    )

    # Build dependencies list (entity name + related)
    deps = [bc.entity_name]
    if bc.class_name:
        deps.append(bc.class_name)

    message = f"""🚨 **Breaking Change Detected**

**Problem:** {bc.change_detail} WILL break existing callers in {affected_inline}.

**Context Used:**
🔗 Dependencies ({len(deps)} analyzed):
{chr(10).join(f'- {d}' for d in deps)}

📁 External Files ({len(bc.affected_callers)} affected):
| File | Break Reason |
|------|--------------|
{table_rows}

**Recommendation:** {bc.recommendation}"""

    return ReviewComment(
        file=bc.file_path,
        line=bc.line,
        severity=bc.severity,
        message=message,
        affected_files=[
            {"path": c.file_path, "line": c.line, "reason": c.break_reason}
            for c in bc.affected_callers
        ],
        recommendation=bc.recommendation,
    )
