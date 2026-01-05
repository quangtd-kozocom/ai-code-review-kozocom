"""Logic agent for analyzing code bugs and errors.

Uses LangChain structured output for type-safe LLM responses.
Supports per-repository configuration via ReviewerConfig.
"""

import asyncio
from typing import TYPE_CHECKING

import structlog

from ...core.config import ReviewerConfig
from ...core.llm import get_structured_llm
from ..models import AgentFindings
from ..prompts.logic import PROMPT
from ..state import FileChange, ReviewComment

if TYPE_CHECKING:
    from ..state import GraphState

log = structlog.get_logger()

MAX_CONCURRENT_CALLS = 5
AGENT_NAME = "logic"


async def run(state: "GraphState") -> dict:
    """
    Analyze code for logic errors and potential bugs.

    Processes all files in parallel with a semaphore to limit concurrency.
    Uses structured output for reliable parsing of LLM responses.

    Uses config for:
    - Checking if agent is enabled
    - confidence_threshold filtering
    - max_comments_per_file limiting
    - path_instructions for additional context

    Args:
        state: Current graph state containing files to analyze.

    Returns:
        Dict with 'comments' key containing list of ReviewComment.
    """
    # Get config (with defaults fallback)
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())

    # Check if this agent is enabled
    if not config.is_agent_enabled(AGENT_NAME):
        log.info(f"{AGENT_NAME} agent disabled by config")
        return {"comments": []}

    files_to_scan = [f for f in state["files"] if f.patch]
    log.info(f"{AGENT_NAME} agent started", files=len(files_to_scan))

    # Get effective thresholds from config
    threshold = config.get_threshold()
    max_comments = config.get_max_comments()

    structured_llm = get_structured_llm(AgentFindings)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

    async def process_file(file: FileChange) -> list[ReviewComment]:
        """Process a single file for logic issues."""
        if not file.patch:
            return []

        # Get path-specific instructions
        extra_instructions = config.get_path_instructions(file.filename)

        # Build prompt with extra instructions
        prompt = _build_prompt(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
            extra_instructions=extra_instructions,
        )

        try:
            async with semaphore:
                result: AgentFindings = await structured_llm.ainvoke(prompt)

            # Filter by configured threshold
            comments = [
                ReviewComment(
                    file=file.filename,
                    line=finding.line,
                    severity=finding.severity,
                    category=AGENT_NAME,
                    message=finding.message,
                    suggestion=finding.suggestion,
                    confidence=finding.confidence,
                    agent=AGENT_NAME,
                )
                for finding in result.findings
                if finding.confidence >= threshold
            ]

            # Limit comments per file
            return comments[:max_comments]

        except Exception as e:
            log.error(f"{AGENT_NAME} agent error", file=file.filename, error=str(e))
            return []

    tasks = [process_file(file) for file in files_to_scan]
    results = await asyncio.gather(*tasks)

    comments = [comment for file_comments in results for comment in file_comments]

    log.info(f"{AGENT_NAME} scan complete", findings=len(comments))
    return {"comments": comments}


def _build_prompt(
    filename: str,
    language: str,
    diff: str,
    extra_instructions: list[str],
) -> str:
    """Build prompt with optional extra instructions."""
    base_prompt = PROMPT.format(
        filename=filename,
        language=language,
        diff=diff,
    )

    if extra_instructions:
        instructions_text = "\n".join(f"- {i}" for i in extra_instructions)
        return f"""{base_prompt}

## Repository-Specific Guidelines

The following additional guidelines apply to this file:

{instructions_text}

Apply these guidelines in addition to the standard logic checks.
"""

    return base_prompt
