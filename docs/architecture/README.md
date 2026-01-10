# PR Review System v2 - Architecture Documentation

> **Version**: 2.0  
> **Last Updated**: January 2026  
> **Status**: Proposed Architecture for Migration

## Overview

This directory contains comprehensive documentation for the redesigned PR Review System. The new architecture moves from a **Vector Database-centric RAG approach** to an **AST-based Direct Analysis approach**.

### Key Insight

> **PR review is a code understanding problem, not a document retrieval problem.**

## Documents

### 1. [ARCHITECTURE.md](./ARCHITECTURE.md)
**Start here.** High-level system design and rationale.

- Current state analysis (what's broken)
- Proposed architecture overview
- Core components and responsibilities
- Data flow diagrams
- Technology stack decisions

### 2. [GRAPH_WORKFLOW.md](./GRAPH_WORKFLOW.md)
Detailed LangGraph workflow design.

- Node structure and responsibilities
- State management schema
- Edge logic and routing
- Complete example flow walkthrough

### 3. [OLD_VS_NEW.md](./OLD_VS_NEW.md)
Side-by-side comparison for migration planning.

- Node mapping (old → new)
- Flow comparison
- Code impact analysis (what to delete/modify/create)
- Migration checklist

### 4. [CONTEXT_STRATEGY.md](./CONTEXT_STRATEGY.md)
Deep dive into context extraction.

- Modified files: diff extraction, impact identification
- New files: dependency analysis, conflict detection
- Deleted files: dangling reference detection
- Cross-file analysis: dependency graphs
- Context assembly examples

### 5. [LANGGRAPH_PATTERNS.md](./LANGGRAPH_PATTERNS.md)
LangGraph pattern implementations.

- Orchestrator-Worker pattern (parallel reviews)
- Evaluator-Optimizer pattern (quality control)
- Routing pattern (change classification)
- Service integration pattern (external tools)
- Error handling patterns

### 6. [DECISIONS.md](./DECISIONS.md)
Architecture Decision Records (ADRs).

- Why abandon vector database
- Why use Tree-sitter AST
- Why on-demand analysis
- Why function-level review
- Trade-offs and risks

## Quick Reference

### Architecture Comparison

| Aspect | Old (v1) | New (v2) |
|--------|----------|----------|
| Context Source | Vector DB (Pinecone) | GitHub API + AST |
| Code Understanding | Embedding similarity | Tree-sitter parsing |
| Branch Handling | Main branch only | Both source & target |
| Indexing | Pre-index entire repo | On-demand analysis |
| Review Granularity | File-level | Function-level |
| LLM Calls per PR | 3N (N files × 3 agents) | N (1 per function) |

### Expected Improvements

| Metric | Current | Target | Change |
|--------|---------|--------|--------|
| Context Accuracy | ~60% | ~99% | +65% |
| False Positive Rate | ~30% | ~10% | -66% |
| Review Latency | ~45s | ~25s | -44% |
| Cost per PR | ~$0.15 | ~$0.05 | -66% |
| Maintenance Hours/Month | ~8 | ~0 | -100% |

### New Graph Structure

```
┌─────────────────────────────────────────────────────────────┐
│                     NEW PIPELINE                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1: DIFF ANALYSIS (No LLM)                            │
│  └─ extract_diff → Parse PR, identify changed functions     │
│                                                              │
│  Phase 2: IMPACT ANALYSIS (No LLM)                          │
│  ├─ build_call_graph → AST-based caller/callee analysis     │
│  └─ analyze_impact → Breaking changes, test coverage        │
│                                                              │
│  Phase 3: INTELLIGENT REVIEW (Targeted LLM)                 │
│  ├─ route_review → Filter, classify review depth            │
│  ├─ review_function → Parallel per-function review          │
│  └─ aggregate → Dedupe, sort, generate summary              │
│                                                              │
│  Output: publish_github ║ notify_slack (parallel)           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Migration Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | Analysis Layer | DiffExtractor, ASTAnalyzer, CallGraphBuilder |
| 2 | Graph Integration | New nodes, state schema, ContextBuilder |
| 3 | Prompts & Aggregation | Targeted prompts, quality control |
| 4 | Deploy & Validate | Staging test, production rollout |

## Reading Order

For **understanding the architecture**:
1. ARCHITECTURE.md → Overall design
2. DECISIONS.md → Why these choices
3. CONTEXT_STRATEGY.md → How context works

For **implementing the migration**:
1. OLD_VS_NEW.md → What changes
2. GRAPH_WORKFLOW.md → How to build it
3. LANGGRAPH_PATTERNS.md → Pattern implementations

## Questions?

If anything is unclear after reading these documents, the most likely gaps are:

1. **"How does X work with Y?"** → Check GRAPH_WORKFLOW.md state flow
2. **"Why not Z?"** → Check DECISIONS.md alternatives considered
3. **"What about edge case W?"** → Check CONTEXT_STRATEGY.md examples
