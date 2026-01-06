"""Base agent module with shared logic for code review agents.

Provides a factory function to create agent run functions with minimal duplication.
Each specialized agent (security, logic, style) uses this base to define its behavior.
"""

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import structlog

from ...core.config import ReviewerConfig
from ...core.llm import get_structured_llm
from ..models import AgentFindings
from ..state import FileChange, ReviewComment

if TYPE_CHECKING:
    from ..state import GraphState

log = structlog.get_logger()

MAX_CONCURRENT_CALLS = 5


def create_agent_runner(
    agent_name: str,
    prompt_template: str,
    check_type: str,
) -> Callable[["GraphState"], "asyncio.coroutines.coroutine"]:
    """
    Factory function to create an agent run function.

    Args:
        agent_name: Unique identifier for the agent (e.g., "security", "logic", "style").
        prompt_template: The prompt template string with {filename}, {language}, {diff}
            placeholders.
        check_type: Description of the check type for guidelines suffix.

    Returns:
        An async run function compatible with LangGraph nodes.
    """

    async def run(state: "GraphState") -> dict:
        """
        Analyze code files using the configured agent.

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
        if not config.is_agent_enabled(agent_name):
            log.info(f"{agent_name} agent disabled by config")
            return {"comments": []}

        files_to_scan = [f for f in state["files"] if f.patch]
        log.info(f"{agent_name} agent started", files=len(files_to_scan))

        # Get effective thresholds from config
        threshold = config.get_threshold()
        max_comments = config.get_max_comments()

        structured_llm = get_structured_llm(AgentFindings)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

        async def process_file(file: FileChange) -> list[ReviewComment]:
            """Process a single file for issues."""
            if not file.patch:
                return []

            # Get path-specific instructions
            extra_instructions = config.get_path_instructions(file.filename)

            # Build prompt with extra instructions
            prompt = _build_prompt(
                prompt_template=prompt_template,
                filename=file.filename,
                language=file.language or "text",
                diff=file.patch,
                extra_instructions=extra_instructions,
                check_type=check_type,
            )

            try:
                async with semaphore:
                    result = cast(AgentFindings, await structured_llm.ainvoke(prompt))

                # Filter by configured threshold
                comments = [
                    ReviewComment(
                        file=file.filename,
                        line=finding.line,
                        severity=finding.severity,
                        category=agent_name,
                        message=finding.message,
                        suggestion=finding.suggestion,
                        confidence=finding.confidence,
                        agent=agent_name,
                    )
                    for finding in result.findings
                    if finding.confidence >= threshold
                ]

                # Limit comments per file
                return comments[:max_comments]

            except Exception as e:
                log.error(f"{agent_name} agent error", file=file.filename, error=str(e))
                return []

        tasks = [process_file(file) for file in files_to_scan]
        results = await asyncio.gather(*tasks)

        comments = [comment for file_comments in results for comment in file_comments]

        log.info(f"{agent_name} scan complete", findings=len(comments))
        return {"comments": comments}

    return run


def _build_prompt(
    prompt_template: str,
    filename: str,
    language: str,
    diff: str,
    extra_instructions: list[str],
    check_type: str,
) -> str:
    """Build prompt with optional extra instructions.

    Args:
        prompt_template: The base prompt template with placeholders.
        filename: Name of the file being analyzed.
        language: Programming language of the file.
        diff: Git diff content.
        extra_instructions: Additional repository-specific instructions.
        check_type: Type of check for the guidelines suffix.

    Returns:
        Formatted prompt string.
    """
    base_prompt = prompt_template.format(
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

Apply these guidelines in addition to the standard {check_type} checks.
"""

    return base_prompt
