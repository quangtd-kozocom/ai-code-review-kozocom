"""Diff analysis utilities for GitHub publisher."""

import re

from ...state import FileChange, ReviewComment
from .models import FilterResult


class DiffAnalyzer:
    """Analyzes git diffs to determine valid comment lines."""

    _HUNK_PATTERN = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    @classmethod
    def get_valid_lines(cls, patch: str) -> set[int]:
        """
        Extract line numbers from a git diff that are valid for commenting.

        GitHub only allows comments on lines that appear in the diff.
        This parses @@ hunk headers and tracks line numbers in the new file.
        """
        if not patch:
            return set()

        valid_lines: set[int] = set()
        current_line = 0

        for line in patch.split("\n"):
            if match := cls._HUNK_PATTERN.match(line):
                current_line = int(match.group(1))
                continue

            if current_line == 0:
                continue

            # Deleted lines don't exist in new file
            if line.startswith("-"):
                continue

            # Skip "\ No newline at end of file" markers
            if not line.startswith("\\"):
                valid_lines.add(current_line)
                current_line += 1

        return valid_lines

    @classmethod
    def filter_comments(
        cls,
        comments: list[ReviewComment],
        files: list[FileChange],
    ) -> FilterResult:
        """Filter comments to only those on lines present in the diff."""
        valid_lines_map = {f.filename: cls.get_valid_lines(f.patch) for f in files}

        valid: list[ReviewComment] = []
        skipped: list[ReviewComment] = []

        for comment in comments:
            file_valid_lines = valid_lines_map.get(comment.file, set())
            if comment.line in file_valid_lines:
                valid.append(comment)
            else:
                skipped.append(comment)

        return FilterResult(valid=valid, skipped=skipped)
