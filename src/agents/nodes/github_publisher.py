"""GitHub publisher node with diff-aware comment validation."""

import re
from enum import StrEnum

import structlog

from ...app.services.github import GitHubService
from ...core.config import ReviewerConfig
from ...core.i18n import Language, get_message
from ..state import FileChange, GraphState, ReviewComment

log = structlog.get_logger()


class Severity(StrEnum):
    """Review comment severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


# Emoji mapping for severity levels
SEVERITY_EMOJI: dict[str, str] = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
    Severity.SUGGESTION: "💡",
}


def parse_diff_lines(patch: str) -> set[int]:
    """
    Parse a git diff patch to extract valid line numbers for commenting.
    
    GitHub only allows comments on lines that appear in the diff.
    This parses the @@ hunk headers to determine valid lines.
    
    Args:
        patch: Git diff patch string
        
    Returns:
        Set of valid line numbers (in the new file) that can be commented on
    """
    if not patch:
        return set()
    
    valid_lines: set[int] = set()
    current_line = 0
    
    for line in patch.split('\n'):
        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue
        
        if current_line == 0:
            continue
            
        # Lines starting with '-' are deletions (old file only)
        if line.startswith('-'):
            continue
        
        # Lines starting with '+' or ' ' are in the new file
        if line.startswith('+') or line.startswith(' ') or not line.startswith('\\'):
            valid_lines.add(current_line)
            current_line += 1
    
    return valid_lines


def build_valid_lines_map(files: list[FileChange]) -> dict[str, set[int]]:
    """
    Build a mapping of filename -> valid line numbers from file diffs.
    
    Args:
        files: List of FileChange objects with patches
        
    Returns:
        Dict mapping filename to set of valid line numbers
    """
    return {f.filename: parse_diff_lines(f.patch) for f in files}


async def run(state: GraphState) -> dict:
    """Post review to GitHub with diff validation."""
    ctx = state["context"]
    comments = state["final_comments"]
    summary = state["summary"]
    files = state.get("files", [])

    # Get language from config
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    language: Language = config.language if config.language in ("en", "vi", "ja") else "en"

    log.info("GitHub publisher started", pr=ctx.pr_number, comments=len(comments))

    if not comments:
        log.info("No comments to publish", pr=ctx.pr_number)
        return {"review_id": None}

    github = GitHubService(ctx.installation_id)
    
    # Build valid lines map from diffs
    valid_lines_map = build_valid_lines_map(files)
    
    # Filter comments to only include those with valid line numbers
    valid_comments: list[ReviewComment] = []
    skipped_comments: list[ReviewComment] = []
    
    for c in comments:
        valid_lines = valid_lines_map.get(c.file, set())
        if c.line in valid_lines:
            valid_comments.append(c)
        else:
            skipped_comments.append(c)
            log.debug(
                "Comment skipped - line not in diff",
                file=c.file,
                line=c.line,
                valid_lines_count=len(valid_lines),
            )
    
    if skipped_comments:
        log.warning(
            "Some comments skipped due to invalid line numbers",
            skipped=len(skipped_comments),
            valid=len(valid_comments),
        )

    if not valid_comments:
        log.warning("No valid comments to publish after filtering", pr=ctx.pr_number)
        # Post summary as issue comment instead
        try:
            skipped_summary = f"{summary}\n\n---\n⚠️ *{len(skipped_comments)} comments could not be posted as inline comments.*"
            comment_id = await github.create_issue_comment(
                owner=ctx.owner,
                repo=ctx.repo,
                issue_number=ctx.pr_number,
                body=skipped_summary,
            )
            log.info("Posted summary as issue comment", comment_id=comment_id)
            return {"review_id": None}
        except Exception as e:
            log.exception("Failed to post summary comment")
            return {"errors": [str(e)]}

    # Format comments for GitHub API
    review_comments = [
        {
            "path": c.file,
            "line": c.line,
            "body": format_comment(c, language),
        }
        for c in valid_comments
    ]

    # Determine review action based on severity
    has_critical = any(c.severity == Severity.CRITICAL for c in valid_comments)
    event = "REQUEST_CHANGES" if has_critical else "COMMENT"
    
    # Add note about skipped comments to summary if any
    if skipped_comments:
        summary = f"{summary}\n\n---\n⚠️ *{len(skipped_comments)} additional comments could not be posted as inline comments.*"

    try:
        review_id = await github.create_review(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            body=summary,
            comments=review_comments,
            event=event,
        )
        log.info("Review published", review_id=review_id, pr=ctx.pr_number)
        return {"review_id": review_id}

    except Exception as e:
        log.exception("Failed to publish review")
        
        # Fallback: try posting as issue comment
        try:
            log.info("Attempting fallback to issue comment")
            fallback_body = format_fallback_comment(summary, valid_comments, language)
            comment_id = await github.create_issue_comment(
                owner=ctx.owner,
                repo=ctx.repo,
                issue_number=ctx.pr_number,
                body=fallback_body,
            )
            log.info("Fallback comment posted", comment_id=comment_id)
            return {"review_id": None, "errors": [f"Review failed, posted as comment: {str(e)}"]}
        except Exception as fallback_error:
            log.exception("Fallback also failed")
            return {"errors": [str(e), str(fallback_error)]}


def format_comment(comment: ReviewComment, language: Language = "en") -> str:
    """
    Format a ReviewComment for GitHub.

    Args:
        comment: The review comment to format
        language: Language code for localized text

    Returns:
        Formatted markdown string
    """
    emoji = SEVERITY_EMOJI.get(comment.severity, "•")
    severity_upper = comment.severity.upper()

    # Build comment body
    parts = [
        f"{emoji} **{severity_upper}** ({comment.category})",
        "",
        comment.message,
    ]

    # Add suggestion if present (localized)
    if comment.suggestion:
        suggestion_prefix = get_message("suggestion_prefix", language)
        parts.extend(["", f"{suggestion_prefix} {comment.suggestion}"])

    return "\n".join(parts)


def format_fallback_comment(
    summary: str,
    comments: list[ReviewComment],
    language: Language = "en",
) -> str:
    """
    Format comments as a single issue comment (fallback when review fails).
    
    Args:
        summary: Review summary
        comments: List of review comments
        language: Language code
        
    Returns:
        Formatted markdown string
    """
    parts = [summary, "", "---", "", "## Inline Comments", ""]
    
    for c in comments:
        emoji = SEVERITY_EMOJI.get(c.severity, "•")
        parts.append(f"### {emoji} `{c.file}:{c.line}`")
        parts.append("")
        parts.append(f"**{c.severity.upper()}** ({c.category})")
        parts.append("")
        parts.append(c.message)
        if c.suggestion:
            suggestion_prefix = get_message("suggestion_prefix", language)
            parts.append("")
            parts.append(f"{suggestion_prefix} {c.suggestion}")
        parts.append("")
        parts.append("---")
        parts.append("")
    
    return "\n".join(parts)
