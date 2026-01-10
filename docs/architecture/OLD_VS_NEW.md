# Architecture Comparison: Old vs New

> **Document Version**: 2.0  
> **Last Updated**: January 2026

## Table of Contents

1. [Side-by-Side Comparison](#side-by-side-comparison)
2. [Node Comparison](#node-comparison)
3. [Flow Comparison](#flow-comparison)
4. [Code Impact Analysis](#code-impact-analysis)
5. [Migration Checklist](#migration-checklist)

---

## Side-by-Side Comparison

### High-Level Architecture

```
┌─────────────────────────────────────┬─────────────────────────────────────┐
│           OLD (v1)                  │           NEW (v2)                  │
├─────────────────────────────────────┼─────────────────────────────────────┤
│                                     │                                     │
│  ┌─────────────┐                    │  ┌─────────────┐                    │
│  │ GitHub App  │                    │  │ GitHub App  │                    │
│  │ Installed   │                    │  │  (webhook)  │                    │
│  └──────┬──────┘                    │  └──────┬──────┘                    │
│         │                           │         │                           │
│         ▼                           │         │                           │
│  ┌─────────────┐                    │         │                           │
│  │ INDEX REPO  │ ← REMOVED          │         │ (No indexing!)            │
│  │ to Pinecone │                    │         │                           │
│  └──────┬──────┘                    │         │                           │
│         │                           │         │                           │
│         ▼                           │         ▼                           │
│  ┌─────────────┐                    │  ┌─────────────┐                    │
│  │   PR Open   │                    │  │   PR Open   │                    │
│  └──────┬──────┘                    │  └──────┬──────┘                    │
│         │                           │         │                           │
│         ▼                           │         ▼                           │
│  ┌─────────────┐                    │  ┌─────────────┐                    │
│  │Query Vector │                    │  │ Fetch Both  │                    │
│  │  DB (main)  │ ← WRONG BRANCH     │  │  Branches   │ ← CORRECT!         │
│  └──────┬──────┘                    │  └──────┬──────┘                    │
│         │                           │         │                           │
│         ▼                           │         ▼                           │
│  ┌─────────────┐                    │  ┌─────────────┐                    │
│  │ RAG Context │                    │  │ AST Parse   │                    │
│  │ (semantic)  │                    │  │(tree-sitter)│                    │
│  └──────┬──────┘                    │  └──────┬──────┘                    │
│         │                           │         │                           │
│         ▼                           │         ▼                           │
│  ┌─────────────┐                    │  ┌─────────────┐                    │
│  │  3 Parallel │                    │  │ Build Call  │                    │
│  │   Agents    │                    │  │   Graph     │                    │
│  │ (Sec/Style/ │                    │  └──────┬──────┘                    │
│  │   Logic)    │                    │         │                           │
│  └──────┬──────┘                    │         ▼                           │
│         │                           │  ┌─────────────┐                    │
│         │                           │  │  Targeted   │                    │
│         │                           │  │   Review    │                    │
│         │                           │  │ (per func)  │                    │
│         │                           │  └──────┬──────┘                    │
│         ▼                           │         ▼                           │
│  ┌─────────────┐                    │  ┌─────────────┐                    │
│  │  Aggregate  │                    │  │  Aggregate  │                    │
│  │  & Publish  │                    │  │  & Publish  │                    │
│  └─────────────┘                    │  └─────────────┘                    │
│                                     │                                     │
└─────────────────────────────────────┴─────────────────────────────────────┘
```

### Key Metrics Comparison

| Metric | Old (v1) | New (v2) | Improvement |
|--------|----------|----------|-------------|
| **Context Accuracy** | ~60% (main branch only) | ~99% (both branches) | +65% |
| **LLM Calls per PR** | 3N (N files × 3 agents) | N (1 per function) | -66% |
| **Time to Review** | ~45s | ~20s | -55% |
| **Cost per PR** | ~$0.15 | ~$0.05 | -66% |
| **False Positive Rate** | ~30% | ~10% (target) | -66% |
| **Maintenance Overhead** | High (index sync) | Zero | -100% |
| **Index Storage Cost** | $50-200/month | $0 | -100% |

---

## Node Comparison

### Old Graph Nodes (v1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OLD GRAPH (8 nodes)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. acknowledge         - Post "review started" comment                      │
│  2. extract_context     - Load config, fetch files, RAG enrich              │
│  3. smart_router        - LLM decides which agents per file                 │
│  4. security_agent      - Security-focused review                           │
│  5. style_agent         - Style-focused review                              │
│  6. logic_agent         - Logic-focused review                              │
│  7. aggregate           - Dedupe, sort, limit comments                      │
│  8. publish             - Post to GitHub                                    │
│  9. notify              - Slack notification                                │
│                                                                              │
│  Problems:                                                                   │
│  - Nodes 4-6 redundant (same code reviewed 3x)                              │
│  - RAG context in node 2 from wrong branch                                  │
│  - Router (node 3) adds latency without much value                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New Graph Nodes (v2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NEW GRAPH (7 nodes)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1 - ANALYSIS (No LLM):                                               │
│  1. extract_diff        - Parse PR diff, identify changed functions         │
│                                                                              │
│  PHASE 2 - IMPACT (No LLM):                                                 │
│  2. build_call_graph    - AST-based caller/callee analysis                  │
│  3. analyze_impact      - Breaking changes, test coverage                   │
│                                                                              │
│  PHASE 3 - REVIEW (Targeted LLM):                                           │
│  4. route_review        - Filter trivial, classify depth                    │
│  5. review_function     - Review single function with context (parallel)    │
│  6. aggregate           - Dedupe, sort, generate summary                    │
│                                                                              │
│  OUTPUT:                                                                     │
│  7. publish_github      - Post review to GitHub                             │
│  8. notify_slack        - Optional Slack notification                       │
│                                                                              │
│  Improvements:                                                               │
│  - Clear phase separation (analysis → impact → review)                      │
│  - LLM only used where necessary (Phase 3)                                  │
│  - Function-level review with precise context                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Node Mapping

| Old Node | New Node | Change |
|----------|----------|--------|
| `acknowledge` | *(removed)* | Unnecessary - adds noise |
| `extract_context` | `extract_diff` | Simplified - no RAG |
| — | `build_call_graph` | **NEW** - AST-based |
| — | `analyze_impact` | **NEW** - deterministic |
| `smart_router` | `route_review` | Simplified routing |
| `security_agent` | `review_function` | **MERGED** |
| `style_agent` | `review_function` | **MERGED** |
| `logic_agent` | `review_function` | **MERGED** |
| `aggregate` | `aggregate` | Same purpose |
| `publish` | `publish_github` | Same purpose |
| `notify` | `notify_slack` | Same purpose |

---

## Flow Comparison

### Old Flow: PR Review

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OLD FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. PR webhook received                                                      │
│     └─→ Celery task queued                                                  │
│                                                                              │
│  2. acknowledge node                                                         │
│     └─→ POST comment: "🤖 AI Review Started"                                │
│         └─→ Problem: Adds noise to PR                                       │
│                                                                              │
│  3. extract_context node                                                     │
│     ├─→ Load .reviewer.yaml from repo                                       │
│     ├─→ Fetch PR files from GitHub                                          │
│     └─→ RAG Enrich (THE PROBLEM):                                           │
│         ├─→ Parse files with internal AST                                   │
│         ├─→ For each function, query Pinecone                               │
│         │   └─→ Query namespace: owner/repo                                 │
│         │   └─→ Filter: {"calls": {"$in": [function_name]}}                │
│         │   └─→ Returns: Code from MAIN branch (indexed)                   │
│         │                                                                    │
│         └─→ ❌ PROBLEM: PR is feature→staging_new                           │
│             But context is from main branch                                  │
│             Agent gets WRONG information                                     │
│                                                                              │
│  4. smart_router node                                                        │
│     └─→ LLM classifies each file                                            │
│         └─→ Returns: {file: [security, style, logic]}                       │
│         └─→ Problem: Extra LLM call, often routes to all agents anyway     │
│                                                                              │
│  5. Parallel agent nodes (security/style/logic)                             │
│     ├─→ security_agent reviews all routed files                             │
│     ├─→ style_agent reviews all routed files                                │
│     └─→ logic_agent reviews all routed files                                │
│         └─→ Problem: Same file reviewed 3x                                  │
│         └─→ Problem: Generic prompts, not function-specific                 │
│         └─→ Problem: RAG context is from wrong branch                       │
│                                                                              │
│  6. aggregate node                                                           │
│     └─→ Merge comments from 3 agents                                        │
│         └─→ Deduplicate (often finds duplicates!)                           │
│         └─→ Problem: Duplicate detection imperfect                          │
│                                                                              │
│  7. publish node                                                             │
│     └─→ POST review to GitHub                                               │
│         └─→ Problem: Comments may reference wrong code                      │
│                                                                              │
│  TOTAL TIME: ~45 seconds                                                     │
│  TOTAL LLM CALLS: 1 (router) + 3N (agents) = 1 + 3N                         │
│  ACCURACY: Low (wrong branch context)                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New Flow: PR Review

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NEW FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. PR webhook received                                                      │
│     └─→ Celery task queued                                                  │
│                                                                              │
│  2. extract_diff node (NO LLM)                                              │
│     ├─→ GET /repos/{owner}/{repo}/pulls/{number}/files                      │
│     │                                                                        │
│     ├─→ For each modified file:                                             │
│     │   ├─→ Fetch from BASE branch (staging_new) ✅                         │
│     │   ├─→ Fetch from HEAD branch (feature/rewards) ✅                     │
│     │   └─→ Parse BOTH with tree-sitter                                     │
│     │                                                                        │
│     └─→ Output: List of FunctionChange objects                              │
│         ├─→ name, file_path                                                 │
│         ├─→ old_code (from staging_new)                                     │
│         ├─→ new_code (from feature/rewards)                                 │
│         └─→ diff                                                            │
│                                                                              │
│  3. build_call_graph node (NO LLM)                                          │
│     ├─→ For each changed function:                                          │
│     │   ├─→ Search BASE branch files for callers                           │
│     │   │   └─→ AST query: who calls this function?                        │
│     │   └─→ Extract callees from function code                              │
│     │                                                                        │
│     └─→ Output: Call graph with accurate relationships                      │
│         └─→ Based on ACTUAL code in ACTUAL branches ✅                      │
│                                                                              │
│  4. analyze_impact node (NO LLM)                                            │
│     ├─→ Compare old vs new signatures                                       │
│     ├─→ Identify breaking changes                                           │
│     ├─→ Find affected tests                                                 │
│     └─→ Output: Impact report                                               │
│                                                                              │
│  5. route_review node (Minimal LLM)                                         │
│     ├─→ Filter trivial changes (whitespace, comments)                       │
│     ├─→ Classify review depth based on impact                               │
│     └─→ Output: List of functions to review                                 │
│                                                                              │
│  6. review_function node (PARALLEL, Targeted LLM)                           │
│     ├─→ For each function (in parallel):                                    │
│     │   ├─→ Build targeted context:                                         │
│     │   │   ├─→ Before code (from staging_new) ✅                           │
│     │   │   ├─→ After code (from feature/rewards) ✅                        │
│     │   │   ├─→ Callers with context                                        │
│     │   │   └─→ Specific questions for this change                         │
│     │   │                                                                    │
│     │   └─→ LLM reviews with PRECISE context                                │
│     │                                                                        │
│     └─→ Output: ReviewComment objects                                       │
│         └─→ Merged via operator.add                                         │
│                                                                              │
│  7. aggregate node                                                           │
│     └─→ Dedupe, sort, limit                                                 │
│         └─→ Much fewer duplicates (one review per function)                │
│                                                                              │
│  8. publish_github + notify_slack (PARALLEL)                                │
│     └─→ Post review, notify team                                            │
│                                                                              │
│  TOTAL TIME: ~20 seconds                                                     │
│  TOTAL LLM CALLS: N (1 per function)                                        │
│  ACCURACY: High (correct branch context)                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Code Impact Analysis

### Files to DELETE

| File | Reason | Lines |
|------|--------|-------|
| `src/rag/indexer.py` | No longer indexing repos | ~400 |
| `src/rag/retriever.py` | Replaced with AST analysis | ~350 |
| `src/rag/chunker.py` | No longer chunking for embeddings | ~200 |
| `src/rag/embedder.py` | No embeddings needed | ~150 |
| `src/rag/vector_store.py` | No Pinecone | ~250 |
| `src/rag/call_resolution.py` | Logic moved to call_graph.py | ~300 |
| `src/agents/services/rag_enricher.py` | Replaced with context_builder.py | ~200 |
| `src/agents/nodes/acknowledger.py` | Removed - adds noise | ~50 |
| **Total** | | **~1,900** |

### Files to MODIFY

| File | Change | Impact |
|------|--------|--------|
| `src/agents/graph.py` | Complete rewrite | New node structure |
| `src/agents/state.py` | Remove RAG fields, add new fields | Schema change |
| `src/agents/nodes/context_extractor.py` | Simplify - no RAG | ~200 lines removed |
| `src/agents/nodes/smart_router.py` | Simplify routing logic | ~100 lines removed |
| `src/agents/prompts/*.py` | New targeted prompts | Complete rewrite |
| `src/app/api/webhooks.py` | Remove indexing handlers | ~100 lines removed |
| `pyproject.toml` | Remove Pinecone, add tree-sitter | Dependencies |

### Files to CREATE

| File | Purpose | Est. Lines |
|------|---------|------------|
| `src/analysis/__init__.py` | Module init | 10 |
| `src/analysis/diff_extractor.py` | Parse GitHub diffs | 150 |
| `src/analysis/ast_analyzer.py` | Tree-sitter parsing | 300 |
| `src/analysis/call_graph.py` | Build call relationships | 250 |
| `src/analysis/impact_analyzer.py` | Analyze change impact | 200 |
| `src/analysis/context_builder.py` | Assemble LLM context | 200 |
| `src/agents/nodes/diff_analysis.py` | Phase 1 node | 100 |
| `src/agents/nodes/impact_graph.py` | Phase 2 nodes | 150 |
| `src/agents/nodes/function_reviewer.py` | Phase 3 review | 200 |
| **Total** | | **~1,560** |

### Net Change

```
Lines Deleted:  ~1,900
Lines Modified: ~400 (effectively deleted and rewritten)
Lines Created:  ~1,560
──────────────────────
Net Change:     -740 lines (simpler codebase!)
```

---

## Migration Checklist

### Pre-Migration

- [ ] Document current review quality metrics
- [ ] Export sample reviews for comparison
- [ ] Backup Pinecone namespace (if needed for reference)
- [ ] Create feature branch for migration

### Phase 1: Build Analysis Layer (Week 1)

- [ ] Create `src/analysis/` directory
- [ ] Implement `DiffExtractor`
  - [ ] GitHub API integration
  - [ ] Diff parsing
  - [ ] Unit tests
- [ ] Implement `ASTAnalyzer`
  - [ ] Tree-sitter setup
  - [ ] Python parser
  - [ ] JavaScript/TypeScript parser
  - [ ] Function extraction
  - [ ] Unit tests
- [ ] Implement `CallGraphBuilder`
  - [ ] Caller finding
  - [ ] Callee extraction
  - [ ] Unit tests

### Phase 2: Build New Graph (Week 2)

- [ ] Create new state schema
- [ ] Implement `extract_diff` node
- [ ] Implement `build_call_graph` node
- [ ] Implement `analyze_impact` node
- [ ] Implement `route_review` node
- [ ] Implement `review_function` node
- [ ] Create new graph definition
- [ ] Integration tests

### Phase 3: Migrate Prompts & Aggregation (Week 3)

- [ ] Design targeted prompts
- [ ] Implement `ContextBuilder`
- [ ] Update `aggregate` node
- [ ] Update `publish_github` node
- [ ] End-to-end tests

### Phase 4: Deploy & Validate (Week 4)

- [ ] Deploy to staging environment
- [ ] Run on 10 test PRs
- [ ] Compare review quality
- [ ] Fix issues
- [ ] Deploy to production
- [ ] Monitor for 1 week
- [ ] Delete old RAG code

### Post-Migration

- [ ] Delete Pinecone namespace
- [ ] Remove Pinecone credentials from secrets
- [ ] Update documentation
- [ ] Archive old code for reference

### Rollback Plan

If issues discovered after deployment:

1. **Immediate**: Disable webhook handler (PRs won't be reviewed)
2. **Short-term**: Revert to old graph (old code still exists in git)
3. **Recovery**: Fix issues in new architecture

Keep old code in git for 30 days post-migration before deleting.

---

## Summary

### Why This Migration is Worth It

| Problem | Old Solution | New Solution |
|---------|--------------|--------------|
| Wrong branch context | Hope RAG finds relevant code | Fetch exact code from both branches |
| Shallow reviews | Generic prompts per file | Targeted prompts per function |
| High cost | 3N LLM calls | N LLM calls |
| High latency | Sequential agents | Parallel function reviews |
| Maintenance burden | Index sync, reindexing | Zero maintenance |
| Hallucinations | "Related" code from wrong branch | Precise code with explicit relationships |

### Expected Outcomes

After migration:

1. **Review Quality**: Reviews based on actual code, not approximations
2. **Cost**: 66% reduction in LLM costs
3. **Speed**: 55% faster reviews
4. **Maintenance**: Zero ongoing maintenance
5. **Accuracy**: Comments reference correct code from correct branches
