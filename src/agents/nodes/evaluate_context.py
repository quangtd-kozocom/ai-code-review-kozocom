"""Evaluate context node - Phase 2.5b of the review pipeline.

LLM evaluates if we have sufficient context for accurate review.
This is the evaluator in the evaluator-optimizer pattern.
"""

import structlog

from ...core.llm import get_llm
from ..models import ContextEvaluation
from ..prompts.context_evaluation import (
    EVALUATE_CONTEXT_PROMPT,
    format_changed_code,
    format_external_files,
)
from ..state import ReviewState

log = structlog.get_logger()

# Maximum iterations for context enrichment loop
MAX_ENRICHMENT_ITERATIONS = 3


async def run(state: ReviewState) -> dict:
    """Evaluate if we have sufficient context for review.
    
    Phase 2.5b: Context evaluation with LLM
    - Analyze changed code and external files found so far
    - Determine if more context is needed
    - Suggest additional classes/services to search for
    - Increment iteration counter
    
    This implements the evaluator part of the evaluator-optimizer pattern.
    
    Args:
        state: Current workflow state with function_changes and external_files.
        
    Returns:
        State update with context_sufficient, pending_searches, evaluation_iteration.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {
            "context_sufficient": True,
            "pending_searches": [],
            "evaluation_iteration": 0,
        }
    
    function_changes = state.get("function_changes", {})
    external_files = state.get("external_files", [])
    iteration = state.get("evaluation_iteration", 0) + 1
    
    log.info(
        "evaluate_context.started",
        iteration=iteration,
        external_files_count=len(external_files),
        functions_changed=len(function_changes),
    )
    
    # Format context for LLM
    changed_code_str = format_changed_code(function_changes)
    external_files_str = format_external_files(external_files)
    
    # Call LLM with structured output
    llm = get_llm().with_structured_output(ContextEvaluation)
    
    try:
        evaluation = await llm.ainvoke(
            EVALUATE_CONTEXT_PROMPT.format(
                changed_code=changed_code_str,
                external_files=external_files_str,
            )
        )
        
        log.info(
            "evaluate_context.complete",
            iteration=iteration,
            sufficient=evaluation.context_sufficient,
            confidence=evaluation.confidence,
            need_more_count=len(evaluation.need_more_context_for),
            need_more=evaluation.need_more_context_for[:5],  # Log first 5
            reasoning=evaluation.reasoning[:200],
        )
        
        return {
            "context_sufficient": evaluation.context_sufficient,
            "pending_searches": evaluation.need_more_context_for,
            "evaluation_iteration": iteration,
        }
    
    except Exception as e:
        log.error(
            "evaluate_context.error",
            iteration=iteration,
            error=str(e),
        )
        # On error, assume sufficient to avoid getting stuck
        return {
            "context_sufficient": True,
            "pending_searches": [],
            "evaluation_iteration": iteration,
        }


def should_continue(state: ReviewState) -> str:
    """Determine if we should continue discovering or move to review.
    
    Conditional edge function for the evaluator loop.
    
    Args:
        state: Current workflow state.
        
    Returns:
        "need_more" to loop back to discover_externals
        "sufficient" to proceed to route_review
        "max_iterations" when we've hit the iteration limit
        "no_more_targets" when LLM has no suggestions
    """
    # Check if context is sufficient
    if state.get("context_sufficient"):
        log.info(
            "evaluate_context.routing",
            decision="sufficient",
            iteration=state.get("evaluation_iteration", 0),
        )
        return "sufficient"
    
    # Check iteration limit
    iteration = state.get("evaluation_iteration", 0)
    if iteration >= MAX_ENRICHMENT_ITERATIONS:
        log.warning(
            "evaluate_context.routing",
            decision="max_iterations",
            iteration=iteration,
        )
        return "max_iterations"
    
    # Check if LLM has suggestions
    pending_searches = state.get("pending_searches", [])
    if not pending_searches:
        log.warning(
            "evaluate_context.routing",
            decision="no_more_targets",
            iteration=iteration,
        )
        return "no_more_targets"
    
    # Continue discovering
    log.info(
        "evaluate_context.routing",
        decision="need_more",
        iteration=iteration,
        pending_count=len(pending_searches),
    )
    return "need_more"
