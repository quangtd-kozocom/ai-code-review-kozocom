"""Verify impact node - LLM confirms which callers will break."""

import structlog

from ...core.llm import get_structured_llm
from ..constants import (
    CRITICAL_CALLER_THRESHOLD,
    MAX_SEARCH_ITERATIONS,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
)
from ..models import ImpactVerificationResult
from ..prompts.verify_impact import VERIFY_IMPACT_PROMPT
from ..state import AffectedCaller, BreakingChange, ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Verify which search results are actually affected.

    The LLM analyzes each search result to determine if it's
    a real usage that will break due to the change.

    Args:
        state: Current workflow state with search_results.

    Returns:
        State updates with verified_callers and need_more_search.
    """
    change = state.get("current_change")
    search_results = state.get("search_results", [])
    iteration = state.get("search_iteration", 0)

    if not change:
        log.debug("verify_impact.skipped", reason="no current_change")
        return {
            "verified_callers": [],
            "need_more_search": False,
        }

    if not search_results:
        log.info(
            "verify_impact.no_results",
            entity=change.entity_name,
            entity_type=change.entity_type,
        )
        return {
            "verified_callers": [],
            "need_more_search": False,
        }

    log.info(
        "verify_impact.started",
        entity=change.entity_name,
        entity_type=change.entity_type,
        results_count=len(search_results),
        iteration=iteration,
    )

    # Format search results for prompt
    results_text = _format_search_results(search_results)

    prompt = VERIFY_IMPACT_PROMPT.format(
        entity_name=change.entity_name,
        entity_type=change.entity_type,
        file_path=change.file_path,
        change_type=change.change_type,
        change_detail=change.change_detail,
        old_definition=change.old_definition or "(none)",
        new_definition=change.new_definition or "(none)",
        search_results=results_text,
    )

    # Call LLM
    llm = get_structured_llm(ImpactVerificationResult)

    try:
        result: ImpactVerificationResult = await llm.ainvoke(prompt)
        log.debug(
            "verify_impact.llm_response",
            entity=change.entity_name,
            affected_count=len(result.affected_callers),
            need_more_search=result.need_more_search,
            confidence=result.confidence,
        )
    except Exception as e:
        log.error(
            "verify_impact.llm_error",
            entity=change.entity_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "verified_callers": [],
            "need_more_search": False,
        }

    # Convert to AffectedCaller
    verified_callers = [
        AffectedCaller(
            file_path=c.file_path,
            line=c.line,
            call_text=c.call_text,
            break_reason=c.break_reason,
        )
        for c in result.affected_callers
        if c.will_break
    ]

    # Check if we should search more
    need_more = (
        result.need_more_search
        and result.additional_queries
        and iteration < MAX_SEARCH_ITERATIONS
    )

    if need_more:
        log.info(
            "verify_impact.requesting_more_search",
            entity=change.entity_name,
            iteration=iteration,
            max_iterations=MAX_SEARCH_ITERATIONS,
            additional_queries=result.additional_queries,
        )

    log.info(
        "verify_impact.complete",
        entity=change.entity_name,
        verified_count=len(verified_callers),
        need_more_search=need_more,
        confidence=result.confidence,
        affected_files=[c.file_path for c in verified_callers],
    )

    # If we have verified callers, create a breaking change
    file_breaking_changes = state.get("file_breaking_changes", [])

    if verified_callers:
        severity = (
            SEVERITY_CRITICAL
            if len(verified_callers) >= CRITICAL_CALLER_THRESHOLD
            else SEVERITY_WARNING
        )

        breaking_change = BreakingChange(
            entity_type=change.entity_type,
            entity_name=change.entity_name,
            class_name=change.class_name,
            file_path=change.file_path,
            change_type=change.change_type,
            old_definition=change.old_definition,
            new_definition=change.new_definition,
            change_detail=change.change_detail,
            line=change.line,
            affected_callers=verified_callers,
            severity=severity,
            recommendation=_generate_recommendation(change, verified_callers),
        )
        file_breaking_changes = [*file_breaking_changes, breaking_change]

        log.info(
            "verify_impact.breaking_change_created",
            entity=change.entity_name,
            severity=severity,
            affected_count=len(verified_callers),
        )

    return {
        "verified_callers": verified_callers,
        "need_more_search": need_more,
        "additional_queries": result.additional_queries if need_more else [],
        "file_breaking_changes": file_breaking_changes,
    }


def _format_search_results(results: list) -> str:
    """Format search results for the prompt."""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"### Result {i}: {r.file_path}:{r.line}")
        lines.append("```")
        lines.append(r.match_text)
        if r.context:
            lines.append(f"\n// Context:\n{r.context}")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _generate_recommendation(change, callers: list[AffectedCaller]) -> str:
    """Generate a recommendation based on the change type."""
    from ..constants import CHANGE_DELETED, CHANGE_SIGNATURE, CHANGE_VISIBILITY

    caller_count = len(callers)

    if change.change_type == CHANGE_SIGNATURE:
        return (
            f"Add a default value for the new parameter, or update all "
            f"{caller_count} caller(s) to pass the required argument."
        )
    elif change.change_type == CHANGE_DELETED:
        return (
            f"Restore the {change.entity_type} or update all "
            f"{caller_count} caller(s) to use an alternative."
        )
    elif change.change_type == CHANGE_VISIBILITY:
        return (
            f"Keep the {change.entity_type} public, or refactor "
            f"{caller_count} caller(s) to use a public API."
        )
    else:
        return f"Review and update all {caller_count} affected caller(s)."
