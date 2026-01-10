"""Execute search node - runs ripgrep on cloned repo.

Requires ripgrep (rg) to be installed:
- macOS: brew install ripgrep
- Ubuntu: apt install ripgrep
- Windows: choco install ripgrep
"""

import asyncio
import json
import re

import structlog

from ..constants import MAX_RESULTS_PER_QUERY, SEARCH_CONTEXT_LINES, SEARCH_EXCLUDE_DIRS
from ..state import ReviewState, SearchResult

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Execute search queries using ripgrep on local repo.

    Uses ripgrep for fast, regex-based search with no rate limits.

    Args:
        state: Current workflow state with search_plan and repo_path.

    Returns:
        State updates with search_results.
    """
    search_plan = state.get("search_plan")
    repo_path = state.get("repo_path")
    current_change = state.get("current_change")

    if not search_plan or not repo_path:
        log.debug(
            "execute_search.skipped",
            has_search_plan=bool(search_plan),
            has_repo_path=bool(repo_path),
        )
        return {"search_results": []}

    log.info(
        "execute_search.started",
        queries=search_plan.queries,
        include_patterns=search_plan.include_patterns,
        exclude_patterns=search_plan.exclude_patterns,
        repo_path=repo_path,
    )

    all_results: list[SearchResult] = []
    seen_locations: set[tuple[str, int]] = set()

    for query in search_plan.queries:
        log.debug("execute_search.query", query=query)

        results = await _run_ripgrep(
            repo_path=repo_path,
            query=query,
            include_patterns=search_plan.include_patterns,
            exclude_patterns=search_plan.exclude_patterns,
            exclude_file=current_change.file_path if current_change else None,
        )

        log.debug(
            "execute_search.query_results",
            query=query,
            results_count=len(results),
        )

        for result in results:
            # Deduplicate by file:line
            key = (result.file_path, result.line)
            if key not in seen_locations:
                seen_locations.add(key)
                all_results.append(result)

    # Limit total results
    max_total = MAX_RESULTS_PER_QUERY * len(search_plan.queries)
    if len(all_results) > max_total:
        log.warning(
            "execute_search.truncated",
            total=len(all_results),
            limit=max_total,
        )
        all_results = all_results[:max_total]

    log.info(
        "execute_search.complete",
        results_count=len(all_results),
        unique_files=len({r.file_path for r in all_results}),
    )

    return {"search_results": all_results}


async def _run_ripgrep(
    repo_path: str,
    query: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
    exclude_file: str | None = None,
) -> list[SearchResult]:
    """Run ripgrep with given parameters."""
    # Unescape LLM output then re-escape for ripgrep regex
    clean = re.sub(r"\\(.)", r"\1", query)
    escaped = re.escape(clean)

    cmd = [
        "rg",
        "--json",
        "--line-number",
        f"--context={SEARCH_CONTEXT_LINES}",
        "--max-count", str(MAX_RESULTS_PER_QUERY),
    ]

    # Add include patterns
    for pat in include_patterns:
        cmd.extend(["--glob", pat])

    # Add exclude patterns
    for pat in exclude_patterns:
        cmd.extend(["--glob", f"!{pat}"])

    # Always exclude common noise directories
    for noise in SEARCH_EXCLUDE_DIRS:
        cmd.extend(["--glob", f"!{noise}"])

    # Add query and path
    cmd.extend([escaped, repo_path])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode not in (0, 1):  # 1 = no matches (ok)
            log.warning(
                "execute_search.ripgrep_error",
                stderr=stderr.decode(),
                return_code=process.returncode,
            )
            return []

        return _parse_ripgrep_output(stdout.decode(), repo_path, exclude_file)

    except FileNotFoundError:
        log.error(
            "execute_search.ripgrep_not_found",
            hint="Install ripgrep: brew install ripgrep (macOS) or apt install ripgrep (Ubuntu)",
        )
        return []
    except Exception as e:
        log.error(
            "execute_search.error",
            error=str(e),
            error_type=type(e).__name__,
        )
        return []


def _parse_ripgrep_output(
    output: str,
    repo_path: str,
    exclude_file: str | None,
) -> list[SearchResult]:
    """Parse ripgrep JSON output into SearchResult objects."""
    results: list[SearchResult] = []
    context_buffer: dict[str, list[str]] = {}  # file -> context lines

    for line in output.strip().split("\n"):
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = data.get("type")

        if msg_type == "match":
            match_data = data.get("data", {})
            file_path = match_data.get("path", {}).get("text", "")

            # Make path relative to repo
            if file_path.startswith(repo_path):
                file_path = file_path[len(repo_path):].lstrip("/")

            # Skip the file being changed
            if exclude_file and file_path == exclude_file:
                continue

            line_num = match_data.get("line_number", 0)
            match_text = match_data.get("lines", {}).get("text", "").strip()

            # Get context from buffer
            context = context_buffer.get(file_path, [])
            context_str = "\n".join(context[-SEARCH_CONTEXT_LINES:]) if context else ""

            results.append(SearchResult(
                file_path=file_path,
                line=line_num,
                match_text=match_text,
                context=context_str,
            ))

        elif msg_type == "context":
            # Store context for next match
            ctx_data = data.get("data", {})
            file_path = ctx_data.get("path", {}).get("text", "")
            ctx_text = ctx_data.get("lines", {}).get("text", "").strip()

            if file_path not in context_buffer:
                context_buffer[file_path] = []
            context_buffer[file_path].append(ctx_text)

    return results
