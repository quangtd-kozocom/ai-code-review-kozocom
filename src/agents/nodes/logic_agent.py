"""Logic agent for analyzing code bugs and errors.

Uses LangChain structured output for type-safe LLM responses.
"""

import asyncio
from typing import TYPE_CHECKING

import structlog

from ...core.llm import get_structured_llm
from ..models import AgentFindings
from ..prompts.logic import PROMPT
from ..state import ReviewComment

if TYPE_CHECKING:
    from ..state import GraphState

log = structlog.get_logger()

MAX_CONCURRENT_CALLS = 5
MIN_CONFIDENCE_THRESHOLD = 0.7


async def run(state: "GraphState") -> dict:
    """
    Analyze code for logic errors and potential bugs.

    Processes all files in parallel with a semaphore to limit concurrency.
    Uses structured output for reliable parsing of LLM responses.

    Args:
        state: Current graph state containing files to analyze.

    Returns:
        Dict with 'comments' key containing list of ReviewComment.
    """
    files_to_scan = [f for f in state["files"] if f.patch]
    log.info("Logic agent started", files=len(files_to_scan))

    structured_llm = get_structured_llm(AgentFindings)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

    async def process_file(file) -> list[ReviewComment]:
        """Process a single file for logic issues."""
        if not file.patch:
            return []

        prompt = PROMPT.format(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
        )

        try:
            async with semaphore:
                result: AgentFindings = await structured_llm.ainvoke(prompt)

            return [
                ReviewComment(
                    file=file.filename,
                    line=finding.line,
                    severity=finding.severity,
                    category="logic",
                    message=finding.message,
                    suggestion=finding.suggestion,
                    confidence=finding.confidence,
                    agent="logic",
                )
                for finding in result.findings
                if finding.confidence >= MIN_CONFIDENCE_THRESHOLD
            ]
        except Exception as e:
            log.error("Logic agent error", file=file.filename, error=str(e))
            return []

    tasks = [process_file(file) for file in files_to_scan]
    results = await asyncio.gather(*tasks)

    comments = [comment for file_comments in results for comment in file_comments]

    log.info("Logic scan complete", findings=len(comments))
    return {"comments": comments}
