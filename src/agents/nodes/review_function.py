"""Function reviewer node - Phase 3b of the review pipeline.

Reviews individual functions with targeted LLM prompts.
This is where the actual LLM-based review happens.
"""

import structlog

from ...analysis.context_builder import FunctionContext
from ...core.llm import get_llm
from ..models import AgentFindings
from ..prompts.function_review import SYSTEM_PROMPT, build_function_review_prompt
from ..state import FunctionReviewInput, ReviewComment, ReviewState

log = structlog.get_logger()


async def review_single_function(
    review_input: FunctionReviewInput,
    external_files: list | None = None,
    breaking_changes: list[str] | None = None,
) -> list[ReviewComment]:
    """Review a single function using LLM.
    
    Args:
        review_input: Function review input with context.
        external_files: External files that depend on this code.
        breaking_changes: List of detected breaking changes.
        
    Returns:
        List of review comments.
    """
    ctx = review_input.function_context
    
    log.debug(
        "review_function.reviewing",
        function=ctx.name,
        file=ctx.file_path,
        depth=review_input.review_depth,
    )
    
    # Build callers dict for prompt
    callers_data = [
        {
            "name": c.caller,
            "file": c.caller_file,
            "line": c.line,
            "context": c.context,
        }
        for c in ctx.callers[:5]  # Limit to 5 callers
    ]

    # Build callees dict for prompt
    callees_data = [
        {
            "name": c.name,
            "file_path": c.file_path,
            "source_code": c.source_code,
            "signature": c.signature,
            "has_validation": c.has_validation,
            "returns_optional": c.returns_optional,
        }
        for c in ctx.callees
    ]
    
    # Build external files dict for prompt
    external_files_data = None
    if external_files:
        external_files_data = [
            {
                "path": f.path,
                "usage_type": f.usage_type,
                "references": f.references,
                "will_break": f.will_break,
                "break_reason": f.break_reason,
                "affected_lines": f.affected_lines,
            }
            for f in external_files
            if ctx.name in f.references  # Only include files that reference this function
        ]

    # Build prompt
    prompt = build_function_review_prompt(
        function_name=ctx.name,
        file_path=ctx.file_path,
        change_type=ctx.change_type.value,
        impact_level=ctx.impact_level.value,
        old_code=ctx.old_code,
        new_code=ctx.new_code,
        diff=ctx.diff,
        callers=callers_data,
        callees=callees_data,
        review_questions=ctx.review_questions,
        focus_areas=review_input.focus_areas,
        review_depth=review_input.review_depth,
        external_files=external_files_data,
        breaking_changes=breaking_changes,
    )
    
    # Log first prompt with dependency context for debugging
    if ctx.callees or callers_data:
        log.info(
            "review_function.prompt_with_dependencies",
            function=ctx.name,
            file=ctx.file_path,
            callers_count=len(callers_data),
            callees_count=len(ctx.callees),
            callees=ctx.callees[:10],
            callers=[c["name"] for c in callers_data],
            prompt_preview=prompt[:2000] if len(prompt) > 2000 else prompt,
        )
        # Full prompt logged at debug level for detailed analysis
        log.debug(
            "review_function.full_prompt",
            function=ctx.name,
            prompt=prompt,
        )
    
    # Call LLM with structured output
    llm = get_llm().with_structured_output(AgentFindings)
    
    try:
        # Combine system prompt and user prompt
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        
        # Get structured output
        result = await llm.ainvoke(full_prompt)
        
        # Convert AgentFindings to ReviewComments
        comments = []
        for finding in result.findings:
            comments.append(ReviewComment(
                file=ctx.file_path,
                line=finding.line,
                severity=finding.severity,
                category="logic",  # Default category
                message=finding.message,
                suggestion=finding.suggestion,
                confidence=finding.confidence,
                agent="function_reviewer",
            ))
        
        log.debug(
            "review_function.complete",
            function=ctx.name,
            comments_count=len(comments),
        )
        
        return comments
    
    except Exception as e:
        log.error(
            "review_function.llm_error",
            function=ctx.name,
            error=str(e),
        )
        return []


async def run(state: ReviewState) -> dict:
    """Review all functions scheduled for review.
    
    Phase 3b: LLM-based review
    - Review each function with targeted prompts
    - Include external files context for complete picture
    - Collect all findings
    
    This node uses LLM for actual code review.
    
    Args:
        state: Current workflow state with functions_to_review.
        
    Returns:
        State update with comments.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {"comments": []}
    
    functions_to_review = state.get("functions_to_review", [])
    
    if not functions_to_review:
        log.info("review_functions.skipped", reason="no_functions")
        return {"comments": []}
    
    # Get external context from state
    external_files = state.get("external_files", [])
    breaking_changes = state.get("breaking_changes", [])
    
    log.info(
        "review_functions.started",
        count=len(functions_to_review),
        external_files_available=len(external_files),
        breaking_changes_detected=len(breaking_changes),
    )
    
    all_comments: list[ReviewComment] = []
    
    # Review each function
    # Note: Could be parallelized with asyncio.gather for performance
    for review_input in functions_to_review:
        comments = await review_single_function(
            review_input,
            external_files=external_files,
            breaking_changes=breaking_changes,
        )
        all_comments.extend(comments)
    
    log.info(
        "review_functions.complete",
        functions_reviewed=len(functions_to_review),
        total_comments=len(all_comments),
    )
    
    return {"comments": all_comments}
