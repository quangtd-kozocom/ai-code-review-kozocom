"""Plan search node - LLM decides search queries."""

import structlog

from ...core.llm import get_structured_llm
from ..models import SearchPlanResult
from ..prompts.plan_search import PLAN_SEARCH_PROMPT
from ..state import ReviewState, SearchPlan

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Plan search queries for finding callers.

    The LLM decides what queries to use based on the entity type,
    language, and change details.

    Args:
        state: Current workflow state with current_change.

    Returns:
        State updates with search_plan.
    """
    change = state.get("current_change")

    if not change:
        log.debug("plan_search.skipped", reason="no current_change")
        return {"search_plan": None}

    # Check if we're refining search (additional queries from verify_impact)
    additional = state.get("additional_queries", [])
    if additional:
        prev_plan = state.get("search_plan")
        iteration = state.get("search_iteration", 0) + 1

        log.info(
            "plan_search.refining",
            entity=change.entity_name,
            iteration=iteration,
            additional_queries=additional,
        )

        return {
            "search_plan": SearchPlan(
                queries=additional,
                include_patterns=prev_plan.include_patterns if prev_plan else [],
                exclude_patterns=prev_plan.exclude_patterns if prev_plan else [],
                reasoning="Refined search based on verification feedback",
            ),
            "additional_queries": [],
            "search_iteration": iteration,
        }

    log.info(
        "plan_search.started",
        entity=change.entity_name,
        entity_type=change.entity_type,
        language=change.language,
        change_type=change.change_type,
    )

    # Prepare prompt
    prompt = PLAN_SEARCH_PROMPT.format(
        entity_type=change.entity_type,
        entity_name=change.entity_name,
        class_name=change.class_name or "N/A",
        language=change.language,
        file_path=change.file_path,
        change_type=change.change_type,
        change_detail=change.change_detail,
        old_definition=change.old_definition or "(none)",
        new_definition=change.new_definition or "(none)",
    )

    # Call LLM
    llm = get_structured_llm(SearchPlanResult)

    try:
        result: SearchPlanResult = await llm.ainvoke(prompt)
        log.debug(
            "plan_search.llm_response",
            entity=change.entity_name,
            queries=result.queries,
            reasoning=result.reasoning,
        )
    except Exception as e:
        log.error(
            "plan_search.llm_error",
            entity=change.entity_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Fallback to simple search
        log.info("plan_search.using_fallback", entity=change.entity_name)
        return {
            "search_plan": SearchPlan(
                queries=[change.entity_name],
                include_patterns=["*"],
                exclude_patterns=["*test*", "*vendor*", "*node_modules*"],
                reasoning="Fallback due to LLM error",
            ),
            "search_iteration": 1,
        }

    search_plan = SearchPlan(
        queries=result.queries,
        include_patterns=result.include_patterns,
        exclude_patterns=result.exclude_patterns,
        reasoning=result.reasoning,
    )

    log.info(
        "plan_search.complete",
        entity=change.entity_name,
        queries=search_plan.queries,
        include_patterns=search_plan.include_patterns,
        exclude_patterns=search_plan.exclude_patterns,
    )

    return {
        "search_plan": search_plan,
        "search_iteration": 1,
    }
