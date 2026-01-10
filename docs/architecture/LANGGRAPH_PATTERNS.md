# LangGraph Patterns for PR Review

> **Document Version**: 2.0  
> **Last Updated**: January 2026

## Table of Contents

1. [Pattern Overview](#pattern-overview)
2. [Orchestrator-Worker Pattern](#orchestrator-worker-pattern)
3. [Evaluator-Optimizer Pattern](#evaluator-optimizer-pattern)
4. [Routing Pattern](#routing-pattern)
5. [Service Integration Pattern](#service-integration-pattern)
6. [Error Handling Patterns](#error-handling-patterns)

---

## Pattern Overview

### Patterns Used in PR Review System

| Pattern | Where Used | Purpose |
|---------|------------|---------|
| **Orchestrator-Worker** | Function reviews | Parallel per-function review |
| **Routing** | Change classification | Route to appropriate review depth |
| **Evaluator-Optimizer** | Quality control | Validate and improve findings |
| **Service Integration** | External tools | Jira, Slack, static analysis |

---

## Orchestrator-Worker Pattern

### Concept

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR-WORKER PATTERN                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌─────────────────┐                                 │
│                         │  ORCHESTRATOR   │                                 │
│                         │  (route_review) │                                 │
│                         └────────┬────────┘                                 │
│                                  │                                          │
│                    ┌─────────────┼─────────────┐                            │
│                    │             │             │                            │
│                    ▼             ▼             ▼                            │
│             ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│             │ WORKER 1 │ │ WORKER 2 │ │ WORKER N │  (review_function)      │
│             │ func_a   │ │ func_b   │ │ func_n   │                         │
│             └────┬─────┘ └────┬─────┘ └────┬─────┘                         │
│                  │            │            │                                │
│                  └────────────┼────────────┘                                │
│                               │                                             │
│                               ▼                                             │
│                      ┌─────────────────┐                                    │
│                      │   AGGREGATOR    │                                    │
│                      │   (aggregate)   │                                    │
│                      └─────────────────┘                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Using Send() API

```python
# src/agents/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

def create_review_graph():
    graph = StateGraph(ReviewState)
    
    # Orchestrator node
    graph.add_node("route_review", route_review_node)
    
    # Worker node (will be called multiple times in parallel)
    graph.add_node("review_function", review_function_node)
    
    # Aggregator node
    graph.add_node("aggregate", aggregate_node)
    
    # Orchestrator decides how to fan out
    graph.add_conditional_edges(
        "route_review",
        orchestrate_workers,  # Returns list of Send objects
        ["review_function", "aggregate"]
    )
    
    # Workers fan back in
    graph.add_edge("review_function", "aggregate")
    
    return graph.compile()


def orchestrate_workers(state: ReviewState) -> list[Send]:
    """
    Orchestrator function that creates parallel worker tasks.
    
    Uses LangGraph's Send() API to spawn parallel executions.
    Each Send() creates an independent execution of the target node.
    """
    functions_to_review = state.get("functions_to_review", [])
    
    if not functions_to_review:
        # No work to do - skip to aggregator
        return [Send("aggregate", state)]
    
    # Create one worker per function
    workers = []
    for func in functions_to_review:
        # Each worker gets a copy of state with current_function set
        worker_state = {
            **state,
            "current_function": func,
        }
        workers.append(Send("review_function", worker_state))
    
    return workers


async def route_review_node(state: ReviewState) -> dict:
    """
    Orchestrator: Prepare work items for workers.
    
    Responsibilities:
    - Filter trivial changes
    - Classify review depth
    - Create work queue
    """
    changed_functions = state["changed_functions"]
    impact_report = state["impact_report"]
    
    functions_to_review = []
    
    for func in changed_functions:
        # Skip trivial
        if is_trivial_change(func):
            continue
        
        # Determine depth based on impact
        depth = "STANDARD"
        if func.name in impact_report.get("critical_functions", []):
            depth = "DEEP"
        
        functions_to_review.append({
            "function": func,
            "depth": depth,
            "context": build_function_context(func, state),
        })
    
    return {"functions_to_review": functions_to_review}


async def review_function_node(state: ReviewState) -> dict:
    """
    Worker: Review a single function.
    
    Receives current_function from orchestrator.
    Returns comments that get merged via operator.add.
    """
    task = state["current_function"]
    
    # Build targeted prompt
    prompt = build_review_prompt(task)
    
    # Call LLM
    response = await llm.ainvoke(prompt)
    
    # Parse findings
    comments = parse_findings(response, task["function"])
    
    # Return partial state - will be merged
    return {"comments": comments}


async def aggregate_node(state: ReviewState) -> dict:
    """
    Aggregator: Collect and process all worker outputs.
    
    Comments from all workers are automatically merged
    via operator.add annotation on the state field.
    """
    all_comments = state.get("comments", [])
    
    # Deduplicate
    unique = deduplicate_comments(all_comments)
    
    # Sort and limit
    final = sort_and_limit(unique)
    
    return {"final_comments": final}
```

### Benefits

| Benefit | Description |
|---------|-------------|
| **True Parallelism** | Each function reviewed concurrently |
| **Independent Failures** | One worker failing doesn't block others |
| **Automatic Merging** | `operator.add` handles result collection |
| **Scalable** | Add more workers without changing architecture |

---

## Evaluator-Optimizer Pattern

### Concept

The Evaluator-Optimizer pattern adds a quality control loop:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EVALUATOR-OPTIMIZER PATTERN                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    ┌─────────────────────────────────────┐                  │
│                    │                                     │                  │
│                    ▼                                     │                  │
│             ┌──────────────┐                            │                  │
│             │   GENERATE   │                            │                  │
│             │   (review)   │                            │                  │
│             └──────┬───────┘                            │                  │
│                    │                                     │                  │
│                    ▼                                     │                  │
│             ┌──────────────┐      ┌──────────────┐      │                  │
│             │   EVALUATE   │─────▶│   OPTIMIZE   │──────┘                  │
│             │   (check)    │ fail │   (refine)   │                         │
│             └──────┬───────┘      └──────────────┘                         │
│                    │ pass                                                   │
│                    ▼                                                        │
│             ┌──────────────┐                                               │
│             │    OUTPUT    │                                               │
│             └──────────────┘                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src/agents/nodes/quality_control.py
from langgraph.graph import StateGraph

def create_quality_controlled_review():
    """Create graph with evaluator-optimizer loop."""
    
    graph = StateGraph(ReviewState)
    
    # Generator
    graph.add_node("generate_review", generate_review_node)
    
    # Evaluator
    graph.add_node("evaluate_quality", evaluate_quality_node)
    
    # Optimizer
    graph.add_node("optimize_review", optimize_review_node)
    
    # Flow
    graph.add_edge("generate_review", "evaluate_quality")
    
    graph.add_conditional_edges(
        "evaluate_quality",
        should_optimize,
        {
            "pass": "output",
            "fail": "optimize_review",
        }
    )
    
    graph.add_edge("optimize_review", "generate_review")  # Loop back
    
    return graph.compile()


async def generate_review_node(state: ReviewState) -> dict:
    """Generate initial review findings."""
    task = state["current_function"]
    optimization_feedback = state.get("optimization_feedback")
    
    # Adjust prompt if we have feedback from optimizer
    prompt = build_review_prompt(task)
    if optimization_feedback:
        prompt += f"\n\nPREVIOUS ATTEMPT FEEDBACK:\n{optimization_feedback}"
    
    response = await llm.ainvoke(prompt)
    comments = parse_findings(response)
    
    return {"pending_comments": comments, "iteration": state.get("iteration", 0) + 1}


async def evaluate_quality_node(state: ReviewState) -> dict:
    """
    Evaluate quality of generated review.
    
    Checks:
    1. Evidence provided for high-severity findings
    2. No hallucinated line numbers
    3. Suggestions are actionable
    4. Not too many false positives
    """
    comments = state["pending_comments"]
    func = state["current_function"]["function"]
    
    issues = []
    
    for comment in comments:
        # Check: Line number exists in the code
        if not line_exists(comment.line, func.new_code):
            issues.append(f"Line {comment.line} doesn't exist in {func.name}")
        
        # Check: High severity has evidence
        if comment.severity in ["critical", "warning"] and not comment.evidence:
            issues.append(f"Finding at line {comment.line} lacks evidence")
        
        # Check: Suggestion is specific
        if comment.suggestion and is_generic_suggestion(comment.suggestion):
            issues.append(f"Suggestion at line {comment.line} is too generic")
    
    quality_score = 1.0 - (len(issues) / max(len(comments), 1))
    
    return {
        "quality_score": quality_score,
        "quality_issues": issues,
    }


def should_optimize(state: ReviewState) -> str:
    """Decide whether to optimize or accept."""
    # Accept if quality is good enough or max iterations reached
    if state["quality_score"] >= 0.8:
        return "pass"
    if state["iteration"] >= 3:
        return "pass"  # Give up after 3 tries
    return "fail"


async def optimize_review_node(state: ReviewState) -> dict:
    """
    Generate feedback to improve the review.
    
    Analyzes quality issues and provides specific guidance.
    """
    issues = state["quality_issues"]
    
    feedback = "Please address these issues in your next attempt:\n"
    for issue in issues:
        feedback += f"- {issue}\n"
    
    return {"optimization_feedback": feedback}
```

### Use Cases

| Use Case | What Gets Evaluated | Optimization Action |
|----------|---------------------|---------------------|
| Line validation | Comment line numbers | Remove invalid comments |
| Evidence checking | High-severity findings | Add code citations |
| Specificity | Generic suggestions | Make suggestions concrete |
| False positive detection | Suspicious patterns | Request verification |

---

## Routing Pattern

### Concept

Route different types of changes to different review strategies:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ROUTING PATTERN                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌─────────────────┐                                 │
│                         │     INPUT       │                                 │
│                         │  (PR changes)   │                                 │
│                         └────────┬────────┘                                 │
│                                  │                                          │
│                                  ▼                                          │
│                         ┌─────────────────┐                                 │
│                         │     ROUTER      │                                 │
│                         │  (classify)     │                                 │
│                         └────────┬────────┘                                 │
│                                  │                                          │
│              ┌───────────────────┼───────────────────┐                      │
│              │                   │                   │                      │
│              ▼                   ▼                   ▼                      │
│       ┌───────────┐       ┌───────────┐       ┌───────────┐                │
│       │   DEEP    │       │ STANDARD  │       │   SKIP    │                │
│       │  REVIEW   │       │  REVIEW   │       │ (no-op)   │                │
│       └───────────┘       └───────────┘       └───────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src/agents/nodes/router.py
from typing import Literal

class ChangeClassification:
    """Classification result for a code change."""
    change: FunctionChange
    route: Literal["deep", "standard", "skip"]
    reason: str
    priority: int


def create_routed_graph():
    graph = StateGraph(ReviewState)
    
    graph.add_node("classify", classify_changes_node)
    graph.add_node("deep_review", deep_review_node)
    graph.add_node("standard_review", standard_review_node)
    graph.add_node("merge", merge_results_node)
    
    # Router decides based on classification
    graph.add_conditional_edges(
        "classify",
        route_by_classification,
        {
            "deep_only": "deep_review",
            "standard_only": "standard_review",
            "mixed": "parallel_reviews",
            "none": "merge",
        }
    )
    
    return graph.compile()


async def classify_changes_node(state: ReviewState) -> dict:
    """
    Classify each change for routing.
    
    Classification Rules:
    - DEEP: Security-sensitive, payment, auth, breaking changes
    - STANDARD: Normal business logic
    - SKIP: Trivial (whitespace, comments, formatting)
    """
    classifications = []
    
    for func in state["changed_functions"]:
        classification = classify_function_change(func, state["impact_report"])
        classifications.append(classification)
    
    return {"classifications": classifications}


def classify_function_change(
    func: FunctionChange,
    impact: ImpactReport,
) -> ChangeClassification:
    """Classify a single function change."""
    
    # SKIP: Trivial changes
    if is_trivial_change(func):
        return ChangeClassification(
            change=func,
            route="skip",
            reason="Trivial change (whitespace/comments only)",
            priority=0,
        )
    
    # DEEP: Security-sensitive
    security_keywords = ['password', 'auth', 'token', 'secret', 'encrypt', 'payment']
    if any(kw in func.name.lower() or kw in func.file_path.lower() for kw in security_keywords):
        return ChangeClassification(
            change=func,
            route="deep",
            reason=f"Security-sensitive function",
            priority=1,
        )
    
    # DEEP: Breaking changes
    if func.name in [bc.function for bc in impact.breaking_changes]:
        return ChangeClassification(
            change=func,
            route="deep",
            reason="Contains breaking changes",
            priority=1,
        )
    
    # DEEP: Many callers
    if len(impact.callers.get(func.name, [])) > 10:
        return ChangeClassification(
            change=func,
            route="deep",
            reason=f"High impact: {len(impact.callers[func.name])} callers",
            priority=2,
        )
    
    # STANDARD: Everything else
    return ChangeClassification(
        change=func,
        route="standard",
        reason="Normal business logic change",
        priority=3,
    )


def route_by_classification(state: ReviewState) -> str:
    """Determine routing path based on classifications."""
    classifications = state["classifications"]
    
    routes = set(c.route for c in classifications if c.route != "skip")
    
    if not routes:
        return "none"
    if routes == {"deep"}:
        return "deep_only"
    if routes == {"standard"}:
        return "standard_only"
    return "mixed"
```

### Decision Tree

```
                        Is it trivial?
                             │
                    ┌────────┴────────┐
                   YES               NO
                    │                 │
                  SKIP          Is it security-sensitive?
                                     │
                            ┌────────┴────────┐
                           YES               NO
                            │                 │
                          DEEP         Is it breaking?
                                            │
                                   ┌────────┴────────┐
                                  YES               NO
                                   │                 │
                                 DEEP          Many callers?
                                                    │
                                           ┌────────┴────────┐
                                          YES               NO
                                           │                 │
                                         DEEP           STANDARD
```

---

## Service Integration Pattern

### Multi-Service Orchestration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SERVICE INTEGRATION PATTERN                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        LANGGRAPH WORKFLOW                            │    │
│  │                                                                       │    │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐    │    │
│  │  │ GitHub │──▶│ Static │──▶│  Jira  │──▶│ Review │──▶│ Slack  │    │    │
│  │  │ Fetch  │   │Analysis│   │ Context│   │  LLM   │   │ Notify │    │    │
│  │  └────────┘   └────────┘   └────────┘   └────────┘   └────────┘    │    │
│  │       │            │            │            │            │         │    │
│  │       ▼            ▼            ▼            ▼            ▼         │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                     SHARED STATE                             │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  │                                                                       │    │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      EXTERNAL SERVICES                                │  │
│  │                                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │  GitHub  │  │  Ruff/   │  │   Jira   │  │  Slack   │              │  │
│  │  │   API    │  │  Pylint  │  │   API    │  │   API    │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src/agents/integrations/service_nodes.py
from dataclasses import dataclass
from typing import Optional
import httpx

@dataclass
class ServiceResult:
    """Result from an external service call."""
    success: bool
    data: dict
    error: Optional[str] = None


class ServiceIntegrationNodes:
    """Nodes for external service integration."""
    
    def __init__(self, config: dict):
        self.github = GitHubClient(config["github_token"])
        self.jira = JiraClient(config.get("jira_url"), config.get("jira_token"))
        self.slack = SlackClient(config.get("slack_webhook"))
        self.static_analyzer = StaticAnalyzer()
    
    async def fetch_github_context(self, state: ReviewState) -> dict:
        """
        Fetch comprehensive context from GitHub.
        
        Gathers:
        - PR details
        - File contents (both branches)
        - PR comments/discussion
        - Related PRs (if any)
        """
        pr = state["pr_context"]
        
        # Fetch in parallel
        pr_details, files, comments = await asyncio.gather(
            self.github.get_pr(pr.owner, pr.repo, pr.number),
            self.github.get_pr_files(pr.owner, pr.repo, pr.number),
            self.github.get_pr_comments(pr.owner, pr.repo, pr.number),
        )
        
        return {
            "pr_details": pr_details,
            "files": files,
            "existing_comments": comments,
        }
    
    async def run_static_analysis(self, state: ReviewState) -> dict:
        """
        Run static analysis tools on changed files.
        
        Tools:
        - Ruff (Python linting)
        - Type checking (if enabled)
        - Security scanning
        """
        results = []
        
        for file in state["changed_files"]:
            if file.path.endswith(".py"):
                # Run Ruff
                ruff_result = await self.static_analyzer.run_ruff(file.head_content)
                results.extend(ruff_result.findings)
                
                # Run type check
                type_result = await self.static_analyzer.run_pyright(file.head_content)
                results.extend(type_result.findings)
        
        return {"static_analysis_results": results}
    
    async def fetch_jira_context(self, state: ReviewState) -> dict:
        """
        Fetch related Jira ticket information.
        
        Extracts ticket ID from PR title/branch name.
        Provides acceptance criteria and context.
        """
        pr = state["pr_context"]
        
        # Extract ticket ID (e.g., "PROJ-123" from "feature/PROJ-123-add-rewards")
        ticket_id = self._extract_ticket_id(pr.head_branch, pr.title)
        
        if not ticket_id:
            return {"jira_context": None}
        
        try:
            ticket = await self.jira.get_ticket(ticket_id)
            return {
                "jira_context": {
                    "ticket_id": ticket_id,
                    "summary": ticket.summary,
                    "description": ticket.description,
                    "acceptance_criteria": ticket.acceptance_criteria,
                    "story_points": ticket.story_points,
                }
            }
        except JiraError:
            return {"jira_context": None}
    
    async def notify_slack(self, state: ReviewState) -> dict:
        """
        Send review completion notification to Slack.
        
        Includes:
        - PR link
        - Summary of findings
        - Severity breakdown
        """
        if not self.slack.is_configured():
            return {"slack_notified": False}
        
        comments = state.get("final_comments", [])
        
        message = self._build_slack_message(state["pr_context"], comments)
        
        try:
            await self.slack.send_message(message)
            return {"slack_notified": True}
        except SlackError:
            return {"slack_notified": False}
    
    def _extract_ticket_id(self, branch: str, title: str) -> Optional[str]:
        """Extract Jira ticket ID from branch or title."""
        import re
        pattern = r'([A-Z]+-\d+)'
        
        for text in [branch, title]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None


def create_integrated_graph(config: dict):
    """Create graph with full service integration."""
    
    services = ServiceIntegrationNodes(config)
    graph = StateGraph(ReviewState)
    
    # Service integration nodes
    graph.add_node("fetch_github", services.fetch_github_context)
    graph.add_node("static_analysis", services.run_static_analysis)
    graph.add_node("fetch_jira", services.fetch_jira_context)
    graph.add_node("notify_slack", services.notify_slack)
    
    # Analysis nodes
    graph.add_node("extract_diff", extract_diff_node)
    graph.add_node("build_call_graph", build_call_graph_node)
    graph.add_node("review", review_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("publish_github", publish_github_node)
    
    # Flow: Parallel fetch → Sequential analysis → Parallel output
    graph.add_edge(START, "fetch_github")
    
    # Parallel: static analysis + jira fetch while building call graph
    graph.add_edge("fetch_github", "extract_diff")
    graph.add_edge("extract_diff", "build_call_graph")
    
    # These can run in parallel with build_call_graph
    graph.add_edge("fetch_github", "static_analysis")
    graph.add_edge("fetch_github", "fetch_jira")
    
    # Sync point: wait for all before review
    graph.add_edge("build_call_graph", "review")
    graph.add_edge("static_analysis", "review")
    graph.add_edge("fetch_jira", "review")
    
    # After review
    graph.add_edge("review", "aggregate")
    
    # Parallel output
    graph.add_edge("aggregate", "publish_github")
    graph.add_edge("aggregate", "notify_slack")
    
    graph.add_edge("publish_github", END)
    graph.add_edge("notify_slack", END)
    
    return graph.compile()
```

### Handling Async Callbacks

```python
# src/agents/integrations/async_handler.py

class AsyncServiceHandler:
    """Handle async operations and callbacks from external services."""
    
    def __init__(self):
        self.pending_operations = {}
    
    async def submit_and_wait(
        self,
        service: str,
        operation: Callable,
        timeout: float = 30.0,
    ) -> ServiceResult:
        """
        Submit operation and wait for completion.
        
        Handles:
        - Timeout
        - Retries
        - Circuit breaking
        """
        operation_id = str(uuid.uuid4())
        
        try:
            async with asyncio.timeout(timeout):
                result = await operation()
                return ServiceResult(success=True, data=result)
        except asyncio.TimeoutError:
            return ServiceResult(
                success=False,
                data={},
                error=f"{service} operation timed out after {timeout}s"
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                data={},
                error=str(e)
            )
    
    async def submit_with_callback(
        self,
        service: str,
        operation: Callable,
        callback_url: str,
    ) -> str:
        """
        Submit operation with webhook callback.
        
        For long-running operations that use webhooks.
        Returns operation ID for tracking.
        """
        operation_id = str(uuid.uuid4())
        
        # Register pending operation
        self.pending_operations[operation_id] = {
            "service": service,
            "status": "pending",
            "submitted_at": datetime.now(),
        }
        
        # Submit operation (non-blocking)
        await operation(callback_url=callback_url, operation_id=operation_id)
        
        return operation_id
    
    async def handle_callback(self, operation_id: str, result: dict):
        """Handle callback from external service."""
        if operation_id in self.pending_operations:
            self.pending_operations[operation_id]["status"] = "completed"
            self.pending_operations[operation_id]["result"] = result
```

---

## Error Handling Patterns

### Graceful Degradation

```python
# src/agents/error_handling.py

from langgraph.errors import NodeInterrupt

class ErrorHandlingMixin:
    """Mixin for graceful error handling in nodes."""
    
    @staticmethod
    def with_fallback(fallback_value):
        """Decorator that returns fallback on error."""
        def decorator(func):
            async def wrapper(state):
                try:
                    return await func(state)
                except Exception as e:
                    logger.error(f"Node {func.__name__} failed: {e}")
                    return fallback_value
            return wrapper
        return decorator
    
    @staticmethod
    def with_retry(max_attempts: int = 3, backoff: float = 1.0):
        """Decorator that retries on failure."""
        def decorator(func):
            async def wrapper(state):
                last_error = None
                for attempt in range(max_attempts):
                    try:
                        return await func(state)
                    except Exception as e:
                        last_error = e
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(backoff * (2 ** attempt))
                raise last_error
            return wrapper
        return decorator


# Usage in nodes
@ErrorHandlingMixin.with_fallback({"static_analysis_results": []})
async def run_static_analysis(state: ReviewState) -> dict:
    """Static analysis with graceful degradation."""
    # If this fails, we continue without static analysis results
    pass


@ErrorHandlingMixin.with_retry(max_attempts=3)
async def publish_to_github(state: ReviewState) -> dict:
    """GitHub publish with retry."""
    # Important operation - retry on failure
    pass
```

### Circuit Breaker Pattern

```python
# src/agents/circuit_breaker.py

class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func: Callable) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen("Circuit breaker is open")
        
        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failures = 0
        self.state = "closed"
    
    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"


# Usage
github_breaker = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)

async def fetch_with_protection(state: ReviewState) -> dict:
    try:
        result = await github_breaker.call(
            lambda: github.get_pr_files(...)
        )
        return {"files": result}
    except CircuitBreakerOpen:
        # Fall back to cached data or skip
        return {"files": [], "fallback_used": True}
```

---

## Summary

### Pattern Selection Guide

| Scenario | Pattern | Why |
|----------|---------|-----|
| Review multiple functions | Orchestrator-Worker | True parallelism |
| Ensure quality | Evaluator-Optimizer | Quality loop |
| Different review depths | Routing | Conditional logic |
| External services | Service Integration | Abstracted calls |
| Handle failures | Circuit Breaker | Graceful degradation |

### Key Implementation Notes

1. **Use Send() for parallelism**: LangGraph's Send API enables true parallel execution
2. **State merging**: Use `operator.add` for automatic result collection
3. **Graceful degradation**: External service failures shouldn't block reviews
4. **Timeouts everywhere**: All external calls should have timeouts
5. **Circuit breakers**: Protect against cascading failures
