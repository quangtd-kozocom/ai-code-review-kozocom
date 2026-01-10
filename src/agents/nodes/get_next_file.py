"""Get next file node - manages file processing loop."""

import structlog

from ..state import ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Get the next file to process from pending files.

    Manages the file processing loop by popping files from
    pending_files and setting current_file.

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_file and reset per-file state.
    """
    pending = state.get("pending_files", [])
    processed = len(state.get("file_diffs", [])) - len(pending)

    if not pending:
        log.info(
            "get_next_file.complete",
            total_processed=processed,
            message="All files processed",
        )
        return {
            "current_file": None,
            "file_changes": [],
            "file_breaking_changes": [],
            "file_comments": [],
        }

    # Pop first file
    current_file = pending[0]
    remaining = pending[1:]

    log.info(
        "get_next_file.processing",
        file=current_file.file_path,
        status=current_file.status,
        language=current_file.language,
        processed=processed,
        remaining=len(remaining),
    )

    return {
        "pending_files": remaining,
        "current_file": current_file,
        # Reset per-file state
        "file_changes": [],
        "current_change_index": 0,
        "current_change": None,
        "file_breaking_changes": [],
        "file_comments": [],
        "search_iteration": 0,
    }
