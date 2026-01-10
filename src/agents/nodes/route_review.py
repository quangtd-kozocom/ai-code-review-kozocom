"""Route review node - Phase 3a of the review pipeline.

Routes functions to appropriate review depth based on impact analysis.
Uses minimal LLM for smart routing decisions.
"""

import structlog

from ...analysis.impact_analyzer import FunctionImpact, ImpactLevel, ImpactReport
from ...core.config import ReviewerConfig
from ..state import FunctionReviewInput, ReviewState

log = structlog.get_logger()


def _is_trivial_change(impact: FunctionImpact) -> bool:
    """Detect trivial changes that don't need review.
    
    Note: We only mark as trivial if we have high confidence.
    If call graph data is missing (caller_count == 0 but we don't know why),
    we err on the side of caution and review the function.
    """
    match impact.impact_level:
        case ImpactLevel.TRIVIAL:
            # Explicitly marked as trivial by impact analyzer
            return True
        case ImpactLevel.LOW if not impact.signature_changed:
            # Low impact without signature change might be trivial
            # BUT: Only skip if we have call graph data confirming no callers
            # If caller_count is 0 due to missing call graph, don't skip
            # (Better to review too much than miss issues)
            # 
            # Since we can't reliably tell the difference, default to False
            # to avoid skipping functions when call graph is empty
            return False
        case _:
            return False


def _determine_review_depth(impact: FunctionImpact) -> str:
    """Determine appropriate review depth for a function."""
    match impact.impact_level:
        case ImpactLevel.CRITICAL:
            return "deep"
        case ImpactLevel.HIGH:
            return "deep" if impact.signature_changed else "standard"
        case ImpactLevel.MEDIUM:
            return "standard"
        case _:
            return "quick"


def _determine_focus_areas(impact: FunctionImpact) -> list[str]:
    """Determine focus areas for review based on impact."""
    areas: list[str] = []
    
    if impact.signature_changed:
        areas.append("backward_compatibility")
    
    if impact.caller_count > 0:
        areas.append("caller_impact")
    
    for warning in impact.warnings:
        match warning.warning_type.value:
            case "breaking_signature":
                areas.append("breaking_changes")
            case "many_callers":
                areas.append("api_stability")
    
    return list(set(areas))  # Deduplicate


async def run(state: ReviewState) -> dict:
    """Route functions to appropriate review depth.
    
    Phase 3a: Review routing
    - Filter out trivial changes
    - Determine review depth for each function
    - Prioritize high-impact changes
    - Set focus areas for targeted review
    
    This node uses minimal LLM (or pure heuristics) for routing.
    
    Args:
        state: Current workflow state with impact_report.
        
    Returns:
        State update with functions_to_review.
    """
    # Skip if flagged
    if state.get("skip_review"):
        return {"functions_to_review": []}
    
    report: ImpactReport = state.get("impact_report", ImpactReport())
    review_context = state.get("review_context")
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    
    if not report.functions:
        log.info("route_review.skipped", reason="no_functions")
        return {"functions_to_review": []}
    
    log.info(
        "route_review.started",
        total_functions=len(report.functions),
    )
    
    functions_to_review: list[FunctionReviewInput] = []
    skipped_trivial = 0
    
    # Get function contexts from review context
    func_contexts = {}
    if review_context:
        func_contexts = {fc.name: fc for fc in review_context.functions}
    
    for impact in report.functions:
        # Skip trivial changes
        if _is_trivial_change(impact):
            skipped_trivial += 1
            log.debug(
                "route_review.skipped_trivial",
                function=impact.name,
            )
            continue
        
        # Get function context
        func_context = func_contexts.get(impact.name)
        if not func_context:
            log.warning(
                "route_review.missing_context",
                function=impact.name,
            )
            continue
        
        # Determine review parameters
        review_depth = _determine_review_depth(impact)
        focus_areas = _determine_focus_areas(impact)
        
        functions_to_review.append(FunctionReviewInput(
            function_context=func_context,
            review_depth=review_depth,
            focus_areas=focus_areas,
        ))
    
    # Sort by impact level (critical first)
    impact_order = {
        ImpactLevel.CRITICAL: 0,
        ImpactLevel.HIGH: 1,
        ImpactLevel.MEDIUM: 2,
        ImpactLevel.LOW: 3,
        ImpactLevel.TRIVIAL: 4,
    }
    functions_to_review.sort(
        key=lambda f: impact_order.get(f.function_context.impact_level, 99)
    )
    
    # Limit number of functions to review based on config
    max_functions = getattr(config, "max_functions_to_review", 20)
    if len(functions_to_review) > max_functions:
        log.warning(
            "route_review.truncated",
            original=len(functions_to_review),
            max=max_functions,
        )
        functions_to_review = functions_to_review[:max_functions]
    
    log.info(
        "route_review.complete",
        to_review=len(functions_to_review),
        skipped_trivial=skipped_trivial,
        deep_review=sum(1 for f in functions_to_review if f.review_depth == "deep"),
        standard_review=sum(1 for f in functions_to_review if f.review_depth == "standard"),
    )
    
    return {"functions_to_review": functions_to_review}
