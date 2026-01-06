"""Response templates for command handlers.

This module provides language-aware response templates using the i18n system.
For backward compatibility, it also exports the original template constants
which now delegate to the i18n system with English as default.
"""

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


def get_fix_success(language: Language = "en", **kwargs: str) -> str:
    """Get localized fix success message."""
    return get_message("fix_success", language, **kwargs)


def get_explain_success(language: Language = "en", **kwargs: str) -> str:
    """Get localized explain success message."""
    return get_message("explain_success", language, **kwargs)


def get_tests_success(language: Language = "en", **kwargs: str) -> str:
    """Get localized tests success message."""
    return get_message("tests_success", language, **kwargs)


def get_help_message(language: Language = "en") -> str:
    """Get localized help message."""
    return get_message("help_message", language)


def get_error_no_parent_comment(language: Language = "en") -> str:
    """Get localized error message for missing parent comment."""
    return get_message("error_no_parent_comment", language)


def get_error_cannot_fetch_comment(language: Language = "en") -> str:
    """Get localized error message for fetch failure."""
    return get_message("error_cannot_fetch_comment", language)


def get_error_cannot_read_file(language: Language = "en") -> str:
    """Get localized error message for file read failure."""
    return get_message("error_cannot_read_file", language)


def get_error_cannot_generate_fix(language: Language = "en") -> str:
    """Get localized error message for fix generation failure."""
    return get_message("error_cannot_generate_fix", language)


def get_error_no_files_found(language: Language = "en") -> str:
    """Get localized error message for no files found."""
    return get_message("error_no_files_found", language)


def get_error_no_matching_files(language: Language = "en", **kwargs: str) -> str:
    """Get localized error message for no matching files."""
    return get_message("error_no_matching_files", language, **kwargs)


def get_error_unknown_command(language: Language = "en") -> str:
    """Get localized error message for unknown command."""
    return get_message("error_unknown_command", language)
