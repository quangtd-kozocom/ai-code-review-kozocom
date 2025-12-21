import json

import structlog

from ...core.llm import get_llm
from ..prompts.logic import PROMPT
from ..state import GraphState, ReviewComment

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """Analyze code for logic errors and bugs."""
    llm = get_llm()
    comments = []

    for file in state["files"]:
        if not file.patch:
            continue

        prompt = PROMPT.format(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
        )

        try:
            response = await llm.ainvoke(prompt)
            findings = _parse_findings(response.content)

            for f in findings:
                if f.get("confidence", 0) < 0.7:
                    continue
                comments.append(
                    ReviewComment(
                        file=file.filename,
                        line=f["line"],
                        severity=f.get("severity", "warning"),
                        category="logic",
                        message=f["message"],
                        suggestion=f.get("suggestion"),
                        confidence=f["confidence"],
                        agent="logic",
                    )
                )
        except Exception as e:
            log.error("Logic agent error", file=file.filename, error=str(e))

    log.info("Logic scan complete", findings=len(comments))
    return {"comments": comments}


def _parse_findings(content: str) -> list[dict]:
    """Extract JSON findings from LLM response."""
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            return data.get("findings", [])
    except json.JSONDecodeError:
        log.warning("Failed to parse logic findings JSON")
    return []
