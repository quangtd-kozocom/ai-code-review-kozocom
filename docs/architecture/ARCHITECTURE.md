# Architecture Overview: PR Review System v2

> **Document Version**: 2.0  
> **Last Updated**: January 2026  
> **Status**: Proposed Architecture

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Architecture](#proposed-architecture)
4. [Core Components](#core-components)
5. [Data Flow](#data-flow)
6. [Technology Stack](#technology-stack)
7. [Key Architectural Changes](#key-architectural-changes)

---

## Executive Summary

This document describes the redesigned PR Review System architecture, moving from a **Vector Database-centric RAG approach** to an **AST-based Direct Analysis approach**. The fundamental insight driving this change:

> **PR review is a code understanding problem, not a document retrieval problem.**

Vector databases excel at "find similar documents" but fail at "understand how this specific change affects these specific functions." We're replacing approximate semantic matching with deterministic code analysis.

### Key Changes at a Glance

| Aspect | Old (v1) | New (v2) |
|--------|----------|----------|
| **Context Source** | Vector DB (Pinecone) | Direct GitHub API + AST |
| **Code Understanding** | Embedding similarity | Tree-sitter parsing |
| **Branch Handling** | Main branch only | Both source & target branches |
| **Call Graph** | Metadata string matching | AST-based traversal |
| **Indexing** | Pre-index entire repo | On-demand analysis |
| **Maintenance** | High (index sync) | Zero (always fresh) |

---

## Current State Analysis

### What's Broken in the Existing System

#### 1. Single-Branch Indexing Limitation

```
PROBLEM:
┌─────────────────────────────────────────────────────────┐
│  Repository State                                        │
├─────────────────────────────────────────────────────────┤
│  main ────────●────────●────────●────────●              │
│                         \                                │
│  staging_new ────────────●────●────●                    │
│                               \                          │
│  feature/rewards ──────────────●────●────● (PR Source)  │
│                                                          │
│  INDEXED: Only 'main' branch                            │
│  PR: feature/rewards → staging_new                      │
│  RESULT: Context is from wrong branch!                  │
└─────────────────────────────────────────────────────────┘
```

**Impact**: When reviewing a PR from `feature/rewards-program` → `staging_new`:
- System queries Pinecone for related code
- Pinecone returns code from `main` branch (the only indexed branch)
- `staging_new` may have diverged significantly from `main`
- Agent reviews based on **stale/incorrect context**
- Reviews are confidently wrong

#### 2. Vector Database Misuse

```python
# CURRENT: Using Pinecone for exact matching (defeats the purpose)
results = store.fetch_by_metadata(
    namespace=f"{owner}/{repo}",
    filter={"calls": {"$in": [function_name]}},  # ← Exact string match!
    limit=5,
)

# PROBLEM: This is what SQL does. Why pay for vector DB?
# Vector DB value proposition: semantic similarity search
# Our usage: exact metadata filtering
```

**What we're paying for vs. what we're using**:

| Vector DB Capability | Are We Using It? |
|---------------------|------------------|
| Semantic similarity search | ❌ Rarely (fallback only) |
| Embedding-based retrieval | ❌ Not for primary queries |
| Metadata filtering | ✅ This is our main usage |
| Namespace isolation | ✅ Per-repo namespaces |

**Verdict**: We're paying vector DB complexity costs without gaining semantic search benefits.

#### 3. Hallucination-Prone Context

```
CURRENT CONTEXT FLOW:
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Changed File   │────▶│  Query Pinecone  │────▶│  "Related" Code  │
│  (from PR diff)  │     │  (main branch)   │     │  (possibly stale)│
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                           │
                                                           ▼
                                                  ┌──────────────────┐
                                                  │  LLM Reviews     │
                                                  │  with wrong      │
                                                  │  context         │
                                                  └──────────────────┘

RESULT: Agent confidently makes claims about code that doesn't exist
        in the actual branches being merged.
```

#### 4. Shallow Review Quality

Current reviews catch:
- ✅ Style issues (naming, formatting)
- ✅ Generic security patterns (hardcoded secrets)
- ❌ Business logic bugs
- ❌ Integration issues with existing code
- ❌ Breaking changes to API contracts
- ❌ Missing error handling for specific use cases

**Root Cause**: Without accurate call graphs and cross-file analysis, the agent can't understand code relationships.

### Specific Bottlenecks

| Bottleneck | Location | Impact |
|------------|----------|--------|
| Stale index | `indexer.py` | Wrong context for non-main branches |
| Metadata-only queries | `retriever.py` | No semantic understanding |
| Single-branch assumption | `context_extractor.py` | Can't compare feature vs. target |
| Truncated content | `chunker.py` (1000 char limit) | Loses important function details |
| Sequential embedding | `embedder.py` | Slow indexing |
| No incremental updates | Webhook handlers | Full re-index on merge |

---

## Proposed Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PR REVIEW SYSTEM v2                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │   GitHub     │     │              LANGGRAPH WORKFLOW                   │  │
│  │   Webhook    │────▶│                                                   │  │
│  │  (PR Event)  │     │  ┌─────────┐   ┌─────────┐   ┌─────────────────┐ │  │
│  └──────────────┘     │  │  PHASE  │   │  PHASE  │   │     PHASE       │ │  │
│                       │  │    1    │──▶│    2    │──▶│       3         │ │  │
│  ┌──────────────┐     │  │  DIFF   │   │ IMPACT  │   │    REVIEW       │ │  │
│  │   FastAPI    │     │  │ANALYSIS │   │ GRAPH   │   │   (LLM-based)   │ │  │
│  │   Server     │     │  └─────────┘   └─────────┘   └─────────────────┘ │  │
│  └──────────────┘     │       │             │               │            │  │
│         │             │       ▼             ▼               ▼            │  │
│         ▼             │  ┌─────────────────────────────────────────────┐ │  │
│  ┌──────────────┐     │  │              SHARED STATE                   │ │  │
│  │   Celery     │     │  │  • PR Context    • Changed Functions        │ │  │
│  │   Worker     │────▶│  │  • Call Graph    • Impact Analysis          │ │  │
│  └──────────────┘     │  │  • Review Comments                          │ │  │
│                       │  └─────────────────────────────────────────────┘ │  │
│                       └──────────────────────────────────────────────────┘  │
│                                          │                                   │
│  ┌───────────────────────────────────────┼───────────────────────────────┐  │
│  │              EXTERNAL SERVICES        │                                │  │
│  │                                       ▼                                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │  GitHub  │  │  Jira/   │  │  Slack   │  │  Static  │              │  │
│  │  │   API    │  │  Linear  │  │          │  │ Analysis │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Three-Phase Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  PHASE 1: DIFF ANALYSIS (No LLM, Deterministic)                             │
│  ─────────────────────────────────────────────                              │
│  • Fetch PR diff from GitHub                                                 │
│  • Parse changed files with Tree-sitter                                      │
│  • Extract: changed functions, modified signatures, new imports              │
│  • Output: Structured list of changes                                        │
│                                                                              │
│  Time: ~2-5 seconds                                                          │
│  Cost: $0 (no LLM)                                                           │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 2: IMPACT GRAPH (No LLM, AST-Based)                                  │
│  ─────────────────────────────────────────                                   │
│  • Build call graph using Tree-sitter queries                                │
│  • Find callers of changed functions (in BOTH branches)                      │
│  • Identify affected tests                                                   │
│  • Detect signature breaking changes                                         │
│  • Output: Complete impact analysis                                          │
│                                                                              │
│  Time: ~5-15 seconds (depends on repo size)                                  │
│  Cost: $0 (no LLM)                                                           │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 3: INTELLIGENT REVIEW (Targeted LLM)                                 │
│  ──────────────────────────────────────────                                  │
│  • Route changes to specialized reviewers                                    │
│  • Provide precise context per function                                      │
│  • Ask specific questions (not generic review)                               │
│  • Aggregate and deduplicate findings                                        │
│  • Output: High-quality review comments                                      │
│                                                                              │
│  Time: ~15-30 seconds                                                        │
│  Cost: ~$0.02-0.05 per PR                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### Component Overview

```
src/
├── analysis/                    # NEW: Code analysis components
│   ├── __init__.py
│   ├── diff_extractor.py       # GitHub diff parsing
│   ├── ast_analyzer.py         # Tree-sitter based analysis
│   ├── call_graph.py           # Build call relationships
│   ├── impact_analyzer.py      # Determine change impact
│   └── context_builder.py      # Assemble review context
│
├── agents/                      # REFACTORED: Simplified workflow
│   ├── __init__.py
│   ├── graph.py                # New 3-phase graph
│   ├── state.py                # Simplified state schema
│   ├── nodes/
│   │   ├── diff_analysis.py    # Phase 1 node
│   │   ├── impact_graph.py     # Phase 2 node
│   │   ├── review_router.py    # Route to reviewers
│   │   ├── function_reviewer.py # Review single function
│   │   ├── aggregator.py       # Combine results
│   │   └── publisher.py        # Post to GitHub
│   └── prompts/
│       ├── function_review.py  # Targeted prompts
│       └── file_review.py      # File-level prompts
│
├── integrations/                # NEW: External service integrations
│   ├── __init__.py
│   ├── github.py               # GitHub API client
│   ├── jira.py                 # Jira integration
│   ├── slack.py                # Slack notifications
│   └── static_analysis.py      # External linters
│
├── app/                         # UNCHANGED: FastAPI server
│   ├── main.py
│   └── api/
│
└── workers/                     # UNCHANGED: Celery workers
    └── tasks.py
```

### Component Responsibilities

#### 1. DiffExtractor (`analysis/diff_extractor.py`)

```python
class DiffExtractor:
    """
    Extracts structured diff information from GitHub PR.
    
    Responsibilities:
    - Fetch PR files and patches from GitHub API
    - Parse unified diff format
    - Identify change types (added, modified, deleted)
    - Extract line ranges for each change
    
    Does NOT:
    - Parse code semantics (that's AST analyzer's job)
    - Make judgments about changes
    - Call any LLM
    """
    
    async def extract(self, pr: PRContext) -> DiffResult:
        # Returns structured diff data
        pass
```

#### 2. ASTAnalyzer (`analysis/ast_analyzer.py`)

```python
class ASTAnalyzer:
    """
    Tree-sitter based code analysis.
    
    Responsibilities:
    - Parse source code into AST
    - Extract functions, classes, methods
    - Identify function signatures and parameters
    - Extract function calls within code
    - Compare old vs. new versions
    
    Supported Languages:
    - Python (.py)
    - JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
    - Go (.go)
    - Java (.java)
    """
    
    def extract_functions(self, code: str, language: str) -> list[FunctionInfo]:
        pass
    
    def extract_calls(self, code: str, language: str) -> list[str]:
        pass
    
    def compare_signatures(self, old: FunctionInfo, new: FunctionInfo) -> SignatureDiff:
        pass
```

#### 3. CallGraphBuilder (`analysis/call_graph.py`)

```python
class CallGraphBuilder:
    """
    Builds accurate call relationships using AST.
    
    Responsibilities:
    - Find all callers of a function across codebase
    - Find all callees (functions called by target)
    - Build bi-directional relationship graph
    - Track call sites with line numbers
    
    Key Difference from v1:
    - v1: String matching in Pinecone metadata
    - v2: AST query for actual function calls
    
    Accuracy: ~99% for direct calls (vs ~60% for string matching)
    """
    
    def find_callers(
        self, 
        function_name: str, 
        files: dict[str, str]
    ) -> list[CallerInfo]:
        pass
    
    def build_graph(
        self, 
        changed_functions: list[str],
        files: dict[str, str]
    ) -> CallGraph:
        pass
```

#### 4. ImpactAnalyzer (`analysis/impact_analyzer.py`)

```python
class ImpactAnalyzer:
    """
    Determines the impact of code changes.
    
    Responsibilities:
    - Identify breaking signature changes
    - Find affected downstream functions
    - Detect missing test coverage
    - Analyze type compatibility
    
    Output: Impact report for each changed function
    """
    
    def analyze(
        self,
        changes: list[FunctionChange],
        call_graph: CallGraph,
        tests: dict[str, str]
    ) -> ImpactReport:
        pass
```

#### 5. ContextBuilder (`analysis/context_builder.py`)

```python
class ContextBuilder:
    """
    Assembles complete context for LLM review.
    
    Key Principle: Provide PRECISE context, not MORE context.
    
    For each changed function, builds:
    - Before/after code
    - Exact diff
    - Relevant callers (with call site context)
    - Related tests
    - Type information
    
    Does NOT include:
    - Unrelated code from same file
    - Generic "similar" code from vector search
    - Code from wrong branch
    """
    
    def build(
        self,
        function: FunctionChange,
        callers: list[CallerInfo],
        tests: list[TestInfo]
    ) -> ReviewContext:
        pass
```

---

## Data Flow

### Complete Flow: PR Created → Review Posted

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Webhook Received                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  GitHub sends:                                                               │
│  {                                                                           │
│    "action": "opened",                                                       │
│    "pull_request": {                                                         │
│      "number": 42,                                                           │
│      "head": {"ref": "feature/rewards-program"},                            │
│      "base": {"ref": "staging_new"},                                        │
│      ...                                                                     │
│    }                                                                         │
│  }                                                                           │
│                                                                              │
│  FastAPI → Validates webhook → Queues Celery task                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Diff Analysis (Phase 1)                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DiffExtractor.extract():                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  GitHub API: GET /repos/{owner}/{repo}/pulls/{number}/files          │    │
│  │                                                                       │    │
│  │  Returns:                                                             │    │
│  │  [                                                                    │    │
│  │    {                                                                  │    │
│  │      "filename": "rewards/calculator.py",                            │    │
│  │      "status": "modified",                                           │    │
│  │      "patch": "@@ -10,6 +10,8 @@\n def calculate..."                │    │
│  │    },                                                                 │    │
│  │    {                                                                  │    │
│  │      "filename": "rewards/models.py",                                │    │
│  │      "status": "added",                                              │    │
│  │      "patch": "..."                                                  │    │
│  │    }                                                                  │    │
│  │  ]                                                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ASTAnalyzer.extract_changed_functions():                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  For each modified file:                                              │    │
│  │  1. Fetch file from BASE branch (staging_new)                        │    │
│  │  2. Fetch file from HEAD branch (feature/rewards-program)            │    │
│  │  3. Parse both with Tree-sitter                                       │    │
│  │  4. Compare function lists                                            │    │
│  │  5. Identify: added, modified, deleted functions                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Output → State:                                                             │
│  {                                                                           │
│    "changed_functions": [                                                    │
│      {                                                                       │
│        "name": "calculate_rewards",                                         │
│        "file": "rewards/calculator.py",                                     │
│        "change_type": "modified",                                           │
│        "old_code": "def calculate_rewards(user_id)...",                     │
│        "new_code": "def calculate_rewards(user_id, multiplier=1.0)...",     │
│        "old_signature": "(user_id: int) -> float",                          │
│        "new_signature": "(user_id: int, multiplier: float = 1.0) -> float"  │
│      }                                                                       │
│    ],                                                                        │
│    "new_files": ["rewards/models.py"]                                       │
│  }                                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Impact Graph (Phase 2)                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CallGraphBuilder.build_graph():                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  For function "calculate_rewards":                                    │    │
│  │                                                                       │    │
│  │  1. Fetch all Python files from staging_new branch                   │    │
│  │  2. For each file, parse AST and search for calls:                   │    │
│  │                                                                       │    │
│  │     Tree-sitter query:                                                │    │
│  │     (call function: (identifier) @fn (#eq? @fn "calculate_rewards")) │    │
│  │                                                                       │    │
│  │  3. Found callers:                                                    │    │
│  │     - orders/processor.py:process_order() @ line 45                  │    │
│  │     - batch/jobs.py:daily_rewards() @ line 128                       │    │
│  │     - api/endpoints.py:get_rewards() @ line 67                       │    │
│  │                                                                       │    │
│  │  4. For each caller, extract 5 lines of context around call site     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ImpactAnalyzer.analyze():                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Signature changed: (user_id) → (user_id, multiplier=1.0)            │    │
│  │                                                                       │    │
│  │  Impact Assessment:                                                   │    │
│  │  - ✅ Backward compatible (new param has default)                    │    │
│  │  - ⚠️ Existing callers won't use new multiplier                     │    │
│  │  - ⚠️ Tests don't cover multiplier parameter                        │    │
│  │                                                                       │    │
│  │  For new file (rewards/models.py):                                   │    │
│  │  - Calls: get_user (from users/service.py)                           │    │
│  │  - Calls: calculate_tax (from billing/utils.py)                      │    │
│  │  - These existing functions validated against their signatures       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Output → State:                                                             │
│  {                                                                           │
│    "call_graph": {                                                          │
│      "calculate_rewards": {                                                 │
│        "callers": [...],                                                    │
│        "callees": ["get_user", "apply_multiplier"]                         │
│      }                                                                       │
│    },                                                                        │
│    "impact_report": {                                                       │
│      "breaking_changes": [],                                                │
│      "warnings": [                                                          │
│        {"type": "unused_parameter", "details": "..."}                      │
│      ],                                                                      │
│      "test_coverage": {"calculate_rewards": {"covered": true, ...}}        │
│    }                                                                         │
│  }                                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Intelligent Review (Phase 3)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ReviewRouter.route():                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Based on change characteristics, route to appropriate reviewers:    │    │
│  │                                                                       │    │
│  │  calculate_rewards (modified):                                       │    │
│  │    → LogicReviewer (has business logic)                              │    │
│  │    → SecurityReviewer (if handles user data)                         │    │
│  │                                                                       │    │
│  │  RewardTier (new class in models.py):                                │    │
│  │    → LogicReviewer (new business entity)                             │    │
│  │    → ArchitectureReviewer (new pattern introduction)                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  FunctionReviewer.review() - FOR EACH FUNCTION:                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Context provided to LLM:                                             │    │
│  │  {                                                                    │    │
│  │    "function": "calculate_rewards",                                  │    │
│  │    "before_code": "...",                                             │    │
│  │    "after_code": "...",                                              │    │
│  │    "diff": "...",                                                    │    │
│  │    "callers": [                                                      │    │
│  │      {                                                                │    │
│  │        "function": "process_order",                                  │    │
│  │        "file": "orders/processor.py",                                │    │
│  │        "context": "reward = calculate_rewards(order.user_id)..."     │    │
│  │      }                                                                │    │
│  │    ],                                                                 │    │
│  │    "specific_questions": [                                           │    │
│  │      "Is the default multiplier backward compatible?",               │    │
│  │      "Should callers be updated to use multiplier?",                 │    │
│  │      "Are there edge cases for multiplier <= 0?"                     │    │
│  │    ]                                                                  │    │
│  │  }                                                                    │    │
│  │                                                                       │    │
│  │  LLM Response:                                                        │    │
│  │  {                                                                    │    │
│  │    "findings": [                                                      │    │
│  │      {                                                                │    │
│  │        "line": 15,                                                   │    │
│  │        "severity": "warning",                                        │    │
│  │        "message": "No validation for multiplier <= 0",               │    │
│  │        "suggestion": "Add: if multiplier <= 0: raise ValueError"    │    │
│  │      }                                                                │    │
│  │    ]                                                                  │    │
│  │  }                                                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Publish Review                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Aggregator.aggregate():                                                     │
│  - Deduplicate by (file, line)                                              │
│  - Sort by severity (critical first)                                        │
│  - Apply per-file comment limit                                             │
│                                                                              │
│  GitHubPublisher.publish():                                                  │
│  - Create pending review                                                     │
│  - Add inline comments at specific lines                                     │
│  - Submit review with appropriate action                                     │
│                                                                              │
│  SlackNotifier.notify() (optional):                                          │
│  - Send summary to configured channel                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Core Technologies

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Workflow Engine** | LangGraph | State management, conditional routing, parallel execution |
| **AST Parsing** | tree-sitter | Fast, accurate, multi-language, battle-tested (used by GitHub) |
| **HTTP Client** | httpx | Async support, modern API, good for GitHub API |
| **Task Queue** | Celery + Redis | Existing infrastructure, proven scalability |
| **Web Framework** | FastAPI | Existing infrastructure, async support |
| **LLM** | OpenAI GPT-4 / Claude | Structured output, good code understanding |

### Why Tree-sitter?

```
Comparison: Regex vs AST vs LSP for code parsing

┌────────────────┬──────────────┬──────────────┬──────────────┐
│ Approach       │ Regex        │ Tree-sitter  │ LSP          │
├────────────────┼──────────────┼──────────────┼──────────────┤
│ Accuracy       │ ~60%         │ ~99%         │ ~99.9%       │
│ Speed          │ Fast         │ Very Fast    │ Slow         │
│ Setup          │ None         │ Easy         │ Complex      │
│ Multi-language │ Custom each  │ Built-in     │ Separate LSP │
│ Maintenance    │ High         │ Low          │ High         │
│ Dependencies   │ None         │ Single lib   │ Multiple     │
└────────────────┴──────────────┴──────────────┴──────────────┘

Winner for our use case: Tree-sitter
- Good enough accuracy
- Very fast (can parse entire repo in seconds)
- Single dependency (tree-sitter-languages)
- No server processes to manage
```

### Python Dependencies

```toml
# pyproject.toml additions

[project]
dependencies = [
    # Existing
    "fastapi>=0.100.0",
    "celery>=5.3.0",
    "redis>=4.5.0",
    "langgraph>=0.2.0",
    "openai>=1.0.0",
    "httpx>=0.24.0",
    
    # New for v2
    "tree-sitter-languages>=1.8.0",  # Multi-language AST parsing
    
    # Removed (or optional)
    # "pinecone-client"  # No longer primary
    # "langchain"  # Direct LangGraph usage
]
```

---

## Key Architectural Changes

### What Gets Removed

| Component | File(s) | Reason |
|-----------|---------|--------|
| **Pinecone Indexer** | `src/rag/indexer.py` | No longer pre-indexing repos |
| **Vector Retriever** | `src/rag/retriever.py` | Replaced with AST-based call graph |
| **RAG Enricher** | `src/agents/services/rag_enricher.py` | Replaced with ContextBuilder |
| **Call Resolution** | `src/rag/call_resolution.py` | Logic moved to CallGraphBuilder |
| **Chunker** | `src/rag/chunker.py` | No longer chunking for embeddings |
| **Index Webhooks** | Handlers for indexing on install/merge | Not needed |

### What Gets Added

| Component | File(s) | Purpose |
|-----------|---------|---------|
| **DiffExtractor** | `src/analysis/diff_extractor.py` | Parse GitHub diffs |
| **ASTAnalyzer** | `src/analysis/ast_analyzer.py` | Tree-sitter based parsing |
| **CallGraphBuilder** | `src/analysis/call_graph.py` | Build accurate call relationships |
| **ImpactAnalyzer** | `src/analysis/impact_analyzer.py` | Determine change impact |
| **ContextBuilder** | `src/analysis/context_builder.py` | Assemble LLM context |
| **New Graph Nodes** | `src/agents/nodes/` | Simplified 3-phase pipeline |

### What Gets Refactored

| Component | Change | Reason |
|-----------|--------|--------|
| **Graph Definition** | 8 nodes → 6 nodes | Simpler, more focused |
| **State Schema** | Remove RAG fields | No longer needed |
| **Prompts** | Generic → Targeted | Ask specific questions |
| **GitHub Client** | Add branch-aware fetching | Support any branch combination |

### Migration Path

```
Week 1: Build analysis/ components
        - DiffExtractor
        - ASTAnalyzer  
        - CallGraphBuilder

Week 2: Integrate into LangGraph
        - New graph definition
        - New state schema
        - ContextBuilder

Week 3: Migrate prompts and reviewers
        - Targeted prompts
        - Function-level review
        - Aggregation

Week 4: Test and deploy
        - End-to-end testing
        - Performance optimization
        - Production rollout
```

---

## Summary

### Before vs. After

```
BEFORE (v1):                           AFTER (v2):
────────────                           ──────────

┌──────────────┐                       ┌──────────────┐
│ Index main   │                       │ PR webhook   │
│ branch       │                       │ received     │
└──────┬───────┘                       └──────┬───────┘
       │                                      │
       ▼                                      ▼
┌──────────────┐                       ┌──────────────┐
│ Store in     │                       │ Fetch both   │
│ Pinecone     │                       │ branches     │
└──────┬───────┘                       └──────┬───────┘
       │                                      │
       ▼                                      ▼
┌──────────────┐                       ┌──────────────┐
│ PR arrives   │                       │ Parse AST    │
│              │                       │ (tree-sitter)│
└──────┬───────┘                       └──────┬───────┘
       │                                      │
       ▼                                      ▼
┌──────────────┐                       ┌──────────────┐
│ Query        │                       │ Build call   │
│ Pinecone     │──── WRONG ────X       │ graph        │──── ACCURATE
│ (main branch)│     CONTEXT           │ (both branches)    CONTEXT
└──────┬───────┘                       └──────┬───────┘
       │                                      │
       ▼                                      ▼
┌──────────────┐                       ┌──────────────┐
│ LLM reviews  │                       │ LLM reviews  │
│ with stale   │                       │ with precise │
│ context      │                       │ context      │
└──────────────┘                       └──────────────┘

RESULT: Hallucinations            RESULT: Accurate reviews
```

### Key Insight

The fundamental change is philosophical:

> **Old approach**: "Let's find semantically similar code and hope the LLM figures it out"
> 
> **New approach**: "Let's give the LLM exactly the code it needs with explicit relationships"

This shift from **retrieval-based** to **analysis-based** context is what will transform review quality from "catches formatting issues" to "catches business logic bugs."
