import asyncio
import json

import structlog

from ...core.llm import get_llm
from ..prompts.security import PROMPT
from ..state import GraphState, ReviewComment

log = structlog.get_logger()

MAX_CONCURRENT_CALLS = 5


async def run(state: GraphState) -> dict:
    """Analyze code for security vulnerabilities."""
    files_to_scan = [f for f in state["files"] if f.patch]
    log.info("Security agent started", files=len(files_to_scan))

    llm = get_llm()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

    async def process_file(file) -> list[ReviewComment]:
        """Process a single file for security issues."""
        if not file.patch:
            return []

        prompt = PROMPT.format(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
        )

        try:
            async with semaphore:
                response = await llm.ainvoke(prompt)
            findings = _parse_findings(response.content)

            file_comments = []
            for f in findings:
                if f.get("confidence", 0) < 0.7:
                    continue
                file_comments.append(
                    ReviewComment(
                        file=file.filename,
                        line=f["line"],
                        severity=f["severity"],
                        category="security",
                        message=f["message"],
                        suggestion=f.get("suggestion"),
                        confidence=f["confidence"],
                        agent="security",
                    )
                )
            return file_comments
        except Exception as e:
            log.error("Security agent error", file=file.filename, error=str(e))
            return []

    tasks = [process_file(file) for file in state["files"]]
    results = await asyncio.gather(*tasks)

    comments = [comment for file_comments in results for comment in file_comments]

    log.info("Security scan complete", findings=len(comments))
    return {"comments": comments}


def _parse_findings(content: str) -> list[dict]:
    """Extract JSON findings from LLM response."""
    try:
        # Try to find JSON in the response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            return data.get("findings", [])
    except json.JSONDecodeError:
        log.warning("Failed to parse security findings JSON")
    return []
