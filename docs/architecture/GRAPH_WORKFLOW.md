# LangGraph Workflow Design

> **Document Version**: 2.0  
> **Last Updated**: January 2026

## Table of Contents

1. [Graph Overview](#graph-overview)
2. [Node Structure](#node-structure)
3. [State Management](#state-management)
4. [Edge Logic](#edge-logic)
5. [Example Flow](#example-flow)

---

## Graph Overview

### Visual Representation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PR REVIEW GRAPH v2                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌─────────────┐                                   │
│                           │   START     │                                   │
│                           └──────┬──────┘                                   │
│                                  │                                          │
│                                  ▼                                          │
│                      ┌───────────────────────┐                              │
│                      │   1. extract_diff     │  ← Phase 1 (Deterministic)   │
│                      │   (No LLM)            │                              │
│                      └───────────┬───────────┘                              │
│                                  │                                          │
│                                  ▼                                          │
│                      ┌───────────────────────┐                              │
│                      │  2. build_call_graph  │  ← Phase 2 (AST Analysis)    │
│                      │   (No LLM)            │                              │
│                      └───────────┬───────────┘                              │
│                                  │                                          │
│                                  ▼                                          │
│                      ┌───────────────────────┐                              │
│                      │  3. analyze_impact    │                              │
│                      │   (No LLM)            │                              │
│                      └───────────┬───────────┘                              │
│                                  │                                          │
│                                  ▼                                          │
│                      ┌───────────────────────┐                              │
│                      │  4. route_review      │  ← Phase 3 (LLM-based)       │
│                      │   (LLM routing)       │                              │
│                      └───────────┬───────────┘                              │
│                                  │                                          │
│                     ┌────────────┼────────────┐                             │
│                     ▼            ▼            ▼                             │
│              ┌───────────┐┌───────────┐┌───────────┐                        │
│              │  review   ││  review   ││  review   │  ← Parallel Workers    │
│              │  func_1   ││  func_2   ││  func_N   │                        │
│              └─────┬─────┘└─────┬─────┘└─────┬─────┘                        │
│                    │            │            │                              │
│                    └────────────┼────────────┘                              │
│                                 ▼                                           │
│                      ┌───────────────────────┐                              │
│                      │  5. aggregate         │                              │
│                      └───────────┬───────────┘                              │
│                                  │                                          │
│                     ┌────────────┴────────────┐                             │
│                     ▼                         ▼                             │
│              ┌───────────┐             ┌───────────┐                        │
│              │  publish  │             │  notify   │  ← Parallel Output     │
│              │  github   │             │  slack    │                        │
│              └───────────┘             └───────────┘                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Graph Definition Code

```python
# src/agents/graph.py
from langgraph.graph import StateGraph, END, START
from langgraph.types import Send

from .state import ReviewState
from .nodes import (
    extract_diff,
    build_call_graph,
    analyze_impact,
    route_review,
    review_function,
    aggregate_findings,
    publish_to_github,
    notify_slack,
)


def create_review_graph() -> StateGraph:
    """Create the PR review workflow graph."""
    
    graph = StateGraph(ReviewState)
    
    # Phase 1: Diff Analysis
    graph.add_node("extract_diff", extract_diff)
    
    # Phase 2: Impact Analysis
    graph.add_node("build_call_graph", build_call_graph)
    graph.add_node("analyze_impact", analyze_impact)
    
    # Phase 3: Review
    graph.add_node("route_review", route_review)
    graph.add_node("review_function", review_function)
    graph.add_node("aggregate", aggregate_findings)
    
    # Output
    graph.add_node("publish_github", publish_to_github)
    graph.add_node("notify_slack", notify_slack)
    
    # Define edges
    graph.add_edge(START, "extract_diff")
    graph.add_edge("extract_diff", "build_call_graph")
    graph.add_edge("build_call_graph", "analyze_impact")
    graph.add_edge("analyze_impact", "route_review")
    
    # Conditional: Fan-out to parallel function reviews
    graph.add_conditional_edges(
        "route_review",
        fan_out_to_reviews,
        ["review_function", "aggregate"]  # If no functions, skip to aggregate
    )
    
    # Fan-in: Collect all reviews
    graph.add_edge("review_function", "aggregate")
    
    # Parallel output
    graph.add_edge("aggregate", "publish_github")
    graph.add_edge("aggregate", "notify_slack")
    graph.add_edge("publish_github", END)
    graph.add_edge("notify_slack", END)
    
    return graph.compile()


def fan_out_to_reviews(state: ReviewState) -> list[Send]:
    """Route to parallel function reviews using Send API."""
    functions_to_review = state.get("functions_to_review", [])
    
    if not functions_to_review:
        return [Send("aggregate", state)]
    
    return [
        Send("review_function", {**state, "current_function": func})
        for func in functions_to_review
    ]
```

---

## Node Structure

### Node 1: extract_diff

**Purpose**: Parse PR diff and identify changed code units.

```python
# src/agents/nodes/extract_diff.py
from dataclasses import dataclass
from ..state import ReviewState
from ...analysis.diff_extractor import DiffExtractor
from ...analysis.ast_analyzer import ASTAnalyzer


@dataclass
class ExtractDiffInput:
    """Input schema for extract_diff node."""
    pr_context: PRContext  # owner, repo, pr_number, base_branch, head_branch


@dataclass
class ExtractDiffOutput:
    """Output schema for extract_diff node."""
    changed_files: list[ChangedFile]
    changed_functions: list[FunctionChange]
    new_files: list[str]
    deleted_files: list[str]


async def extract_diff(state: ReviewState) -> dict:
    """
    Extract structured diff information from PR.
    
    Process:
    1. Fetch PR files from GitHub API
    2. For each modified file:
       - Fetch content from both branches
       - Parse with tree-sitter
       - Identify changed functions
    3. Return structured change list
    
    No LLM calls - purely deterministic.
    """
    pr = state["pr_context"]
    extractor = DiffExtractor(github_token=state["github_token"])
    analyzer = ASTAnalyzer()
    
    # Get PR files
    pr_files = await extractor.get_pr_files(pr.owner, pr.repo, pr.number)
    
    changed_functions = []
    changed_files = []
    
    for file in pr_files:
        if file.status == "removed":
            continue
            
        # Fetch both versions
        base_content = await extractor.get_file_content(
            pr.owner, pr.repo, file.path, pr.base_branch
        )
        head_content = await extractor.get_file_content(
            pr.owner, pr.repo, file.path, pr.head_branch
        )
        
        # Parse and compare
        base_functions = analyzer.extract_functions(base_content, file.language)
        head_functions = analyzer.extract_functions(head_content, file.language)
        
        # Find changes
        changes = analyzer.diff_functions(base_functions, head_functions)
        changed_functions.extend(changes)
        
        changed_files.append(ChangedFile(
            path=file.path,
            status=file.status,
            patch=file.patch,
            base_content=base_content,
            head_content=head_content,
        ))
    
    return {
        "changed_files": changed_files,
        "changed_functions": changed_functions,
        "new_files": [f.path for f in pr_files if f.status == "added"],
        "deleted_files": [f.path for f in pr_files if f.status == "removed"],
    }
```

### Node 2: build_call_graph

**Purpose**: Build call relationships for changed functions.

```python
# src/agents/nodes/build_call_graph.py

async def build_call_graph(state: ReviewState) -> dict:
    """
    Build call graph for changed functions.
    
    Process:
    1. For each changed function, find:
       - Functions that call it (callers)
       - Functions it calls (callees)
    2. Get context around each call site
    3. Build bi-directional graph
    
    Uses AST queries - no LLM calls.
    """
    pr = state["pr_context"]
    changed_functions = state["changed_functions"]
    
    # Fetch relevant files from base branch (where callers exist)
    graph_builder = CallGraphBuilder()
    repo_files = await fetch_source_files(pr.owner, pr.repo, pr.base_branch)
    
    call_graph = {}
    
    for func in changed_functions:
        # Find callers in the codebase
        callers = graph_builder.find_callers(func.name, repo_files)
        
        # Find callees from the function's code
        callees = graph_builder.extract_calls(func.new_code or func.old_code)
        
        call_graph[func.name] = CallRelationships(
            function=func,
            callers=callers,
            callees=callees,
        )
    
    return {"call_graph": call_graph}
```

### Node 3: analyze_impact

**Purpose**: Determine the impact of changes.

```python
# src/agents/nodes/analyze_impact.py

async def analyze_impact(state: ReviewState) -> dict:
    """
    Analyze impact of code changes.
    
    Checks:
    1. Signature compatibility (breaking changes)
    2. Return type changes
    3. Missing test coverage
    4. Affected downstream functions
    
    Deterministic analysis - no LLM.
    """
    changed_functions = state["changed_functions"]
    call_graph = state["call_graph"]
    
    impact_analyzer = ImpactAnalyzer()
    impact_report = ImpactReport()
    
    for func in changed_functions:
        # Check signature changes
        if func.change_type == "modified":
            sig_diff = impact_analyzer.compare_signatures(
                func.old_signature, 
                func.new_signature
            )
            if sig_diff.is_breaking:
                impact_report.breaking_changes.append(BreakingChange(
                    function=func.name,
                    reason=sig_diff.reason,
                    affected_callers=call_graph[func.name].callers,
                ))
        
        # Check test coverage
        test_info = impact_analyzer.find_tests(func.name, state["changed_files"])
        impact_report.test_coverage[func.name] = test_info
    
    return {"impact_report": impact_report}
```

### Node 4: route_review

**Purpose**: Decide which functions need deep review and route accordingly.

```python
# src/agents/nodes/route_review.py
from langchain_core.messages import HumanMessage

async def route_review(state: ReviewState) -> dict:
    """
    Route functions to appropriate review depth.
    
    Uses LLM to classify:
    - DEEP: Complex logic, security-sensitive, high-impact
    - STANDARD: Normal business logic
    - SKIP: Trivial changes (formatting, comments)
    
    This is the first LLM call in the pipeline.
    """
    changed_functions = state["changed_functions"]
    impact_report = state["impact_report"]
    
    # Quick filter: skip obvious non-issues
    functions_to_review = []
    
    for func in changed_functions:
        # Skip trivial changes
        if is_trivial_change(func):
            continue
        
        # Flag high-impact for deep review
        review_depth = "STANDARD"
        if func.name in [bc.function for bc in impact_report.breaking_changes]:
            review_depth = "DEEP"
        elif contains_security_patterns(func.new_code):
            review_depth = "DEEP"
        
        functions_to_review.append(FunctionReviewTask(
            function=func,
            depth=review_depth,
            callers=state["call_graph"].get(func.name, {}).get("callers", []),
        ))
    
    return {"functions_to_review": functions_to_review}


def is_trivial_change(func: FunctionChange) -> bool:
    """Detect trivial changes that don't need review."""
    if func.change_type == "modified":
        # Only whitespace/comment changes
        old_normalized = normalize_code(func.old_code)
        new_normalized = normalize_code(func.new_code)
        return old_normalized == new_normalized
    return False
```

### Node 5: review_function

**Purpose**: Review a single function with full context.

```python
# src/agents/nodes/review_function.py

async def review_function(state: ReviewState) -> dict:
    """
    Review a single function with targeted context.
    
    Provides LLM with:
    - Before/after code
    - Exact diff
    - Callers with context
    - Related tests
    - Specific questions based on change type
    """
    task = state["current_function"]
    func = task.function
    
    # Build targeted context
    context = ContextBuilder().build(
        function=func,
        callers=task.callers,
        tests=state["impact_report"].test_coverage.get(func.name),
        depth=task.depth,
    )
    
    # Generate review with structured output
    prompt = build_review_prompt(context)
    
    response = await llm.with_structured_output(ReviewFindings).ainvoke(prompt)
    
    # Convert to review comments
    comments = [
        ReviewComment(
            file=func.file_path,
            line=finding.line,
            severity=finding.severity,
            message=finding.message,
            suggestion=finding.suggestion,
        )
        for finding in response.findings
    ]
    
    return {"comments": comments}  # Automatically merged via operator.add
```

### Node 6: aggregate

**Purpose**: Deduplicate and prioritize findings.

```python
# src/agents/nodes/aggregate.py

async def aggregate_findings(state: ReviewState) -> dict:
    """
    Aggregate all review comments.
    
    Process:
    1. Deduplicate by (file, line, message_hash)
    2. Sort by severity (critical > warning > info)
    3. Apply per-file limit
    4. Generate summary
    """
    comments = state.get("comments", [])
    config = state.get("repo_config", {})
    
    # Deduplicate
    seen = set()
    unique_comments = []
    for comment in comments:
        key = (comment.file, comment.line, hash(comment.message))
        if key not in seen:
            seen.add(key)
            unique_comments.append(comment)
    
    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}
    unique_comments.sort(key=lambda c: severity_order.get(c.severity, 99))
    
    # Apply limit
    max_per_file = config.get("max_comments_per_file", 10)
    limited = apply_per_file_limit(unique_comments, max_per_file)
    
    # Generate summary
    summary = generate_summary(limited, state["impact_report"])
    
    return {
        "final_comments": limited,
        "summary": summary,
    }
```

---

## State Management

### State Schema Definition

```python
# src/agents/state.py
from typing import TypedDict, Annotated
from dataclasses import dataclass
import operator


@dataclass
class PRContext:
    """PR metadata from webhook."""
    owner: str
    repo: str
    number: int
    base_branch: str  # Target branch (e.g., staging_new)
    head_branch: str  # Source branch (e.g., feature/rewards)
    author: str
    title: str
    installation_id: int


@dataclass
class FunctionChange:
    """Represents a changed function."""
    name: str
    file_path: str
    change_type: str  # "added" | "modified" | "deleted"
    old_code: str | None
    new_code: str | None
    old_signature: str | None
    new_signature: str | None
    line_range: tuple[int, int]


@dataclass
class CallerInfo:
    """Information about a function that calls another."""
    function_name: str
    file_path: str
    line_number: int
    context_code: str  # 5 lines around call site


@dataclass
class ReviewComment:
    """A review comment to post."""
    file: str
    line: int
    severity: str  # "critical" | "warning" | "info" | "suggestion"
    message: str
    suggestion: str | None


class ReviewState(TypedDict):
    """
    Complete state for the review workflow.
    
    State flows through nodes, each adding their output.
    Comments use operator.add for automatic merging from parallel reviews.
    """
    # Input (set at start)
    pr_context: PRContext
    github_token: str
    repo_config: dict
    
    # Phase 1 output
    changed_files: list[dict]
    changed_functions: list[FunctionChange]
    new_files: list[str]
    deleted_files: list[str]
    
    # Phase 2 output
    call_graph: dict[str, dict]  # function_name -> {callers, callees}
    impact_report: dict
    
    # Phase 3 intermediate
    functions_to_review: list[dict]
    current_function: dict | None  # Set during fan-out
    
    # Phase 3 output (merged from parallel)
    comments: Annotated[list[ReviewComment], operator.add]
    
    # Final output
    final_comments: list[ReviewComment]
    summary: str
    published: bool
    notified: bool
```

### State Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STATE EVOLUTION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Initial State (from webhook):                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ pr_context: {owner, repo, number, base_branch, head_branch, ...}    │    │
│  │ github_token: "ghp_xxx"                                              │    │
│  │ repo_config: {...}                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼ extract_diff                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ + changed_files: [{path, status, patch, base_content, head_content}]│    │
│  │ + changed_functions: [{name, file_path, change_type, old/new_code}] │    │
│  │ + new_files: ["rewards/models.py"]                                   │    │
│  │ + deleted_files: []                                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼ build_call_graph                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ + call_graph: {                                                      │    │
│  │     "calculate_rewards": {                                           │    │
│  │       "callers": [{fn: "process_order", file: "...", line: 45}],    │    │
│  │       "callees": ["get_user", "apply_multiplier"]                   │    │
│  │     }                                                                │    │
│  │   }                                                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼ analyze_impact                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ + impact_report: {                                                   │    │
│  │     "breaking_changes": [],                                          │    │
│  │     "warnings": [{type: "unused_param", ...}],                      │    │
│  │     "test_coverage": {"calculate_rewards": {covered: true}}         │    │
│  │   }                                                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼ route_review                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ + functions_to_review: [                                             │    │
│  │     {function: {...}, depth: "DEEP", callers: [...]},               │    │
│  │     {function: {...}, depth: "STANDARD", callers: [...]}            │    │
│  │   ]                                                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                    ┌────────────────┴────────────────┐                      │
│                    ▼                                 ▼                       │
│  ┌──────────────────────────┐    ┌──────────────────────────┐               │
│  │ review_function (func_1) │    │ review_function (func_2) │  PARALLEL     │
│  │ + comments: [{...}]      │    │ + comments: [{...}]      │               │
│  └──────────────────────────┘    └──────────────────────────┘               │
│                    │                                 │                       │
│                    └────────────────┬────────────────┘                      │
│                                     │ (operator.add merges comments)         │
│                                     ▼ aggregate                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ + comments: [{...}, {...}, {...}]  ← Merged from all review_function│    │
│  │ + final_comments: [{...}, {...}]   ← Deduplicated, sorted           │    │
│  │ + summary: "Found 2 issues..."                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                    ┌────────────────┴────────────────┐                      │
│                    ▼                                 ▼                       │
│  ┌──────────────────────────┐    ┌──────────────────────────┐               │
│  │ publish_github           │    │ notify_slack             │  PARALLEL     │
│  │ + published: true        │    │ + notified: true         │               │
│  └──────────────────────────┘    └──────────────────────────┘               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Edge Logic

### Conditional Routing Rules

```python
# Edge conditions

def should_skip_review(state: ReviewState) -> str:
    """Determine if review should be skipped entirely."""
    pr = state["pr_context"]
    config = state.get("repo_config", {})
    
    # Skip draft PRs
    if pr.is_draft and not config.get("review_drafts", False):
        return "skip"
    
    # Skip based on author
    if pr.author in config.get("ignore_authors", []):
        return "skip"
    
    # Skip based on title keywords
    skip_keywords = config.get("skip_keywords", ["[skip-review]", "WIP"])
    if any(kw.lower() in pr.title.lower() for kw in skip_keywords):
        return "skip"
    
    return "continue"


def fan_out_to_reviews(state: ReviewState) -> list[Send]:
    """
    Fan out to parallel function reviews.
    
    Uses LangGraph's Send API for true parallelism.
    Each function gets its own review_function invocation.
    """
    functions = state.get("functions_to_review", [])
    
    if not functions:
        # No functions to review - go directly to aggregate
        return [Send("aggregate", state)]
    
    # Create parallel tasks
    sends = []
    for func in functions:
        sends.append(Send("review_function", {
            **state,
            "current_function": func,
        }))
    
    return sends


def route_after_aggregate(state: ReviewState) -> list[str]:
    """Determine which output nodes to run."""
    outputs = []
    config = state.get("repo_config", {})
    
    # Always publish to GitHub
    outputs.append("publish_github")
    
    # Conditionally notify Slack
    if config.get("slack_webhook") and state.get("final_comments"):
        outputs.append("notify_slack")
    
    return outputs
```

### Error Handling

```python
# src/agents/nodes/error_handling.py

from langgraph.errors import NodeInterrupt

async def review_function_with_retry(state: ReviewState) -> dict:
    """Review function with error handling and retry."""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            return await review_function(state)
        except RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            # Last attempt failed - return empty to not block others
            return {"comments": []}
        except Exception as e:
            logger.error(f"Review failed: {e}")
            return {"comments": []}


# Graph-level error handling
def create_graph_with_error_handling():
    graph = StateGraph(ReviewState)
    
    # ... add nodes ...
    
    # Add error boundary
    graph.add_node("error_handler", handle_error)
    
    # On any node failure, route to error handler
    for node in ["extract_diff", "build_call_graph", "review_function"]:
        graph.add_conditional_edges(
            node,
            lambda state: "error" if state.get("error") else "continue",
            {"error": "error_handler", "continue": get_next_node(node)}
        )
    
    return graph.compile()
```

---

## Example Flow

### Scenario: `feature/rewards-program` → `staging_new`

```
Changed files:
- rewards/calculator.py (modified)
- rewards/models.py (new file)  
- tests/test_rewards.py (modified)
```

### Step-by-Step Walkthrough

#### Step 1: Webhook Received

```json
// GitHub webhook payload
{
  "action": "opened",
  "pull_request": {
    "number": 42,
    "title": "Add rewards multiplier feature",
    "head": {"ref": "feature/rewards-program", "sha": "abc123"},
    "base": {"ref": "staging_new", "sha": "def456"},
    "user": {"login": "developer"},
    "draft": false
  },
  "repository": {
    "owner": {"login": "company"},
    "name": "backend"
  }
}
```

#### Step 2: extract_diff Node

```python
# Input state
{
    "pr_context": PRContext(
        owner="company",
        repo="backend",
        number=42,
        base_branch="staging_new",
        head_branch="feature/rewards-program",
        author="developer",
        title="Add rewards multiplier feature",
    ),
    "github_token": "ghp_xxx",
}

# Processing
# 1. GET /repos/company/backend/pulls/42/files
# 2. For rewards/calculator.py:
#    - GET content from staging_new branch
#    - GET content from feature/rewards-program branch
#    - Parse both with tree-sitter
#    - Compare function lists

# Output added to state
{
    "changed_functions": [
        FunctionChange(
            name="calculate_rewards",
            file_path="rewards/calculator.py",
            change_type="modified",
            old_code="def calculate_rewards(user_id: int) -> float:\n    ...",
            new_code="def calculate_rewards(user_id: int, multiplier: float = 1.0) -> float:\n    ...",
            old_signature="(user_id: int) -> float",
            new_signature="(user_id: int, multiplier: float = 1.0) -> float",
            line_range=(10, 25),
        ),
    ],
    "new_files": ["rewards/models.py"],
}
```

#### Step 3: build_call_graph Node

```python
# Processing
# 1. Fetch Python files from staging_new branch
# 2. For each file, query AST: "who calls calculate_rewards?"

# Tree-sitter query:
# (call function: (identifier) @fn (#eq? @fn "calculate_rewards"))

# Found in orders/processor.py:
# def process_order(order):
#     reward = calculate_rewards(order.user_id)  # line 45
#     ...

# Output added to state
{
    "call_graph": {
        "calculate_rewards": {
            "callers": [
                CallerInfo(
                    function_name="process_order",
                    file_path="orders/processor.py",
                    line_number=45,
                    context_code="""
def process_order(order):
    # Calculate rewards for this order
    reward = calculate_rewards(order.user_id)
    if reward > 0:
        apply_reward(order.user_id, reward)
""",
                ),
            ],
            "callees": ["get_user", "apply_multiplier"],
        },
    },
}
```

#### Step 4: analyze_impact Node

```python
# Processing
# 1. Compare signatures
# 2. Check if callers need updates
# 3. Find test coverage

# Output added to state
{
    "impact_report": {
        "breaking_changes": [],  # New param has default, backward compatible
        "warnings": [
            {
                "type": "unused_new_feature",
                "message": "New 'multiplier' parameter not used by any existing callers",
                "affected": ["process_order"],
            },
        ],
        "test_coverage": {
            "calculate_rewards": {
                "has_tests": True,
                "test_file": "tests/test_rewards.py",
                "tests": ["test_calculate_rewards_basic"],
                "missing_coverage": ["multiplier parameter"],
            },
        },
    },
}
```

#### Step 5: route_review Node

```python
# Processing
# 1. Classify each function for review depth
# 2. Skip trivial changes

# Output added to state
{
    "functions_to_review": [
        {
            "function": FunctionChange(...),
            "depth": "DEEP",  # Has impact warnings
            "callers": [...],
        },
    ],
}
```

#### Step 6: review_function Node (Parallel)

```python
# Context provided to LLM:
"""
## Function: calculate_rewards

### BEFORE (staging_new):
```python
def calculate_rewards(user_id: int) -> float:
    user = get_user(user_id)
    return user.points * 0.01
```

### AFTER (feature/rewards-program):
```python
def calculate_rewards(user_id: int, multiplier: float = 1.0) -> float:
    user = get_user(user_id)
    base_reward = user.points * 0.01
    return base_reward * multiplier
```

### Callers (will be affected):
```python
# orders/processor.py - process_order() @ line 45
def process_order(order):
    reward = calculate_rewards(order.user_id)  # <-- Currently not passing multiplier
    if reward > 0:
        apply_reward(order.user_id, reward)
```

### Test Coverage:
- Existing tests in tests/test_rewards.py
- Missing: tests for multiplier parameter

### Questions:
1. Is the default multiplier of 1.0 backward compatible?
2. Should callers be updated to pass multiplier explicitly?
3. Are there edge cases for multiplier <= 0?
4. Does the test file need new test cases?
"""

# LLM Response
{
    "findings": [
        {
            "line": 12,
            "severity": "warning",
            "message": "No validation for multiplier parameter. Negative or zero values could produce unexpected rewards.",
            "suggestion": "Add: if multiplier <= 0: raise ValueError('multiplier must be positive')",
        },
        {
            "line": 12,
            "severity": "info", 
            "message": "Consider documenting the multiplier parameter's expected range and use cases.",
            "suggestion": "Add docstring explaining when to use multiplier != 1.0",
        },
    ],
}
```

#### Step 7: aggregate Node

```python
# Merge comments from all parallel reviews
# Deduplicate, sort by severity

{
    "final_comments": [
        ReviewComment(
            file="rewards/calculator.py",
            line=12,
            severity="warning",
            message="No validation for multiplier parameter...",
            suggestion="Add: if multiplier <= 0: raise ValueError...",
        ),
        ReviewComment(
            file="rewards/calculator.py",
            line=12,
            severity="info",
            message="Consider documenting the multiplier parameter...",
            suggestion="Add docstring...",
        ),
    ],
    "summary": "## Review Summary\n\n**1 warning, 1 suggestion**\n\n...",
}
```

#### Step 8: publish_github Node

```python
# POST /repos/company/backend/pulls/42/reviews
{
    "body": "## Review Summary\n\n**1 warning, 1 suggestion**\n\n...",
    "event": "COMMENT",  # No critical issues
    "comments": [
        {
            "path": "rewards/calculator.py",
            "line": 12,
            "body": "⚠️ **Warning**: No validation for multiplier parameter..."
        },
        # ...
    ]
}
```

### Timeline

| Phase | Node | Time | LLM Calls |
|-------|------|------|-----------|
| 1 | extract_diff | ~3s | 0 |
| 2 | build_call_graph | ~5s | 0 |
| 2 | analyze_impact | ~1s | 0 |
| 3 | route_review | ~1s | 0 |
| 3 | review_function | ~10s | 1 per function |
| 3 | aggregate | ~0.5s | 0 |
| Output | publish + notify | ~2s | 0 |
| **Total** | | **~22s** | **~1-3** |
