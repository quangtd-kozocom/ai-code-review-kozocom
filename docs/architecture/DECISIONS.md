# Architecture Decision Log

> **Document Version**: 2.0  
> **Last Updated**: January 2026

## Table of Contents

1. [Decision 1: Abandon Vector Database as Primary Context Source](#decision-1-abandon-vector-database)
2. [Decision 2: Use AST Parsing with Tree-sitter](#decision-2-use-ast-parsing)
3. [Decision 3: On-Demand Analysis vs Pre-Indexing](#decision-3-on-demand-analysis)
4. [Decision 4: Function-Level Review Granularity](#decision-4-function-level-review)
5. [Decision 5: Keep Vector DB for Pattern Search (Optional)](#decision-5-keep-vector-db-optional)
6. [Decision 6: Targeted Prompts vs Generic Review](#decision-6-targeted-prompts)
7. [Decision 7: Simplified Graph Structure](#decision-7-simplified-graph)

---

## Decision 1: Abandon Vector Database

### Decision

**Demote vector database from primary context source to optional pattern search tool.**

### Status

✅ **APPROVED**

### Context

The current system uses Pinecone vector database as the primary source of context for PR reviews:

```
Current Flow:
1. Index main branch → Pinecone
2. PR arrives
3. Query Pinecone for "related" code
4. Provide to LLM as context
```

### Problem Statement

1. **Wrong branch context**: Only `main` is indexed, but PRs target various branches (`staging`, `develop`, etc.)
2. **Metadata abuse**: Using vector DB primarily for exact metadata matching (`calls: {$in: [name]}`)
3. **Stale data**: Index becomes stale between merges
4. **Complexity cost**: High maintenance without proportional benefit

### Options Considered

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Fix indexing** | Index all branches | Accurate context | Massive storage cost, sync complexity |
| **B: Per-PR indexing** | Index target branch on each PR | Always fresh | Slow (must index before review) |
| **C: Abandon for primary use** | Direct GitHub fetch + AST | Always accurate, zero maintenance | No semantic similarity |
| **D: Hybrid** | AST primary + vector for patterns | Best of both | Two systems to maintain |

### Decision

**Option C with optional D**: Use direct GitHub fetch + AST parsing as primary context source. Optionally keep vector DB for pattern search only.

### Rationale

1. **PR review is deterministic**: "What functions call X?" has an exact answer. We don't need semantic approximation.

2. **Branch accuracy is critical**: Reviews must be based on actual branches being merged, not approximations from `main`.

3. **Complexity reduction**: Eliminating indexing pipeline removes:
   - Webhook handlers for indexing
   - Index sync logic
   - Reindexing jobs
   - Pinecone costs (~$70-200/month)

4. **Query pattern analysis**:
   ```python
   # 95% of our queries are exact matches:
   filter={"calls": {"$in": [function_name]}}  # This is SQL, not vector search!
   
   # Only 5% use actual embedding search:
   results = store.query(vector=embedding, ...)  # Rarely used
   ```

### Consequences

**Positive:**
- Always-accurate context from correct branches
- Zero maintenance burden
- Reduced infrastructure costs
- Simpler architecture

**Negative:**
- Lose semantic "similar code" search (mitigated by keeping optional)
- Slightly more GitHub API calls (mitigated by caching)

### Trade-offs Accepted

| Lost Capability | Mitigation | Acceptable? |
|----------------|------------|-------------|
| Find semantically similar code | Keep optional vector search | ✅ Yes |
| Pre-computed relationships | Build on-demand (fast with AST) | ✅ Yes |
| Cross-repo patterns | Future enhancement | ✅ Yes for MVP |

---

## Decision 2: Use AST Parsing

### Decision

**Use Tree-sitter for code parsing instead of regex/string matching.**

### Status

✅ **APPROVED**

### Context

Need to extract:
- Function definitions and signatures
- Function calls (who calls what)
- Import relationships
- Class hierarchies

### Options Considered

| Option | Accuracy | Speed | Multi-lang | Complexity |
|--------|----------|-------|------------|------------|
| **Regex** | ~60% | Fast | Custom each | Low |
| **Tree-sitter** | ~99% | Very Fast | Built-in | Medium |
| **LSP** | ~99.9% | Slow | Per-language | High |
| **LLM parsing** | ~90% | Slow | Any | Low |

### Decision

**Tree-sitter** via `tree-sitter-languages` Python package.

### Rationale

1. **Accuracy vs. Complexity trade-off**: Tree-sitter provides near-perfect accuracy without the complexity of running language servers.

2. **Battle-tested**: Used by GitHub for syntax highlighting, Neovim, and many IDEs.

3. **Speed**: Can parse entire file in milliseconds.

4. **Multi-language**: Single API for Python, JavaScript, TypeScript, Go, etc.

5. **Query language**: Tree-sitter's query DSL makes pattern matching declarative:
   ```scheme
   ; Find all function calls to a specific function
   (call
     function: (identifier) @func_name
     (#eq? @func_name "calculate_rewards")
   ) @call
   ```

### Consequences

**Positive:**
- Accurate function extraction
- Accurate call graph construction
- Fast enough for on-demand analysis
- Single dependency

**Negative:**
- Learning curve for Tree-sitter queries
- Some edge cases (dynamic calls, metaprogramming) not detectable

### Implementation Notes

```python
# Installation
pip install tree-sitter-languages

# Usage
from tree_sitter_languages import get_parser, get_language

parser = get_parser('python')
tree = parser.parse(bytes(code, 'utf8'))

# Query for function definitions
language = get_language('python')
query = language.query("""
    (function_definition
        name: (identifier) @name
        parameters: (parameters) @params
    ) @function
""")
captures = query.captures(tree.root_node)
```

---

## Decision 3: On-Demand Analysis

### Decision

**Perform code analysis on-demand when PR arrives, not pre-indexed.**

### Status

✅ **APPROVED**

### Context

Two approaches to providing context:
1. **Pre-index**: Index entire codebase upfront, query when needed
2. **On-demand**: Analyze relevant code when PR arrives

### Options Considered

| Approach | Freshness | Latency | Maintenance | Cost |
|----------|-----------|---------|-------------|------|
| Pre-index | Stale (until re-index) | Low query time | High | High |
| On-demand | Always fresh | Higher analysis time | Zero | Low |
| Hybrid | Moderate | Moderate | Moderate | Moderate |

### Decision

**On-demand analysis** for all context.

### Rationale

1. **Freshness trumps speed**: A 5-second slower review with correct context beats instant review with wrong context.

2. **Analysis is fast**: With Tree-sitter, analyzing changed files takes 2-5 seconds.

3. **Scope is limited**: We only need to analyze:
   - Changed files (from PR)
   - Files that import changed files (1 level)
   - Files that call changed functions (2 levels)
   
   This is typically 10-50 files, not the entire codebase.

4. **GitHub API is fast**: File content fetch is ~100ms per file, parallelizable.

### Consequences

**Positive:**
- Always accurate to the exact branches
- No index drift
- No background jobs
- No storage costs

**Negative:**
- Slightly higher latency per review (~5s more)
- More GitHub API calls (mitigated by caching)

### Performance Analysis

```
PR with 5 changed files:

Pre-index approach:
- Query Pinecone: ~500ms
- BUT: Context may be wrong (from main, not staging)

On-demand approach:
- Fetch 5 changed files: ~500ms (parallel)
- Parse with Tree-sitter: ~100ms
- Find callers (scan 20 files): ~1000ms
- Fetch caller files: ~500ms (parallel)
- Build context: ~100ms
- TOTAL: ~2.2s (but 100% accurate)
```

---

## Decision 4: Function-Level Review

### Decision

**Review at function granularity instead of file granularity.**

### Status

✅ **APPROVED**

### Context

Current system reviews entire files, providing file-level diff to LLM. This leads to:
- Generic comments
- Context overflow for large files
- Missed relationships between functions

### Options Considered

| Granularity | Precision | Context Size | LLM Calls |
|-------------|-----------|--------------|-----------|
| File | Low | Large (~5000 tokens) | N (files) |
| Function | High | Small (~500 tokens) | M (functions) |
| Line | Very High | Tiny | Very Many |

### Decision

**Function-level granularity** with targeted context per function.

### Rationale

1. **Focused context**: Each review call includes only:
   - The changed function
   - Its callers
   - Its callees
   - Related tests
   
   Not the entire file with unrelated code.

2. **Better prompts**: Can ask specific questions:
   ```
   "Is the new multiplier parameter validated?"
   vs.
   "Review this 500-line file"
   ```

3. **Parallel review**: Functions can be reviewed in parallel.

4. **Cost control**: Smaller context = fewer tokens = lower cost.

### Consequences

**Positive:**
- Higher quality reviews
- Lower token usage
- Parallelizable
- Specific comments

**Negative:**
- More LLM calls (M > N typically, but each is smaller)
- May miss file-level issues (mitigated by separate file-level pass)

---

## Decision 5: Keep Vector DB Optional

### Decision

**Keep Pinecone as optional tool for pattern search, not primary context.**

### Status

✅ **APPROVED**

### Context

While vector DB fails as primary context source, it has legitimate use cases:
- "Find similar error handling patterns"
- "Show me how other integrations are structured"
- "Are there similar functions I should check?"

### Decision

Keep vector DB infrastructure but:
1. Remove from critical path
2. Use only for optional "similar code" search
3. Don't require it for reviews to work

### Implementation

```python
class PatternSearcher:
    """Optional vector-based pattern search."""
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store
        self.enabled = vector_store is not None
    
    async def find_similar_patterns(
        self,
        code: str,
        pattern_type: str,  # "error_handling", "api_call", etc.
    ) -> list[SimilarCode]:
        """
        Find similar code patterns in codebase.
        
        OPTIONAL: Returns empty list if vector DB not configured.
        """
        if not self.enabled:
            return []
        
        embedding = await self.embed(code)
        results = await self.vector_store.query(
            vector=embedding,
            top_k=3,
            filter={"pattern_type": pattern_type}
        )
        return [SimilarCode.from_result(r) for r in results]
```

### Consequences

**Positive:**
- Keep valuable capability
- Not a blocker for MVP
- Can enhance reviews when available

**Negative:**
- Two code paths to maintain
- Confusion about when to use

---

## Decision 6: Targeted Prompts

### Decision

**Use function-specific targeted prompts instead of generic review prompts.**

### Status

✅ **APPROVED**

### Context

Current prompts are generic:
```
"Review this code for security, style, and logic issues."
```

This leads to:
- Generic advice ("consider adding tests")
- Hallucinated issues
- Missed specific problems

### Decision

Use targeted prompts with:
1. Specific context about the change
2. Explicit relationships (callers, callees)
3. Concrete questions based on change type

### Example

```python
# OLD (Generic)
prompt = f"""
Review this code:
{diff}

Check for security, style, and logic issues.
"""

# NEW (Targeted)
prompt = f"""
## Function Modified: {func.name}

### Before:
```{language}
{func.old_code}
```

### After:
```{language}
{func.new_code}
```

### Callers (will be affected):
{formatted_callers}

### Questions:
1. Is the signature change backward compatible?
2. Will the callers at lines {caller_lines} work correctly?
3. Are there edge cases for the new {new_param} parameter?

Provide specific findings with line numbers.
"""
```

### Consequences

**Positive:**
- More relevant findings
- Fewer hallucinations (context is explicit)
- Actionable suggestions

**Negative:**
- More complex prompt engineering
- Need to generate questions per change type

---

## Decision 7: Simplified Graph Structure

### Decision

**Reduce graph from 9 nodes to 7 nodes with clear phase separation.**

### Status

✅ **APPROVED**

### Context

Current graph:
```
acknowledge → extract → router → [security, style, logic] → aggregate → publish → notify
```

Problems:
- `acknowledge` adds noise (comment on every PR)
- Three parallel agents review same code redundantly
- `router` LLM call often routes to all agents anyway

### Decision

New graph:
```
extract_diff → build_call_graph → analyze_impact → route → review_function(s) → aggregate → publish
```

### Changes

| Old Node | New Node | Change |
|----------|----------|--------|
| acknowledge | *(removed)* | Eliminated |
| extract_context | extract_diff | No RAG enrichment |
| — | build_call_graph | **NEW** |
| — | analyze_impact | **NEW** |
| smart_router | route_review | Simplified |
| security/style/logic | review_function | **MERGED** |
| aggregate | aggregate | Similar |
| publish | publish_github | Similar |
| notify | notify_slack | Parallel with publish |

### Rationale

1. **Clear phases**: 
   - Phase 1: Diff (deterministic)
   - Phase 2: Impact (AST-based)
   - Phase 3: Review (LLM)

2. **Reduced redundancy**: One review per function instead of three.

3. **Better parallelism**: Functions reviewed in parallel, not agents.

### Consequences

**Positive:**
- Simpler to understand
- Fewer LLM calls
- Clear separation of concerns

**Negative:**
- Lose "specialist" agents (mitigated by comprehensive prompts)
- Single point of review (mitigated by quality control)

---

## Summary of Decisions

| # | Decision | Rationale | Impact |
|---|----------|-----------|--------|
| 1 | Abandon Vector DB (primary) | Wrong branch, metadata abuse | Major architecture change |
| 2 | Use Tree-sitter AST | Accuracy, speed, multi-lang | New dependency |
| 3 | On-demand analysis | Freshness, zero maintenance | Slight latency increase |
| 4 | Function-level review | Precision, parallelism | More LLM calls, smaller each |
| 5 | Keep Vector DB (optional) | Pattern search value | Maintain capability |
| 6 | Targeted prompts | Quality, reduced hallucination | Prompt engineering effort |
| 7 | Simplified graph | Clarity, efficiency | Code restructure |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter edge cases | Medium | Low | Fallback to full file |
| GitHub API rate limits | Low | Medium | Caching, pagination |
| Latency increase | Certain | Low | Parallel fetching |
| Lost semantic search | Low | Low | Keep optional vector DB |

### Success Metrics

Post-migration, track:

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| False positive rate | ~30% | <10% | Manual review sampling |
| Review latency | ~45s | ~25s | P95 latency |
| Cost per PR | ~$0.15 | ~$0.05 | LLM token tracking |
| Context accuracy | Unknown | 100% | Branch verification |
| Maintenance hours/month | ~8 | ~0 | Time tracking |
