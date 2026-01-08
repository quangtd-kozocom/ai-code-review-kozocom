"""Base agent module - factory for creating code review agent nodes."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import structlog

from ...core.config import ReviewerConfig
from ...core.llm import get_structured_llm
from ..models import AgentFindings
from ..state import EnhancedFileChange, FileChange, ReviewComment

if TYPE_CHECKING:
    from ..state import GraphState

log = structlog.get_logger()

MAX_CONCURRENT_CALLS = 5


# =============================================================================
# Prompt Building
# =============================================================================


def _build_prompt(
    template: str,
    filename: str,
    language: str,
    diff: str,
    extra_instructions: list[str],
    check_type: str,
    rag_context: str | None = None,
) -> str:
    """Build the analysis prompt with optional repository-specific instructions and RAG context."""
    base = template.format(filename=filename, language=language, diff=diff)

    parts = [base]

    # Add RAG-retrieved related code context
    if rag_context:
        parts.append(f"""
## ⚠️ IMPORTANT: Related Code Context (You MUST consider this)

The code being reviewed calls or is called by the following functions from the codebase:

{rag_context}

**YOU MUST CHECK:**
1. **Parameter Compatibility**: Do the parameters passed match what the called function expects?
2. **Return Value Handling**: Is the return value from called functions handled correctly?
3. **Error Propagation**: If the called function can raise exceptions, are they handled?
4. **Type Consistency**: Are the types compatible between caller and callee?
5. **Side Effects**: Could changes break the behavior expected by callers?

If you find issues related to these functions, mention them by name
(e.g., "The call to `calculate()` may fail because...").
""")

    # Add repository-specific instructions
    if extra_instructions:
        instructions = "\n".join(f"- {i}" for i in extra_instructions)
        parts.append(f"""
## Repository-Specific Guidelines

The following additional guidelines apply to this file:

{instructions}

Apply these guidelines in addition to the standard {check_type} checks.
""")

    return "\n".join(parts)


# =============================================================================
# Finding Conversion
# =============================================================================


def _convert_findings_to_comments(
    findings: AgentFindings,
    filename: str,
    agent_name: str,
    threshold: float,
    max_comments: int,
    related_files: list[str] | None = None,
) -> list[ReviewComment]:
    """Convert LLM findings to ReviewComment objects, applying filters."""
    comments = [
        ReviewComment(
            file=filename,
            line=f.line,
            severity=f.severity,
            category=agent_name,
            message=f.message,
            suggestion=f.suggestion,
            confidence=f.confidence,
            agent=agent_name,
            related_files=related_files or [],
        )
        for f in findings.findings
        if f.confidence >= threshold
    ]
    return comments[:max_comments]


# =============================================================================
# Factory
# =============================================================================


def create_agent_runner(
    agent_name: str,
    prompt_template: str,
    check_type: str,
) -> Callable[["GraphState"], Awaitable[dict]]:
    """
    Create an agent run function for LangGraph.

    Args:
        agent_name: Identifier for the agent (e.g., "security", "logic", "style")
        prompt_template: Template with {filename}, {language}, {diff} placeholders
        check_type: Type of check for logging and instructions suffix
    """

    async def run(state: "GraphState") -> dict:
        config: ReviewerConfig = state.get("repo_config", ReviewerConfig())

        # Check if agent is enabled
        if not config.is_agent_enabled(agent_name):
            log.info("agent.disabled", agent=agent_name)
            return {"comments": []}

        files = [f for f in state["files"] if f.patch]
        log.info("agent.started", agent=agent_name, files=len(files))

        # Get config values
        threshold = config.get_threshold()
        max_comments = config.get_max_comments()
        llm = get_structured_llm(AgentFindings)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

        async def analyze_file(file: FileChange | EnhancedFileChange) -> list[ReviewComment]:
            if not file.patch:
                return []

            rag_context = None
            related_files: list[str] = []

            if hasattr(file, "related_context") and file.related_context:
                for ctx in file.related_context:
                    log.info(
                        "agent.rag_detail",
                        file=file.filename,
                        relationship=ctx.relationship,
                        related_file=ctx.file_path,
                        related_func=ctx.name,
                    )
                    # Format with line numbers if available
                    if ctx.start_line and ctx.end_line:
                        ref = f"{ctx.file_path}:{ctx.name} (L{ctx.start_line}-{ctx.end_line})"
                    else:
                        ref = f"{ctx.file_path}:{ctx.name}"
                    if ref not in related_files:
                        related_files.append(ref)

                context_parts = [
                    f"**{ctx.relationship.upper()}**: `{ctx.file_path}` - `{ctx.name}`\n"
                    f"```\n{ctx.content[:500]}\n```"
                    for ctx in file.related_context[:3]
                ]
                rag_context = "\n\n".join(context_parts)

            prompt = _build_prompt(
                template=prompt_template,
                filename=file.filename,
                language=file.language or "text",
                diff=file.patch,
                extra_instructions=config.get_path_instructions(file.filename),
                check_type=check_type,
                rag_context=rag_context,
            )

            try:
                async with semaphore:
                    result = cast(AgentFindings, await llm.ainvoke(prompt))

                return _convert_findings_to_comments(
                    findings=result,
                    filename=file.filename,
                    agent_name=agent_name,
                    threshold=threshold,
                    max_comments=max_comments,
                    related_files=related_files,
                )
            except Exception as e:
                log.error("agent.file_error", agent=agent_name, file=file.filename, error=str(e))
                return []

        # Process all files concurrently
        results = await asyncio.gather(*[analyze_file(f) for f in files])
        comments = [c for file_comments in results for c in file_comments]

        log.info("agent.completed", agent=agent_name, findings=len(comments))
        return {"comments": comments}

    return run
