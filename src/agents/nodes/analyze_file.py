"""Analyze file node - LLM detects breaking changes in a file."""

import structlog

from ...core.llm import get_structured_llm, invoke_with_retry
from ..constants import FILE_ADDED, FILE_DELETED
from ..models import FileAnalysisResult
from ..prompts.analyze_file import get_analyze_file_prompt
from ..state import DetectedChange, ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Analyze a file for breaking changes using LLM.

    The LLM examines the diff and identifies changes that could
    break existing callers in the codebase.

    Args:
        state: Current workflow state with current_file.

    Returns:
        State updates with file_changes.
    """
    current_file = state.get("current_file")

    if not current_file:
        log.debug("analyze_file.skipped", reason="no current_file")
        return {"file_changes": []}

    # Skip deleted files (nothing to analyze for callers)
    if current_file.status == FILE_DELETED:
        log.info(
            "analyze_file.skipped",
            file=current_file.file_path,
            reason="file deleted",
        )
        return {"file_changes": []}

    # Skip new files (no old code to compare)
    if current_file.status == FILE_ADDED:
        log.info(
            "analyze_file.skipped",
            file=current_file.file_path,
            reason="new file (no breaking changes possible)",
        )
        return {"file_changes": []}

    log.info(
        "analyze_file.started",
        file=current_file.file_path,
        status=current_file.status,
        language=current_file.language,
    )

    # Get output language from config
    config = state.get("config")
    output_lang = config.output_language if config else "en"

    # Prepare prompt
    prompt_template = get_analyze_file_prompt(output_lang)
    prompt = prompt_template.format(
        file_path=current_file.file_path,
        language=current_file.language or "unknown",
        status=current_file.status,
        old_content=current_file.base_content or "(empty)",
        new_content=current_file.head_content or "(empty)",
        patch=current_file.patch or "(no diff)",
    )

    # Call LLM with structured output
    llm = get_structured_llm(FileAnalysisResult)

    try:
        result: FileAnalysisResult = await invoke_with_retry(llm, prompt)
        log.debug(
            "analyze_file.llm_response",
            file=current_file.file_path,
            total_changes=len(result.changes),
            summary=result.summary,
        )
    except Exception as e:
        log.error(
            "analyze_file.llm_error",
            file=current_file.file_path,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {"file_changes": []}

    # Filter to only breaking changes
    breaking_changes = [c for c in result.changes if c.could_break_callers]

    # Convert to DetectedChange
    file_changes = [
        DetectedChange(
            entity_type=c.entity_type,
            entity_name=c.entity_name,
            class_name=c.class_name,
            file_path=current_file.file_path,
            language=current_file.language or "unknown",
            change_type=c.change_type,
            old_definition=c.old_definition,
            new_definition=c.new_definition,
            change_detail=c.change_detail,
            line=c.line,
        )
        for c in breaking_changes
    ]

    log.info(
        "analyze_file.complete",
        file=current_file.file_path,
        total_changes=len(result.changes),
        breaking_changes=len(file_changes),
        entities=[c.entity_name for c in file_changes],
    )

    return {
        "file_changes": file_changes,
        "current_change_index": 0,
        "current_change": file_changes[0] if file_changes else None,
    }
