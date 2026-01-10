"""Function reviewer node - Phase 3b of the review pipeline.

Reviews individual functions with targeted LLM prompts.
This is where the actual LLM-based review happens.
"""

import json
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ...analysis.context_builder import FunctionContext
from ...core.llm import get_llm
from ..prompts.function_review import SYSTEM_PROMPT, build_function_review_prompt
from ..state import FunctionReviewInput, ReviewComment, ReviewState

log = structlog.get_logger()


def _parse_llm_response(response: str, file_path: str) -> list[ReviewComment]:
    """Parse LLM response into ReviewComment objects.
    
    Args:
        response: Raw LLM response string.
        file_path: File path for the comments.
        
    Returns:
        List of ReviewComment objects.
    """
    comments: list[ReviewComment] = []
    
    try:
        # Try to extract JSON from response
        response = response.strip()
        
        # Handle markdown code blocks
        if response.startswith("```"):
            lines = response.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                elif in_block:
                    json_lines.append(line)
            response = "\n".join(json_lines)
        
        data = json.loads(response)
        findings = data.get("findings", [])
        
        for finding in findings:
            # Validate required fields
            if not all(k in finding for k in ["line", "severity", "message"]):
                log.warning(
                    "review_function.invalid_finding",
                    missing_keys=[k for k in ["line", "severity", "message"] if k not in finding],
                )
                continue
            
            # Validate severity
            severity = finding["severity"]
            if severity not in ("critical", "warning", "info", "suggestion"):
                severity = "warning"
            
            comments.append(ReviewComment(
                file=file_path,
                line=int(finding["line"]),
                severity=severity,
                category="logic",  # Default category
                message=finding["message"],
                suggestion=finding.get("suggestion"),
                confidence=float(finding.get("confidence", 0.8)),
                agent="function_reviewer",
            ))
    
    except json.JSONDecodeError as e:
        log.error(
            "review_function.parse_failed",
            error=str(e),
            response_preview=response[:200],
        )
    except Exception as e:
        log.error(
            "review_function.parse_error",
            error=str(e),
        )
    
    return comments


async def review_single_function(
    review_input: FunctionReviewInput,
) -> list[ReviewComment]:
    """Review a single function using LLM.
    
    Args:
        review_input: Function review input with context.
        
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
        callees=ctx.callees,
        review_questions=ctx.review_questions,
        focus_areas=review_input.focus_areas,
        review_depth=review_input.review_depth,
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
    
    # Call LLM
    llm = get_llm()
    
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        
        comments = _parse_llm_response(content, ctx.file_path)
        
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
    
    log.info(
        "review_functions.started",
        count=len(functions_to_review),
    )
    
    all_comments: list[ReviewComment] = []
    
    # Review each function
    # Note: Could be parallelized with asyncio.gather for performance
    for review_input in functions_to_review:
        comments = await review_single_function(review_input)
        all_comments.extend(comments)
    
    log.info(
        "review_functions.complete",
        functions_reviewed=len(functions_to_review),
        total_comments=len(all_comments),
    )
    
    return {"comments": all_comments}
