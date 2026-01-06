"""Response templates for command handlers.

This module provides language-aware response templates using the i18n system.
For backward compatibility, it also exports the original template constants
which now delegate to the i18n system with English as default.
"""

from functools import partial

from ..core.i18n import Language, get_message

# Re-export for backward compatibility (defaults to English)
FIX_SUCCESS = get_message("fix_success", "en")
EXPLAIN_SUCCESS = get_message("explain_success", "en")
TESTS_SUCCESS = get_message("tests_success", "en")
HELP_MESSAGE = get_message("help_message", "en")
ERROR_NO_PARENT_COMMENT = get_message("error_no_parent_comment", "en")
ERROR_CANNOT_FETCH_COMMENT = get_message("error_cannot_fetch_comment", "en")
ERROR_CANNOT_READ_FILE = get_message("error_cannot_read_file", "en")
ERROR_CANNOT_GENERATE_FIX = get_message("error_cannot_generate_fix", "en")
ERROR_NO_FILES_FOUND = get_message("error_no_files_found", "en")
ERROR_NO_MATCHING_FILES = get_message("error_no_matching_files", "en")
ERROR_UNKNOWN_COMMAND = get_message("error_unknown_command", "en")


def _get_localized(key: str, language: Language = "en", **kwargs: str) -> str:
    """Get localized message by key."""
    return get_message(key, language, **kwargs)


# Create specific getters using partial
get_fix_success = partial(_get_localized, "fix_success")
get_explain_success = partial(_get_localized, "explain_success")
get_tests_success = partial(_get_localized, "tests_success")
get_help_message = partial(_get_localized, "help_message")
get_error_no_parent_comment = partial(_get_localized, "error_no_parent_comment")
get_error_cannot_fetch_comment = partial(_get_localized, "error_cannot_fetch_comment")
get_error_cannot_read_file = partial(_get_localized, "error_cannot_read_file")
get_error_cannot_generate_fix = partial(_get_localized, "error_cannot_generate_fix")
get_error_no_files_found = partial(_get_localized, "error_no_files_found")
get_error_no_matching_files = partial(_get_localized, "error_no_matching_files")
get_error_unknown_command = partial(_get_localized, "error_unknown_command")
