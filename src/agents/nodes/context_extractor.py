import fnmatch
import os

import structlog

from ...app.services.github import GitHubService
from ..state import FileChange, GraphState

log = structlog.get_logger()

IGNORE_PATTERNS = (
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "*.min.js",
    "*.min.css",
    "*.map",
    "node_modules/*",
    "vendor/*",
    "dist/*",
    ".git/*",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
)

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".vue": "vue",
    ".svelte": "svelte",
}


async def run(state: GraphState) -> dict:
    """Fetch PR files and extract relevant changes."""
    ctx = state["context"]
    github = GitHubService(ctx.installation_id)

    raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    files = []
    for f in raw_files:
        if _should_ignore(f["filename"]):
            log.debug("Ignoring file", filename=f["filename"])
            continue

        files.append(
            FileChange(
                filename=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch", ""),
                language=_detect_language(f["filename"]),
            )
        )

    log.info("Extracted files", count=len(files), pr=ctx.pr_number)
    return {"files": files}


def _should_ignore(filename: str) -> bool:
    """Check if file should be ignored based on patterns."""
    return any(fnmatch.fnmatch(filename, p) for p in IGNORE_PATTERNS)


def _detect_language(filename: str) -> str | None:
    """Detect programming language from file extension."""
    _, ext = os.path.splitext(filename)
    return LANGUAGE_MAP.get(ext.lower())
